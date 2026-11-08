"""feed_tariffs_from_scrapper.py — Import scraped CFE tariff tiers into MySQL.

Reads monthly tier data from the scraper's SQLite DB (scrapper/data/cfe_tarifas.db)
and upserts tariff_versions + tariff_ranges in the backend database for the
selected tariffs/months.

Stores MONTHLY tier limits exactly as scraped (max_kwh per calendar month); the
billing calculator applies the 60-day midpoint doubling itself (see
services/business/cfe_billing_calculator.py, MIDPOINT_PERIOD_FACTOR). The feed is
idempotent: only missing (tariff, year, month) combos are created unless
--overwrite is passed.

Usage:
    cd app
    python -m scripts.feed_tariffs_from_scrapper [--tariffs 1C 1D] [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger

BASE_DIR = Path(__file__).resolve().parents[4]
DEFAULT_SQLITE_PATH = BASE_DIR / "scrapper" / "data" / "cfe_tarifas.db"
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

SUMMER_MONTHS = range(4, 10)  # Apr-Sep, matching the backend calculator window


def select_season(month: int) -> str:
    """Return the season key used by the backend for a billing month.

    The billing calculator treats Apr-Sep as summer, so months 4-9 use the
    "verano" tier set and the rest use "fuera de verano".

    Args:
        month (int): Billing month (1-12).

    Returns:
        str: "verano" or "fuera de verano".
    """
    return "verano" if month in SUMMER_MONTHS else "fuera de verano"


def build_ranges(tiers: List[dict]) -> List[Dict[str, Optional[Decimal]]]:
    """Convert ordered monthly tiers into tariff_ranges rows.

    Monthly limits are stored as scraped (no 60-day doubling here). The first
    range starts at 0; each range_min is the previous tier's max_kwh; the last
    unbounded tier (max_kwh None) maps to range_max None.

    Args:
        tiers (List[dict]): Tier rows with tier_order, max_kwh, price_kwh.

    Returns:
        List[Dict[str, Optional[Decimal]]]: Range dicts with range_min,
        range_max and price_per_kwh (Decimal, quantized to column precision).
    """
    ordered = sorted(tiers, key=lambda t: t["tier_order"])
    ranges: List[Dict[str, Optional[Decimal]]] = []
    previous_max = Decimal("0")
    for tier in ordered:
        max_kwh = tier["max_kwh"]
        range_max = (
            None
            if max_kwh is None
            else Decimal(str(max_kwh)).quantize(Decimal("0.01"))
        )
        ranges.append(
            {
                "range_min": previous_max,
                "range_max": range_max,
                "price_per_kwh": Decimal(str(tier["price_kwh"])).quantize(
                    Decimal("0.00001")
                ),
            }
        )
        if range_max is not None:
            previous_max = range_max
    return ranges


def load_scraped_combos(
    sqlite_path: Path,
    tariff_codes: List[str],
    months: Optional[List[int]] = None,
) -> Dict[Tuple[str, int, int], List[dict]]:
    """Load scraped tiers from SQLite, one tier set per (code, year, month).

    Selects the season that matches the backend summer window for each month.
    If that season was not scraped but only one season exists, it is used as a
    fallback; ambiguous combos are skipped with a warning.

    Args:
        sqlite_path (Path): Path to the scraper's cfe_tarifas.db.
        tariff_codes (List[str]): Tariff codes to include (e.g. ["1C", "1D"]).
        months (Optional[List[int]]): Restrict to these months; None = all.

    Returns:
        Dict[(code, year, month), List[dict]]: Tier rows per combo (as dicts
        with tier_order, max_kwh, price_kwh, season).
    """
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite DB not found: {sqlite_path}")

    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" * len(tariff_codes))
        rows = conn.execute(
            f"""
            SELECT t.code AS code, tr.year AS year, tr.month AS month,
                   tr.season AS season, tr.tier_order AS tier_order,
                   tr.max_kwh AS max_kwh, tr.price_kwh AS price_kwh
            FROM tiers tr
            JOIN tariffs t ON t.id = tr.tariff_id
            WHERE t.code IN ({placeholders})
            ORDER BY t.code, tr.year, tr.month, tr.season, tr.tier_order
            """,
            tariff_codes,
        ).fetchall()
    finally:
        conn.close()

    by_key: Dict[Tuple[str, int, int], List[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        if months is not None and row["month"] not in months:
            continue
        by_key[(row["code"], row["year"], row["month"])].append(row)

    combos: Dict[Tuple[str, int, int], List[dict]] = {}
    for (code, year, month), tiers in by_key.items():
        season = select_season(month)
        seasonal = [t for t in tiers if (t["season"] or "") == season]
        if seasonal:
            combos[(code, year, month)] = [dict(t) for t in seasonal]
            continue
        scraped_seasons = {(t["season"] or "") for t in tiers}
        if len(scraped_seasons) == 1:
            combos[(code, year, month)] = [dict(t) for t in tiers]
            continue
        logger.warning(
            "Skipping {}-{}-{}: season '{}' not scraped (found {})",
            code, year, month, season, ", ".join(sorted(scraped_seasons)),
        )
    return combos


def feed(
    uow,
    combos: Dict[Tuple[str, int, int], List[dict]],
    overwrite: bool = False,
    dry_run: bool = False,
) -> Dict[str, object]:
    """Feed scraped combos into MySQL through a Unit of Work.

    Args:
        uow: Entered Unit of Work exposing tariff_repository,
            tariff_version_repository, tariff_range_repository, session and
            commit()/rollback(). Accepts fakes for tests.
        combos (Dict): Output of load_scraped_combos.
        overwrite (bool): Replace ranges of already-fed combos.
        dry_run (bool): Report what would happen without writing.

    Returns:
        Dict[str, object]: Summary with created/overwritten/skipped counts and
        a list of (combo, error) failures.
    """
    from model.domain.tariff_model import Tariff
    from model.domain.tariff_range_model import TariffRange
    from model.domain.tariff_version_model import TariffVersion

    summary: Dict[str, object] = {
        "created": 0,
        "overwritten": 0,
        "skipped": 0,
        "failed": [],
    }
    tariff_ids: Dict[str, Optional[int]] = {}

    for code in sorted({key[0] for key in combos}):
        tariff = uow.tariff_repository.get_by_code(code)
        if tariff is None:
            if not dry_run:
                uow.tariff_repository.add(Tariff(code=code, description=f"Tarifa doméstica {code}"))
                uow.commit()
                tariff = uow.tariff_repository.get_by_code(code)
            tariff_ids[code] = None if dry_run else tariff.id
        else:
            tariff_ids[code] = tariff.id

    for key in sorted(combos):
        code, year, month = key
        tariff_id = tariff_ids[code]
        if tariff_id is None:
            summary["created"] += 1  # dry-run: tariff row would be created
            continue
        try:
            existing = uow.tariff_version_repository.get_by_tariff_and_period(
                tariff_id, year, month
            )
            if existing is not None and not overwrite:
                summary["skipped"] += 1
                continue
            if dry_run:
                summary["overwritten" if existing is not None else "created"] += 1
                continue

            if existing is not None:
                for rng in uow.tariff_range_repository.list(
                    tariff_version_id=existing.id
                ):
                    uow.tariff_range_repository.delete(rng)
                version = existing
            else:
                version = TariffVersion(tariff_id=tariff_id, year=year, month=month)
                uow.tariff_version_repository.add(version)
                uow.session.flush()

            for rng in build_ranges(combos[key]):
                uow.tariff_range_repository.add(
                    TariffRange(
                        tariff_version_id=version.id,
                        range_min=rng["range_min"],
                        range_max=rng["range_max"],
                        price_per_kwh=rng["price_per_kwh"],
                    )
                )
            uow.commit()
            summary["overwritten" if existing is not None else "created"] += 1
            logger.info(
                "{} {}-{}-{} ({} ranges)",
                "Overwrote" if existing is not None else "Created",
                code, year, month, len(combos[key]),
            )
        except Exception as exc:  # noqa: BLE001
            uow.rollback()
            summary["failed"].append((key, str(exc)))
            logger.error("Failed {}-{}-{}: {}", code, year, month, exc)

    return summary


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point: parse args, load env, connect and feed."""
    parser = argparse.ArgumentParser(
        description="Feed scraped CFE tariff tiers (SQLite) into MySQL."
    )
    parser.add_argument(
        "--sqlite",
        default=str(DEFAULT_SQLITE_PATH),
        help="Path to the scraper SQLite DB (default: %(default)s)",
    )
    parser.add_argument(
        "--tariffs",
        nargs="+",
        default=["1C", "1D"],
        help="Tariff codes to import (default: %(default)s)",
    )
    parser.add_argument(
        "--months",
        nargs="+",
        type=int,
        default=None,
        help="Restrict to these months 1-12 (default: all)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace ranges of already-fed (tariff, year, month) combos",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be fed without writing anything",
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help="Path to a .env file with DB_* variables (default: %(default)s)",
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    if Path(args.env_file).exists():
        from dotenv import load_dotenv

        load_dotenv(args.env_file, override=False)
    # common.config raises if SECRET_KEY is unset; the feed only needs DB_* vars.
    os.environ.setdefault("SECRET_KEY", "0" * 64)

    logger.remove()
    logger.add(sys.stderr, level=args.log_level.upper())

    for var in ("DB_HOST", "DB_PORT", "DB_USER", "DB_PSWD", "DB_NAME"):
        if not os.getenv(var):
            parser.error(f"Missing environment variable {var} (use --env-file)")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import pymysql

    # The app expects the mysqlclient DBAPI; locally we use PyMySQL as a
    # drop-in via the MySQLdb alias so db.uow/db.database imports succeed.
    pymysql.install_as_MySQLdb()

    from db.orm import start_mappers
    from db.uow import TariffConsumptionUnitofWork

    start_mappers()

    engine = create_engine(
        f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PSWD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
        "?charset=utf8mb4",
        pool_pre_ping=True,
    )
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    combos = load_scraped_combos(Path(args.sqlite), args.tariffs, args.months)
    logger.info(
        "Loaded {} combos from {} (tariffs={}, months={})",
        len(combos), args.sqlite, args.tariffs, args.months or "all",
    )

    uow = TariffConsumptionUnitofWork()
    uow.__enter__(session_factory=session_factory)
    try:
        summary = feed(uow, combos, overwrite=args.overwrite, dry_run=args.dry_run)
    finally:
        uow.__exit__(None, None, None)

    logger.info(
        "{} summary: created={}, overwritten={}, skipped={}, failed={}",
        "DRY-RUN" if args.dry_run else "Feed",
        summary["created"], summary["overwritten"], summary["skipped"],
        len(summary["failed"]),
    )
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
