# AGENTS.md — Context for AI Agents (api-cfe)

## Project Overview

**api-cfe** is a FastAPI-based backend for the CFE (Comisión Federal de Electricidad) project. It provides a RESTful API for managing household electricity tariff data, including tariffs, tariff versions, tariff ranges, meter readings, billing periods, households, and dashboards. It also includes a JWT-based authentication system with OAuth2 password flow.

The project uses **imperative SQLAlchemy ORM mapping** (Core `Table` definitions + `registry.map_imperatively`) with a MySQL database, following a **Unit of Work + Repository** architectural pattern.

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy (imperative mapping) |
| Database | MySQL (via `mysqlclient` / `MySQLdb`) |
| Auth | JWT (`python-jose`), password hashing (`passlib` + `bcrypt`) |
| Validation | Pydantic |
| Logging | Loguru |
| Containerization | Docker + Docker Compose |
| CI/CD | GitHub Actions (self-hosted runner) |
| Python Version | 3.12+ |

## Project Structure

```
app/
  main.py              # FastAPI app entrypoint; registers middleware, routers, ORM mappers
  requirements.pip     # Python dependencies
  common/              # Shared utilities
    config.py          # Environment-based config (DB, JWT, Twilio, HSM, etc.)
    logging.py         # Loguru interceptor for stdlib logging
    services/          # Shared service dependencies (e.g., auth_dependency, APIKeyChecker)
    api/errors/        # Custom exception handlers (HTTP, validation, entity not found)
  db/                  # Persistence layer
    database.py        # SQLAlchemy engine & session factory (MySQL)
    orm.py             # Table definitions + imperative mapper (start_mappers)
    uow.py             # Unit of Work (TariffConsumptionUnitofWork) with all repositories
    repositories/      # Per-entity repository classes
      billing_period_repository.py
      household_repository.py
      household_tariff_repository.py
      meter_reading_repository.py   # incl. get_by_billing_period_and_date_range, first/last reading in range
      tariff_range_repository.py
      tariff_repository.py
      tariff_version_repository.py  # incl. get_by_tariff_and_period_or_latest_before
      url_repository.py             # URL-shortener (legacy; wired as uow.url_shotner_repository — note typo)
      user_repository.py
  model/               # Pydantic serializers & domain models
    domain/            # Domain entities (BillingPeriod, Household, Tariff, User, UrlModel, etc.)
    auth.py            # Auth-related Pydantic models
    dashboard_serializers.py  # All dashboard response models (see Dashboard Serializers)
    serializers.py            # URL-shortener Pydantic models (legacy: URLBase, URLCreate, URL, URLDelete, ShortURLResponse)
    *_serializers.py   # Pydantic output serializers per domain (tariff, household, billing_period, etc.)
    errors.py          # EntityNotFoundException + 420 handler
  scripts/             # Standalone CLI utilities
    feed_tariffs_from_scrapper.py  # Import scraped tiers (SQLite) into tariff_versions/ranges (see Feeding Scraped Tariffs)
    __init__.py
  routes/              # API routers (all under /api/v1 prefix)
    api.py             # Router aggregation (include_router for each registered router)
    auth.py            # JWT auth (login, register, refresh, /me)
    billing_periods.py
    dashboards.py      # Dashboard endpoints (auth-protected; see Dashboard Endpoints)
    households.py
    household_tariffs.py
    meter_readings.py
    tariff_ranges.py
    tariff_versions.py
    tariffs.py
    controller.py      # URL-shortener router (LEGACY — NOT registered in api.py; see Gotchas)
  services/            # Application/business logic handlers
    business/          # Business-specific calculation services
      __init__.py                # MeterReadingConsumptionCalculator.calculate_total: Consumo between first/last Lectura in a range
      billing_service.py        # BillingService: period cost + multi-period summary (consumption + Costo total -> response)
      costo_total.py            # CostoTotal: sole module pricing a Consumo (Asignación, Fecha efectiva, segments, proration, taxes)
      costo_total_catalog.py    # TariffCatalog adapters: UowTariffCatalog (prod), InMemoryTariffCatalog (tests)
      history_rows.py           # the one Consumo derivation: consumption_between, daily_average, build_history_rows
      period_utils.py           # Billing period date/segment utilities (midpoint_date, MonthSegment, split_by_month_segments)
    errors.py                   # Domain errors (no HTTP): DashboardDomainError -> InvalidFilterError, HouseholdNotFoundError, BillingPeriodNotFoundError, BillingPeriodOwnershipError
    dashboard_service.py        # DashboardService: household consumption dashboard + meter-reading history (filters, validation, cost per interval)
    constants.py                # URL-shortener constants (legacy: HOST_URL, CREATE/DELETE_API_KEY, TIME_EXPIRATION_URL)
    *_handler.py       # CRUD/service methods per domain
    tariff_version_normalizer.py
  common/
    config.py          # Environment-based config (DB, JWT, Twilio, HSM, etc.)
    logging.py         # Loguru interceptor for stdlib logging
    services/          # Shared service dependencies (auth_dependency, APIKeyChecker, auth_audit, time_decorator)
    api/errors/        # Custom exception handlers (http_error, validation_error, entity not found)
    api/responses.py   # Shared OpenAPI response dict
    db/base.py         # BaseRepository
    db/abstract_unit_of_work.py  # AbstractUnitOfWork
    model/rest.py      # Dashboard REST filter dataclasses (MeterReadingFilters, ResolvedMeterReadingQuery, IntervalDetails)
```

