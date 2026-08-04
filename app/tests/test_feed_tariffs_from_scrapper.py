"""Tests for scripts.feed_tariffs_from_scrapper (pure helpers + feed orchestration).

Uses stdlib unittest and fake repositories so no MySQL/SQLite connection is
needed. Run with: python -m unittest discover -s tests -v
"""
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import unittest

from scripts.feed_tariffs_from_scrapper import (
    build_ranges,
    feed,
    load_scraped_combos,
    select_season,
)


class SelectSeasonTests(unittest.TestCase):
    def test_summer_months_use_verano(self):
        for month in (4, 5, 6, 7, 8, 9):
            self.assertEqual(select_season(month), "verano")

    def test_non_summer_months_use_fuera_de_verano(self):
        for month in (1, 2, 3, 10, 11, 12):
            self.assertEqual(select_season(month), "fuera de verano")


class BuildRangesTests(unittest.TestCase):
    def test_three_tier_monthly_mapping(self):
        tiers = [
            {"tier_order": 1, "max_kwh": 75.0, "price_kwh": 1.132},
            {"tier_order": 2, "max_kwh": 200.0, "price_kwh": 1.377},
            {"tier_order": 3, "max_kwh": None, "price_kwh": 4.028},
        ]

        ranges = build_ranges(tiers)

        self.assertEqual(
            ranges,
            [
                {"range_min": Decimal("0"), "range_max": Decimal("75.00"),
                 "price_per_kwh": Decimal("1.13200")},
                {"range_min": Decimal("75.00"), "range_max": Decimal("200.00"),
                 "price_per_kwh": Decimal("1.37700")},
                {"range_min": Decimal("200.00"), "range_max": None,
                 "price_per_kwh": Decimal("4.02800")},
            ],
        )

    def test_four_tier_verano_mapping(self):
        tiers = [
            {"tier_order": 4, "max_kwh": None, "price_kwh": 3.992},
            {"tier_order": 1, "max_kwh": 175.0, "price_kwh": 1.004},
            {"tier_order": 3, "max_kwh": 600.0, "price_kwh": 1.495},
            {"tier_order": 2, "max_kwh": 400.0, "price_kwh": 1.163},
        ]

        ranges = build_ranges(tiers)

        self.assertEqual(
            [r["range_min"] for r in ranges],
            [Decimal("0"), Decimal("175.00"), Decimal("400.00"), Decimal("600.00")],
        )
        self.assertEqual(
            [r["range_max"] for r in ranges],
            [Decimal("175.00"), Decimal("400.00"), Decimal("600.00"), None],
        )
        self.assertEqual([r["price_per_kwh"] for r in ranges],
                         [Decimal("1.00400"), Decimal("1.16300"),
                          Decimal("1.49500"), Decimal("3.99200")])

    def test_out_of_order_tiers_are_sorted_by_tier_order(self):
        tiers = [
            {"tier_order": 3, "max_kwh": None, "price_kwh": 3.0},
            {"tier_order": 1, "max_kwh": 75.0, "price_kwh": 1.0},
            {"tier_order": 2, "max_kwh": 150.0, "price_kwh": 2.0},
        ]

        ranges = build_ranges(tiers)

        self.assertEqual(ranges[0]["range_min"], Decimal("0"))
        self.assertEqual(ranges[1]["range_min"], Decimal("75.00"))
        self.assertEqual(ranges[2]["range_min"], Decimal("150.00"))


class LoadScrapedCombosTests(unittest.TestCase):
    def test_selects_season_matching_summer_window(self):
        combos = load_scraped_combos(
            _SQLITE_PATH, ["1C"], months=[8]
        )

        # August -> verano set (4 tiers for 1C)
        tiers = combos[("1C", 2026, 8)]
        self.assertEqual(len(tiers), 4)
        self.assertTrue(all(t["season"] == "verano" for t in tiers))

    def test_excludes_dac_and_other_tariffs(self):
        # The CLI default only selects 1C/1D; DAC requires explicit selection.
        combos = load_scraped_combos(_SQLITE_PATH, ["1C", "1D"], months=None)

        self.assertTrue(all(code in ("1C", "1D") for code, _, _ in combos))
        self.assertEqual(len(combos), 24)

        dac_combos = load_scraped_combos(_SQLITE_PATH, ["DAC"], months=None)
        self.assertEqual(len(dac_combos), 8)  # DAC scraped only for months 1-8

    def test_filters_months(self):
        combos = load_scraped_combos(_SQLITE_PATH, ["1C"], months=[1, 2])

        self.assertEqual(sorted((m for _, _, m in combos)), [1, 2])
        for (code, year, month) in combos:
            self.assertEqual(len(combos[(code, year, month)]), 3)  # fuera de verano


