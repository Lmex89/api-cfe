# api-cfe

FastAPI backend for the CFE (Comisión Federal de Electricidad) project. Provides a RESTful API for managing household electricity tariff data with JWT-based authentication.

## Features

- FastAPI application with CORS and custom exception handlers
- Modular route registration under `app/routes/api.py`
- JWT authentication with OAuth2 password flow (access + refresh tokens)
- Password hashing with `passlib[bcrypt]`
- JWT signing with `python-jose` and HS256
- Unit of Work + Repository pattern for database access
- Imperative SQLAlchemy ORM mapping with MySQL
- Docker and Docker Compose support
- CI/CD with GitHub Actions (self-hosted runner)

## Project Structure

```text
app/
  main.py              # FastAPI app entrypoint
  requirements.pip     # Python dependencies
  common/              # Shared config, logging, and API helpers
    config.py          # Environment-based configuration
    logging.py         # Loguru interceptor for stdlib logging
    services/          # Shared service dependencies (auth, API keys)
    api/errors/        # Custom exception handlers
  db/                  # ORM and persistence layer
    database.py        # SQLAlchemy engine & session factory
    orm.py             # Table definitions + imperative mapper
    uow.py             # Unit of Work with all repositories
    repositories/      # Per-entity repository classes
  model/               # Pydantic models and domain objects
    domain/            # Domain entities
    *_serializers.py   # Pydantic output serializers
    errors.py          # Custom exceptions
  routes/              # API routers (all under /api/v1 prefix)
    api.py             # Router aggregation
    auth.py            # JWT auth routes
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
      billing_service.py        # Billing cost calculation
      cfe_billing_calculator.py # CFE tier-based kWh calculator
      period_utils.py           # Billing period utilities
      tariff_calculator.py      # Tariff range application
Dockerfile
docker-compose.yaml
```

## Requirements

- Python 3.12+
- MySQL database
- Docker & Docker Compose (optional)

## Installation

```bash
cd app
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.pip
```

## Running Locally

From the `app/` directory:

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

## Docker

Build and run with Docker Compose:

```bash
docker compose up --build
```

`docker-compose.yaml` expects:

- an `.env` file for environment variables
- an external Docker network named `db-test-net`

## Configuration

Environment variables (set in `.env` or shell):

| Variable | Description |
|----------|-------------|
| `DB_HOST` | MySQL host |
| `DB_PORT` | MySQL port (default: 3306) |
| `DB_USER` | Database user |
| `DB_PSWD` | Database password |
| `DB_NAME` | Database name |
| `SECRET_KEY` | JWT signing secret |
| `LOGGING_LEVEL` | Log level (DEBUG/INFO) |
| `REGISTER_API_KEY` | API key required for user registration |

Optional variables: `TWILIO_USER_NAME`, `TWILIO_USER_PWD`, `TWILIO_FROM_NUMBER`, `TWILIO_PHONE_WHATSAPP`, `COMMON_ENCRYPT_KEY`, `COMMON_ENCRYPT_IMG_KEY`, `HSM_HOST`, `HSM_PORT`, `CURRENT_DOMAIN`.

## Authentication

The auth module lives in `app/routes/auth.py` and provides:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/register` | Create a new user (requires `REGISTER_API_KEY` header) |
| `POST` | `/api/v1/auth/login` | OAuth2 password flow – returns access + refresh tokens |
| `POST` | `/api/v1/auth/refresh` | Rotate refresh token and get new access token |
| `GET` | `/api/v1/auth/me` | Get current user info (protected) |

- JWT algorithm: HS256
- Access token expiry: 12 hours
- Refresh token expiry: 7 days
- Password hashing: bcrypt via passlib

### Login Request

Send form-encoded credentials:

```bash
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice&password=supersecret"
```

Response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

### Protected Request

Use the token in the `Authorization` header:

```bash
curl http://localhost:8080/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

### Refresh Token

```bash
curl -X POST http://localhost:8080/api/v1/auth/refresh \
  -H "Authorization: Bearer <refresh_token>"
```

## API Modules

| Module | Endpoints |
|--------|-----------|
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

- **Household** – A residential unit consuming electricity
- **Tariff** – A tariff definition (code + description)
- **TariffVersion** – A versioned tariff for a specific year/month
- **TariffRange** – Price bands within a tariff version (min/max kWh range, price per kWh)
- **MeterReading** – KWh meter readings for a household
- **BillingPeriod** – Billing period for a household (start/end dates)
- **HouseholdTariff** – Association between a household and a tariff over a date range
- **User** – Authenticated system user (username, email, role, active status)

## Architecture

### Unit of Work + Repository

All database access goes through `TariffConsumptionUnitofWork`:

```python
with TariffConsumptionUnitofWork() as uow:
    user = uow.user_repository.get_by_username(username)
    uow.commit()
```

Repositories: `HouseholdRepository`, `TariffRepository`, `MeterReadingRepository`, `BillingPeriodRepository`, `TariffVersionRepository`, `TariffRangeRepository`, `HouseholdTariffRepository`, `UserRepository`.

### Imperative ORM Mapping

SQLAlchemy mappings are done imperatively in `app/db/orm.py` via `start_mappers()`, called at app startup in `main.py`.

## Notes

- `bcrypt==4.0.1` is pinned because newer bcrypt versions are not compatible with `passlib 1.7.4`
- The ORM uses `expire_on_commit=False` to avoid lazy-load issues after commits
- The Dockerfile uses a multi-stage build with Alpine + MariaDB connector for `mysqlclient`
- Database isolation level is set to `REPEATABLE READ`
- The `EntityNotFoundException` handler returns HTTP status **420** (non-standard)

## CI/CD

Pushing to `main` triggers a GitHub Actions workflow on a self-hosted runner that builds and deploys via Docker Compose.