## Key Architectural Patterns

### Unit of Work + Repository

All database access goes through `TariffConsumptionUnitofWork`, which acts as a context manager aggregating multiple repositories:

```python
with TariffConsumptionUnitofWork() as uow:
    user = uow.user_repository.get_by_username(username)
    uow.commit()
```

Repositories include: `HouseholdRepository`, `TariffRepository`, `MeterReadingRepository`, `BillingPeriodRepository`, `TariffVersionRepository`, `TariffRangeRepository`, `HouseholdTariffRepository`, `UserRepository`, and the legacy `UrlRepository` (exposed on the UoW as the misspelled attribute `url_shotner_repository`).

### Imperative ORM Mapping

SQLAlchemy mappings are done imperatively in `db/orm.py` via `start_mappers()`, called at app startup in `main.py`. Tables are defined using SQLAlchemy Core `Table` constructs, then mapped to domain classes.

### Router Registration

All routers are defined in `app/routes/api.py` under the `/api/v1` prefix. New routes must be imported and included there.

### Dashboard Service Architecture

Dashboard endpoints live in `routes/dashboards.py` and are **auth-protected** (`dependencies=[Depends(get_current_user)]`). They follow a layered composition:

- **`services/dashboard_service.py` (`DashboardService`)** — the service layer for the meter-reading history use-case. Owns a UoW factory (`TariffConsumptionUnitofWork` by default), validates filters, resolves the effective date range, fetches readings via `meter_reading_repository.get_by_billing_period_and_date_range`, and builds a per-reading history with cumulative cost per interval (pricing each interval with `CostoTotal`). Also serves the household consumption dashboard (`get_household_consumption_dashboard`, raises `BillingServiceError` 422 for a missing household). Tolerates `CostoTotalError` per interval (sets `billing_period_cost=None`).
  - Validation: **400** if neither `billing_period_id` nor a complete `start_date`+`end_date` range is provided; **400** if `start_date > end_date`; **404** for missing household/billing period; **400** if the billing period does not belong to the household.
- **`services/business/costo_total.py` (`CostoTotal`)** — the single module that prices a Consumo. `calculate(consumo, vivienda_id, start, end, periodo_id=None)` returns a `Desglose`; a Periodo, if given, is read once and its end date replaces `end` for Fecha efectiva and segmentation. Its only seam is a `TariffCatalog` (`UowTariffCatalog` in production, `InMemoryTariffCatalog` in tests). Raises `CostoTotalError` subclasses only.
- **`services/business/billing_service.py` (`BillingService`)** — wraps `CostoTotal` + `MeterReadingConsumptionCalculator` into `BillingPeriodCostResponse`: `calculate_billing_period_cost`, `calculate_cost_for_date_range`, `get_multiple_periods_summary`. Maps `CostoTotalError` to `BillingServiceError(message)`; `BillingServiceError` carries no status code (routes map it to 422). `load_household(uow, id, not_found=BillingServiceError)` is the single Vivienda lookup; the history passes `HouseholdNotFoundError` (404), the billing routes keep 422. `cost_for_consumption` prices an already-derived Consumo. `calculate_cost_for_date_range` has no production caller; it stays as the legacy oracle for characterization tests.