class FeedTests(unittest.TestCase):
    def _make_fake_uow(self, existing):
        rows = {}

        class FakeVersionRepo:
            def get_by_tariff_and_period(self, tariff_id, year, month):
                return existing.get((tariff_id, year, month))

            def add(self, version):
                version.id = max(rows, default=0) + 1
                rows[version.id] = version

        class FakeRangeRepo:
            def list(self, tariff_version_id):
                return [r for r in range_rows if r.tariff_version_id == tariff_version_id]

            def add(self, rng):
                rng.id = len(range_rows) + 1
                range_rows.append(rng)

            def delete(self, rng):
                range_rows.remove(rng)

        range_rows = []
        existing_ids = {v.id for v in existing.values()}

        tariff = SimpleNamespace(id=2, code="1C")

        class FakeTariffRepo:
            def get_by_code(self, code):
                return tariff if code == "1C" else None

            def add(self, model):
                pass

        uow = SimpleNamespace(
            tariff_repository=FakeTariffRepo(),
            tariff_version_repository=FakeVersionRepo(),
            tariff_range_repository=FakeRangeRepo(),
            session=SimpleNamespace(flush=lambda: None),
            committed=0,
        )
        uow.commit = lambda: setattr(uow, "committed", uow.committed + 1)
        uow.rollback = lambda: None
        return uow, range_rows

    def test_creates_missing_combos_with_monthly_ranges(self):
        uow, range_rows = self._make_fake_uow({})
        combos = {("1C", 2026, 1): [
            {"tier_order": 1, "max_kwh": 75.0, "price_kwh": 1.11},
            {"tier_order": 2, "max_kwh": 175.0, "price_kwh": 1.349},
            {"tier_order": 3, "max_kwh": None, "price_kwh": 3.944},
        ]}

        summary = feed(uow, combos)

        self.assertEqual(summary["created"], 1)
        self.assertEqual(summary["overwritten"], 0)
        self.assertEqual(summary["skipped"], 0)
        self.assertEqual(len(range_rows), 3)
        self.assertEqual(range_rows[0].range_min, Decimal("0"))
        self.assertEqual(range_rows[0].range_max, Decimal("75.00"))
        self.assertEqual(range_rows[2].range_max, None)

    def test_skips_existing_combos_without_overwrite(self):
        existing_version = SimpleNamespace(id=7, tariff_id=2, year=2026, month=1)
        uow, range_rows = self._make_fake_uow({(2, 2026, 1): existing_version})
        combos = {("1C", 2026, 1): [
            {"tier_order": 1, "max_kwh": 75.0, "price_kwh": 1.11},
        ]}

        summary = feed(uow, combos)

        self.assertEqual(summary["skipped"], 1)
        self.assertEqual(range_rows, [])

    def test_overwrite_replaces_existing_ranges(self):
        existing_version = SimpleNamespace(id=7, tariff_id=2, year=2026, month=1)
        uow, range_rows = self._make_fake_uow({(2, 2026, 1): existing_version})
        uow.tariff_range_repository.add(
            SimpleNamespace(tariff_version_id=7, range_min=Decimal("0"),
                            range_max=Decimal("150.00"))
        )
        combos = {("1C", 2026, 1): [
            {"tier_order": 1, "max_kwh": 75.0, "price_kwh": 1.11},
        ]}

        summary = feed(uow, combos, overwrite=True)

        self.assertEqual(summary["overwritten"], 1)
        self.assertEqual(len(range_rows), 1)
        self.assertEqual(range_rows[0].range_max, Decimal("75.00"))

    def test_dry_run_writes_nothing(self):
        uow, range_rows = self._make_fake_uow({})
        combos = {("1C", 2026, 1): [
            {"tier_order": 1, "max_kwh": 75.0, "price_kwh": 1.11},
        ]}

        summary = feed(uow, combos, dry_run=True)

        self.assertEqual(summary["created"], 1)
        self.assertEqual(range_rows, [])
        self.assertEqual(uow.committed, 0)


def _sqlite_path():
    return Path(__file__).resolve().parents[4] / "scrapper" / "data" / "cfe_tarifas.db"


_SQLITE_PATH = _sqlite_path()


if __name__ == "__main__":
    unittest.main()
