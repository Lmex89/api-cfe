# Backend coding standards

Single reference for coding standards in `backend/api-cfe`. Scope: this backend only (not the frontend, scraper or database service). Architecture rationale lives in [`docs/adr/`](adr/), domain vocabulary in [`GLOSSARY.md`](../GLOSSARY.md), operational instructions in [`AGENTS.md`](../AGENTS.md).

## How to read this document

- **Required**: expected of all new or changed code. Some are machine-enforced (marked *enforced*), the rest are checked in review.
- **Recommended**: preferred; deviate when there is a reason.
- **Current state**: how the code actually is today. The codebase is not uniform; do not assume every file follows these rules.

## Gradual adoption

Standards apply to code you add or change. Do not rewrite or reformat unrelated code to comply. Legacy violations are grandfathered by the [baseline](#baseline); fixing one is welcome but optional, and must come with the matching baseline cleanup.

## Architecture

- **Required**: all database access goes through the Unit of Work (`TariffConsumptionUnitofWork`) and its repositories. Never create raw sessions in route handlers.
  - *Current state*: `routes/auth.py` and `routes/dashboards.py` open the UoW directly; other routes delegate to `services/*_handler.py`. Do not copy the direct usage for new business logic.
- **Required**: put new business logic in `services/` (dashboard use-cases in `services/business/` and `services/dashboard_service.py`), not in route handlers. Routes parse the request, call a service, and shape the response.
- **Required**: new endpoints are registered in `app/routes/api.py` under the `/api/v1` prefix.
- **Required**: response validation uses Pydantic serializers in `model/` (`*_serializers.py`; dashboards in `model/dashboard_serializers.py`).
- **Required**: domain entities are plain Python classes in `model/domain/`, mapped imperatively. A new entity needs a `Table` plus a mapping in `start_mappers()` (`db/orm.py`), a repository in `db/repositories/`, and a field on the UoW in `db/uow.py`. See [ADR 0001](adr/0001-imperative-sqlalchemy-mapping.md).
- **Required**: services raise domain errors (`services/errors.py`, `CostoTotalError`, `BillingServiceError`); only the route layer maps them to HTTP. Dashboard routes use the single status map `HTTP_STATUS_BY_ERROR` via `domain_errors_as_http`.
- **Recommended**: apply SOLID as design guidance, not a mandate for extra classes. Examples in this repo: `CostoTotal` only prices a Consumo; `BillingService` orchestrates; the tariff catalog seam (`UowTariffCatalog`, `InMemoryTariffCatalog`, `CachedTariffCatalog`) lets pricing swap data sources, and implementations must keep identical lookup semantics (ordering, missing values). Keep interfaces narrow. Some services still build concrete dependencies; dependency inversion is a direction, not a universal fact.

## Naming, formatting and imports

- **Required**: follow PEP 8 as general guidance; four-space indentation; `snake_case` functions/modules, `PascalCase` classes.
- **Required** (*enforced*, `ruff format` / `ruff check` rule `I`): imports in three groups, separated by blank lines: standard library, third-party, local.
- **Line width**: Ruff's default is 88 columns. It is a formatter default, not an absolute ban on longer lines: the formatter cannot split long strings, and lint rule `E501` is part of the selected `E` set, so long lines that cannot be wrapped need a justified exception. Do not reformat unrelated code just to rewrap it.
- **Recommended**: use domain vocabulary from `GLOSSARY.md` in names and test names. The glossary is Spanish (Vivienda, Lectura, Consumo, Tarifa, Rango); code uses the English entity names (`Household`, `MeterReading`, ...). Existing identifiers with typos (`url_shotner_repository`, `total_cost_witout_taxes`) are intentional or frontend-coupled: do not rename without coordinating.

## Documentation

- **Required** (*enforced*, Ruff `D`, Google convention): public modules, classes and functions have English Google-style docstrings. Include only the sections that apply (`Args`, `Returns`, `Raises`); explain intent, not mechanics. Tests and `__init__.py` are exempt. Ruff cannot check that a docstring is English.

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
```

## Security, validation and error handling

- **Required**: preserve existing trust boundaries. Protected routes keep `Depends(get_current_user)` (all dashboard routes); registration keeps the `REGISTER_API_KEY` check; never log secrets or tokens.
- **Required**: validate input at the boundary (Pydantic models, explicit filter checks) and keep existing validation when moving code.
- **Required**: preserve API behavior unless the change is the point. In particular `EntityNotFoundException` returns HTTP **420** (the frontend depends on it), and dashboard errors keep the status map: 400 invalid filter/ownership, 404 missing household/billing period, 422 `BillingServiceError`.
- **Required**: `bcrypt` stays pinned to 4.0.1 (incompatible with `passlib` 1.7.4 otherwise).
- **Required**: use Loguru for logging (stdlib logging is intercepted).
- **Recommended**: tariff data stores monthly limits; the bimonthly doubling lives in the calculator (see [ADR 0003](adr/0003-tiered-pricing-incremental.md) and `AGENTS.md` gotchas).

## Testing

- **Required**: stdlib `unittest` only (no pytest), tests under `app/tests/`; no MySQL needed.
- Run: `cd app && .venv/bin/python -m unittest discover -s tests -v`.
- Route tests: build `FakeUoW()`, seed repos, then `with make_client(uow) as client:` (see `app/tests/fakes.py`). Pass `user=None` to exercise real auth.
- **Recommended**: name tests with `GLOSSARY.md` vocabulary. Tests pin current behavior; bugs found are reported (e.g. as issues), not fixed inside a test change.
- The scraper-feed tests read `scrapper/data/cfe_tarifas.db` from the monorepo layout and fail in a standalone checkout or worktree without it; report that rather than hiding it.

## Automated checks

Configuration: `pyproject.toml`, `.pre-commit-config.yaml`, `scripts/check_standards.py`, `scripts/standards-baseline.json`, `app/requirements-dev.pip`. See [ADR 0004](adr/0004-python-standards.md) for the trade-offs.

| Check | What it enforces |
|---|---|
| `ruff check` | Rules `E`, `F`, `I`, `D` (Google convention), `C90` (max complexity 10), `PLR0913` (max 5 arguments). Tests and `__init__.py` are exempt from `D`. |
| `ruff format` | Formatting, target Python 3.12. |
| `mypy` | Strict mode, missing imports reported. Runs in a pre-commit-managed environment with pinned analysis dependencies, on tracked files in an isolated copy, even for deletion-only commits. Unresolved imports still type as `Any`. |

Setup and commands, from the repository root with Python 3.12:

```bash
python3.12 -m venv app/.venv  # if it does not already exist
app/.venv/bin/python -m pip install -r app/requirements-dev.pip
source app/.venv/bin/activate
pre-commit install
pre-commit run ruff-check --all-files
pre-commit run ruff-format --all-files
pre-commit run mypy --all-files
pre-commit run --all-files
```

Raw `ruff check`, `ruff format --check` and `mypy app` also report legacy violations; use the hooks for baseline-aware results.

### What is not machine-checked

SOLID soundness, English docstrings, where business logic lives, security and API compatibility are human-review items.

### Baseline

`scripts/standards-baseline.json` freezes legacy diagnostics so only new violations fail.

- Lint and mypy diagnostics are identified by path, rule/message and source line (D100 by path and rule). Formatting edits are identified by their original and formatted text. Occurrence counts stop an extra identical violation from hiding.
- Changing a line that carries a legacy diagnostic, or its formatting block, can require cleaning it up.
- **Never regenerate or expand the baseline to fit new violations.** Fixing a legacy issue: remove its entry (or lower its count), then run `pre-commit run --all-files` and the unit tests.
- **Renames**: the diagnostic path changes. Either fix the file's legacy violations or move only that file's entries to the new path, reviewing old vs. new counts and any changed mypy messages.
- Limitation: replacing a legacy violation with an identical one in the same file leaves the count unchanged and is not detected; review such changes by hand.
- Avoid broad formatting or unrelated rewrites.

### Not CI enforcement

The checks are local pre-commit hooks and can be bypassed (`--no-verify`, not installing hooks). The only CI workflow deploys on push to `main`; it does not run these checks.