- **`CachedTariffCatalog`** (`costo_total_catalog.py`) — memoizing decorator over a `TariffCatalog`; the history flow wraps `UowTariffCatalog` in it so per-row pricing does not re-query the tariff data.
- **`services/business/history_rows.py` (`build_history_rows`)** — pure function turning ordered readings into rows (cumulative Consumo, since-last delta/days/avg) plus total. `consumption_between` (also used by `MeterReadingConsumptionCalculator.calculate_total`) and `daily_average` (used by billing and the household dashboard) keep Consumo derived in one module. Routes build `DashboardService` only through `routes/dashboards.py` `dashboard_service()`.
- **Single status map** — `routes/dashboards.py` `HTTP_STATUS_BY_ERROR` (looked up via MRO in `domain_errors_as_http`) is the only place domain errors become HTTP: `InvalidFilterError`/`BillingPeriodOwnershipError` 400, `HouseholdNotFoundError`/`BillingPeriodNotFoundError` 404, `BillingServiceError` 422. Services raise `services/errors.py` types only; the `start_date > end_date` route checks raise `InvalidFilterError` too.

### Dashboard Serializers

All dashboard response Pydantic models are defined in `app/model/dashboard_serializers.py`:

| Model | Purpose |
|---|---|
| `CfeTierLineItem` | One CFE tier segment (level, name, prorated capacity, kWh charged, price, subtotal) |
| `CfeBillingBreakdownResponse` | `tier_lines` + `subtotal_before_taxes`, `iva`, `dap`, `total` |
| `BillingPeriodCostResponse` | Full period cost (consumption, avg daily, tariff code, taxes, `cfe_breakdown`) |
| `ActiveTariffResponse` / `ActiveTariffVersionResponse` | Resolved tariff/version used for a calculation |
| `TariffCostCalculationResponse` | Tariff version + dap/iva cost components |
| `HouseholdConsumptionDashboardResponse` | Single-household consumption overview with reading points |
| `MultiplePeriodsSummaryResponse` | Multi-period comparison aggregating `BillingPeriodCostResponse` |
| `MeterReadingWithHistoryResponse` | Single reading with since-last consumption/avg and per-reading `billing_period_cost` |
| `MeterReadingHistoryDashboardResponse` | Household + billing period + period range + readings history |
| `HouseholdResponse` / `DateRangeResponse` / `BillingPeriodInfoResponse` | Shared nested models |

Dashboard REST filter/internals live in `app/common/model/rest.py` as frozen dataclasses: `MeterReadingFilters`, `ResolvedMeterReadingQuery`, `IntervalDetails` (plus `ValidationErrorModel`).

## Building and Running

### Prerequisites

- Python 3.12+
- MySQL database accessible
- Docker & Docker Compose (optional)

### Local Installation (without Docker)

```bash
cd app
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.pip
```

### Running Locally

```bash
cd app
uvicorn main:app --host 0.0.0.0 --port 8080
```

### Docker / Docker Compose

```bash
docker compose up --build
```

Requires:
- A `.env` file with environment variables (see Configuration below)
- An external Docker network named `db-test-net`

### CI/CD Deployment

Pushing to `main` triggers a GitHub Actions workflow on a self-hosted runner that builds and deploys via Docker Compose.

## Configuration

Environment variables (set in `.env` or shell):

| Variable | Description |
|---|---|
| `DB_HOST` | MySQL host |
| `DB_PORT` | MySQL port (default: 3306) |
| `DB_USER` | Database user |
| `DB_PSWD` | Database password |
| `DB_NAME` | Database name |
| `SECRET_KEY` | JWT signing secret |
| `LOGGING_LEVEL` | Log level (DEBUG/INFO) |
| `REGISTER_API_KEY` | API key required for user registration |

Additional optional vars: `TWILIO_USER_NAME`, `TWILIO_USER_PWD`, `TWILIO_FROM_NUMBER`, `TWILIO_PHONE_WHATSAPP`, `COMMON_ENCRYPT_KEY`, `COMMON_ENCRYPT_IMG_KEY`, `HSM_HOST`, `HSM_PORT`, `CURRENT_DOMAIN`.

