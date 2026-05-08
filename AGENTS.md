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
      meter_reading_repository.py
      tariff_range_repository.py
      tariff_repository.py
      tariff_version_repository.py
      url_repository.py
      user_repository.py
  model/               # Pydantic serializers & domain models
    domain/            # Domain entities (BillingPeriod, Household, Tariff, User, etc.)
    auth.py            # Auth-related Pydantic models
    *_serializers.py   # Pydantic output serializers per domain
    errors.py          # EntityNotFoundException + 420 handler
  routes/              # API routers (all under /api/v1 prefix)
    api.py             # Router aggregation
    auth.py            # JWT auth (login, register, refresh, /me)
    billing_periods.py
    dashboards.py
    households.py
    household_tariffs.py
    meter_readings.py
    tariff_ranges.py
    tariff_versions.py
    tariffs.py
  services/            # Application/business logic handlers
    business/          # Business-specific calculation services
      billing_service.py        # Orchestrates billing cost calculation for a period
      cfe_billing_calculator.py # CFE tier-based kWh cost calculator
      period_utils.py           # Billing period date/segment utilities
      tariff_calculator.py      # Applies tariff ranges to consumption data
    *_handler.py       # CRUD/service methods per domain
    tariff_version_normalizer.py
```

## Key Architectural Patterns

### Unit of Work + Repository

All database access goes through `TariffConsumptionUnitofWork`, which acts as a context manager aggregating multiple repositories:

```python
with TariffConsumptionUnitofWork() as uow:
    user = uow.user_repository.get_by_username(username)
    uow.commit()
```

Repositories include: `HouseholdRepository`, `TariffRepository`, `MeterReadingRepository`, `BillingPeriodRepository`, `TariffVersionRepository`, `TariffRangeRepository`, `HouseholdTariffRepository`, `UserRepository`.

### Imperative ORM Mapping

SQLAlchemy mappings are done imperatively in `db/orm.py` via `start_mappers()`, called at app startup in `main.py`. Tables are defined using SQLAlchemy Core `Table` constructs, then mapped to domain classes.

### Router Registration

All routers are defined in `app/routes/api.py` under the `/api/v1` prefix. New routes must be imported and included there.

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
| Dashboards | `GET /dashboards/summary`, `GET /dashboards/consumption` |

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

## Notable Gotchas

- `bcrypt==4.0.1` is pinned because newer versions are incompatible with `passlib 1.7.4`
- The ORM uses `expire_on_commit=False` to avoid lazy-load issues after commits
- The Dockerfile uses a multi-stage build with Alpine + MariaDB connector for `mysqlclient`
- Database isolation level is set to `REPEATABLE READ`
- The `EntityNotFoundException` handler returns HTTP status **420** (non-standard)



## Working Rules

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

- No test framework is currently configured in the project.
- Manual testing is done via curl or API clients like Postman/Insomnia.
- Future improvements should include pytest integration.

## Common Tasks

### Adding a New Endpoint

1. Create route handler in `app/routes/<entity>.py`
2. Add Pydantic serializer in `model/<entity>_serializers.py`
3. Register router in `app/routes/api.py`
4. Add repository methods in `app/db/repositories/<entity>_repository.py` if needed

### Adding a New Domain Entity

1. Define `Table` in `app/db/orm.py`
2. Create domain model in `model/domain/<entity>.py`
3. Map entity imperatively in `start_mappers()` in `app/db/orm.py`
4. Create repository class in `app/db/repositories/`
5. Add repository to `TariffConsumptionUnitofWork` in `app/db/uow.py`
6. Create Pydantic serializers in `model/`