Legacy URL-shortener env vars (only referenced by the unwired `routes/controller.py` / `services/constants.py`): `HOST_URL`, `CREATE_API_KEY`, `DELETE_API_KEY`.

## Authentication

Endpoints live under `/api/v1/auth`:

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Create a new user (requires `REGISTER_API_KEY` header) |
| `POST` | `/auth/login` | OAuth2 password flow – returns access + refresh tokens |
| `POST` | `/auth/refresh` | Rotate refresh token and get new access token |
| `GET` | `/auth/me` | Get current user info (protected, requires Bearer token) |

- JWT algorithm: HS256
- Access token expiry: 12 hours
- Refresh token expiry: 7 days
- Password hashing: bcrypt via passlib
- Token refresh: Supported with automatic rotation

### Full API Endpoints

| Module | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me` |
| Tariffs | `GET /tariffs`, `POST /tariffs`, `GET /tariffs/{id}`, `PUT /tariffs/{id}`, `DELETE /tariffs/{id}` |
| Tariff Versions | `GET /tariff-versions`, `POST /tariff-versions`, `GET /tariff-versions/{id}`, `PUT /tariff-versions/{id}`, `DELETE /tariff-versions/{id}` |
| Tariff Ranges | `GET /tariff-ranges`, `POST /tariff-ranges`, `GET /tariff-ranges/{id}`, `PUT /tariff-ranges/{id}`, `DELETE /tariff-ranges/{id}` |
| Households | `GET /households`, `POST /households`, `GET /households/{id}`, `PUT /households/{id}`, `DELETE /households/{id}` |
| Meter Readings | `GET /meter-readings`, `POST /meter-readings`, `GET /meter-readings/{id}`, `DELETE /meter-readings/{id}` |
| Billing Periods | `GET /billing-periods`, `POST /billing-periods`, `GET /billing-periods/{id}`, `DELETE /billing-periods/{id}` |
| Household Tariffs | `GET /household-tariffs`, `POST /household-tariffs`, `GET /household-tariffs/{id}`, `DELETE /household-tariffs/{id}` |
| Dashboards (auth-protected) | `GET /dashboards/billing-period/{billing_period_id}`, `GET /dashboards/household/{household_id}/consumption`, `GET /dashboards/household/{household_id}/billing-summary`, `GET /dashboards/household/{household_id}/meter-readings` |

## Domain Entities

The system manages the following core domain concepts:

- **Household** – A residential unit consuming electricity
- **Tariff** – A tariff definition (code + description)
- **TariffVersion** – A versioned tariff for a specific year/month
- **TariffRange** – Price bands within a tariff version (min/max kWh range, price per kWh)
- **MeterReading** – KWh meter readings for a household
- **BillingPeriod** – Billing period for a household (start/end dates)
- **HouseholdTariff** – Association between a household and a tariff over a date range
- **User** – Authenticated system user (username, email, role, active status)

## Development Conventions

- **Pydantic serializers** live in `model/` with `*_serializers.py` naming for output schemas
- **Domain models** live in `model/domain/` as plain Python classes (imperatively mapped)
- **Route handlers** in `routes/` should delegate to services in `services/` or repositories via UoW
- **Custom exceptions**: Use `EntityNotFoundException` for 420 responses; FastAPI `HTTPException` for standard errors
- **Logging**: Use Loguru; stdlib logging is intercepted via `InterceptHandler`

## Standards

Write English Google-style docstrings for public modules, classes and functions. Include only applicable sections; explain intent, arguments, return values and errors when useful:

```python
def example(value: int) -> int:
    """Summarize the operation in one sentence.

    Args:
        value: Input to the operation.

    Returns:
        The resulting value.

    Raises:
        ValueError: If the input is invalid.
    """
    if value < 0:
        raise ValueError("value must be non-negative")
    return value
```

Use SOLID as design guidance, not a mandate for extra classes:

- **Single responsibility:** `CostoTotal` prices consumption; `BillingService` orchestrates consumption, pricing and response construction instead of duplicating pricing.
- **Open/closed:** `CostoTotal` accepts a tariff catalog; `UowTariffCatalog`, `InMemoryTariffCatalog` and `CachedTariffCatalog` supply or decorate that behavior without changing the calculator.
- **Liskov substitution:** catalog implementations must preserve the same lookup semantics, including ordering and missing values, so pricing works with either adapter.
- **Interface segregation:** keep the catalog focused on the lookups pricing needs rather than exposing the entire UoW to the calculator.
- **Dependency inversion:** the calculator depends on the catalog seam, while `UowTariffCatalog` bridges to UoW repositories; the UoW groups persistence and transaction boundaries. Some services still construct concrete dependencies, so this is a direction, not a claim of universal inversion.

### Checks and baseline

From the repository root, after installing the runtime dependencies as above:

```bash
app/.venv/bin/python -m pip install -r app/requirements-dev.pip
source app/.venv/bin/activate
pre-commit install
pre-commit run ruff-check --all-files
pre-commit run ruff-format --all-files
pre-commit run mypy --all-files
pre-commit run --all-files
```

`ruff check` selects E, F, I, Google-convention D, C90 and PLR0913; the complexity limit is 10 and the argument limit is 5. Tests and `__init__.py` are exempt from D rules. Ruff cannot verify that docstrings are English or that a design is SOLID. Mypy uses strict mode with missing imports ignored, so missing type information can escape checking.

The hooks compare Ruff diagnostics, individual formatting edits and mypy diagnostics against `scripts/standards-baseline.json`. Each diagnostic is identified by its path, rule/message and source line; formatting edits include their original and formatted text. Occurrence counts prevent an additional identical violation from being hidden. Changes that alter an existing diagnostic or formatting block can require cleaning up that legacy issue. Raw `ruff check`, `ruff format --check`, and `mypy app` report legacy violations as well; use the hooks for baseline-aware results. Mypy checks the entire `app` tree; the other hooks check selected Python files. Local hooks require the activated environment and can be bypassed; they are not CI enforcement.

When fixing legacy issues, remove their entries (or reduce their counts) in `scripts/standards-baseline.json`, then run `pre-commit run --all-files` and the existing unit tests. Do not regenerate or expand the baseline to accommodate new violations. The matching scheme cannot distinguish replacing a legacy violation with an identical one in the same file when the total count stays unchanged; review such moves. Avoid broad formatting or unrelated rewrites.

See [ADR 0004](docs/adr/0004-python-standards.md) for the trade-offs.

## Notable Gotchas

- `bcrypt==4.0.1` is pinned because newer versions are incompatible with `passlib 1.7.4`
- The ORM uses `expire_on_commit=False` to avoid lazy-load issues after commits
- The Dockerfile uses a multi-stage build with Alpine + MariaDB connector for `mysqlclient`
- Database isolation level is set to `REPEATABLE READ`
- The `EntityNotFoundException` handler returns HTTP status **420** (non-standard)
- **Dashboard routes are auth-protected** (`Depends(get_current_user)`) — unlike the older documented `/dashboards/summary` / `/dashboards/consumption` endpoints which no longer exist. The current endpoints are `/dashboards/billing-period/{id}`, `/dashboards/household/{id}/consumption`, `/dashboards/household/{id}/billing-summary`, and `/dashboards/household/{id}/meter-readings`.
- **Legacy / dead URL-shortener code**: `routes/controller.py`, `model/serializers.py`, `model/domain/url_model.py`, `db/repositories/url_repository.py`, and `services/constants.py` belong to an unfinished URL-shortener feature. `controller.py` is **NOT registered** in `routes/api.py` and imports `services.short_code_handler`, which **does not exist** — importing the module fails. Do not register `controller.py` until `short_code_handler` is restored. The `UrlRepository` is wired into the UoW as the misspelled `url_shotner_repository`. The FastAPI app title in `main.py` is still `"URL shortener"` (legacy).
- `BillingPeriodCostResponse` carries the backend typo `total_cost_witout_taxes` (note `"witout"`); the frontend intentionally mirrors this field name — do not "fix" it without coordinating both sides.
- **`tariff_ranges` store MONTHLY tier limits** (as scraped from CFE). The 60-day bimonthly convention lives in the calculator: `MIDPOINT_PERIOD_FACTOR = 2` in `services/business/costo_total.py` doubles tier capacity only on the single-segment (midpoint) path (`MonthSegment.capacity_factor`, set by `_midpoint_segment`). Per-month segments (cross-season, minority ≥ 15 days) use stored monthly values prorated by calendar days. Do not store ×2 limits in the DB.
- **Missing month versions degrade silently**: `get_by_tariff_and_period_or_latest_before` falls back to the latest earlier month's version (logged, no error). Keep every month referenced by billing periods/dashboards fed.



## Working Rules

### Codegraph (Mandatory First)

**Always use codegraph tools FIRST** for any code exploration, search, or navigation task. Do NOT use `grep`, `read`, or `glob` for code discovery unless codegraph tools cannot satisfy the query.

**Codegraph tools to use first:**
- `codegraph_find_symbol` — Find exact or fuzzy symbol matches (classes, functions, variables)
- `codegraph_search_symbols` — Search symbol names, signatures, and docs
- `codegraph_search_semantic` — Hybrid semantic search (vector + FTS)
- `codegraph_find_callers` / `codegraph_find_callees` — Trace call relationships
- `codegraph_trace_dependencies` — Trace transitive dependency chains
- `codegraph_context_for_task` — Get relevant files/symbols for a task description
- `codegraph_find_related_tests` — Find tests related to a symbol or file
- `codegraph_get_impact_radius` — Estimate affected symbols/files around a change
- `codegraph_find_dead_code` — Find unused symbols
- `codegraph_graph_analytics` — Run pagerank, coupling, or cycle analysis

**Fallback:** Only use `grep`, `read`, `glob`, or the `explore` subagent if codegraph tools return no results or cannot answer the specific query (e.g., searching raw file content, non-code files, or config values not captured as symbols).

### General Rules

- Use the `docs` subagent for library, API, setup, and configuration questions.
- Prefer Context7 for current, version-specific documentation instead of relying on model memory.
- If a task depends on repo code, inspect the local files first and then consult Context7 for external API details.
- Keep changes minimal and preserve the current FastAPI modular route layout.
- Avoid guessing about external APIs when a docs lookup can confirm the behavior.
- All database operations must go through the Unit of Work pattern.
- New endpoints must be registered in `app/routes/api.py`.
- Use Pydantic serializers for response validation in `model/` directory.

## Context7

- The project uses Context7 through OpenCode MCP.
- The docs-focused subagent lives at `.opencode/agents/docs.md`.

## Testing

- Stdlib `unittest` (no pytest), tests in `app/tests/`. No MySQL needed.
- Run: `cd app && .venv/bin/python -m unittest discover -s tests -v`
- The scraper-feed tests also read `scrapper/data/cfe_tarifas.db` from the CFE monorepo layout; a standalone worktree without that relative path will fail those tests.
- Files:
  - `fakes.py` — shared `FakeRepository`, `FakeUoW`, `make_client` (not a test module).
  - Calculator/scripts: `test_costo_total.py`, `test_costo_total_pricing.py`, `test_costo_total_characterization.py`, `test_dashboard_history_costs.py`, `test_history_rows.py`, `test_history_single_load.py`, `test_period_rules.py`, `test_feed_tariffs_from_scrapper.py`.
  - Route tests: `test_auth_routes.py`, `test_billing_periods_routes.py`, `test_dashboards_routes.py`, `test_households_routes.py`, `test_households_routes_crud.py`, `test_household_tariffs_routes.py`, `test_meter_readings_routes.py`, `test_tariff_model_routes.py`.
  - Cross-cutting: `test_dashboard_error_mapping.py`, `test_error_responses.py`, `test_security_and_rate_limit.py`.
- Writing a route test: build a `FakeUoW()`, seed `uow.<name>_repository.add(entity)`, then `with make_client(uow) as client: client.get("/api/v1/...")`. `make_client` swaps every module's `TariffConsumptionUnitofWork` for the fake and overrides `get_current_user`; pass `user=None` to exercise real auth/401s. The fake UoW keeps state across requests; assert on its repos and `uow.committed`.
- Name tests with `GLOSSARY.md` vocabulary (Household, Billing Period, Tariff Version, ...).
- Tests pin current behavior. Bugs found are reported (e.g. as issues), not fixed in the test change.
- Manual testing is done via curl or API clients like Postman/Insomnia.

## Feeding Scraped Tariffs

`scripts/feed_tariffs_from_scrapper.py` imports scraped CFE tiers from the scraper's SQLite DB (`scrapper/data/cfe_tarifas.db`) into MySQL `tariff_versions` + `tariff_ranges`:

```bash
cd app
.venv/bin/python -m scripts.feed_tariffs_from_scrapper            # 1C + 1D, all months, missing only
.venv/bin/python -m scripts.feed_tariffs_from_scrapper --overwrite  # also replace already-fed combos
.venv/bin/python -m scripts.feed_tariffs_from_scrapper --tariffs 1D --months 1 2 --dry-run
```

- Flags: `--tariffs` (default `1C 1D`), `--months` (default all), `--overwrite`, `--dry-run`, `--sqlite`, `--env-file` (defaults to `backend/api-cfe/.env`), `--log-level`.
- Loads env from `.env`; run from the host with `DB_HOST=127.0.0.1 DB_PORT=3307` overrides (the `.env` uses the docker-network hostname). PyMySQL is used locally via `pymysql.install_as_MySQLdb()`; the Docker image uses `mysqlclient`.
- Season per month follows the calculator's summer window: months 4–9 → `verano`, else `fuera de verano`.
- Stores monthly limits as scraped; one `TariffVersion` + ordered `TariffRange`s per (tariff, year, month), committed atomically per combo. Idempotent; `--overwrite` deletes and recreates the ranges of existing combos.
- Pre-change safety: dump the DB first (`db/backups/`).

## Backup & Restore

Database backup and restore scripts are in `scripts/`:

### Backup

`scripts/backup_db.sh` creates a gzipped MariaDB dump, stores it in `./backups/`, and optionally uploads to Backblaze B2 via `rclone`.

```bash
./scripts/backup_db.sh [backup_dir] [retention_days]
```

- Default backup directory: `./backups/`
- Default retention: 30 days
- Uploads to B2 bucket/prefix configured in `.env` (`BACK_BLAZE_BUCKET`, `BACK_BLAZE_DIR`)
- Gracefully skips cloud upload if `rclone` not installed or B2 credentials missing

**Cron setup** (daily at 02:00):

```bash
./scripts/install-cron.sh          # install cron entry
./scripts/install-cron.sh --remove # remove cron entry
```

### Restore

`scripts/restore_db.sh` restores from a gzipped backup file. **This is destructive** — it drops and recreates the database.

```bash
./scripts/restore_db.sh /path/to/backup.sql.gz
```

- Stops the `api` container during restore
- Prompts for confirmation before proceeding
- Restarts the `api` container and waits for health check

### Environment Variables

Add to `.env` for cloud backup:

| Variable | Description |
|---|---|
| `BACK_BLAZE_KEY_ID` | Backblaze B2 application key ID |
| `BACK_BLAZE_SECRET` | Backblaze B2 application key secret |
| `BACK_BLAZE_BUCKET` | B2 bucket name (default: `lmex-backups-db`) |
| `BACK_BLAZE_DIR` | Folder/prefix inside the bucket (default: `api-cfe-db`) |

## Common Tasks

### Adding a New Endpoint

1. Create route handler in `app/routes/<entity>.py`
2. Add Pydantic serializer in `model/<entity>_serializers.py` (or `model/dashboard_serializers.py` for dashboard responses)
3. Register router in `app/routes/api.py`
4. Add repository methods in `app/db/repositories/<entity>_repository.py` if needed
5. For dashboard use-cases, add business logic to `services/business/costo_total.py` / `billing_service.py` (`BillingService`) and/or `services/dashboard_service.py` (`DashboardService`) rather than querying repositories directly from the route — dashboard routes are auth-protected via `Depends(get_current_user)` and raise domain errors (`services/errors.py`) or `BillingServiceError`; routes wrap calls in `domain_errors_as_http()` (single status map, `BillingServiceError` -> 422).

### Adding a New Domain Entity

1. Define `Table` in `app/db/orm.py`
2. Create domain model in `model/domain/<entity>.py`
3. Map entity imperatively in `start_mappers()` in `app/db/orm.py`
4. Create repository class in `app/db/repositories/`
5. Add repository to `TariffConsumptionUnitofWork` in `app/db/uow.py`
6. Create Pydantic serializers in `model/`

## Agent skills

### Issue tracker

Issues and specs live in GitHub Issues (`Lmex89/api-cfe`), via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Pull requests

Always write PR bodies with the `pr` skill (Summary, Evidence, Merge Danger). Do not hand-roll the body.
