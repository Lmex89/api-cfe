# api-cfe

FastAPI backend for the CFE project. The app keeps the existing modular route layout and adds a small JWT auth demo with a login endpoint and a protected `/me` endpoint.

## Features

- FastAPI application with CORS and custom exception handlers.
- Modular route registration under `app/routes/api.py`.
- JWT authentication with OAuth2 password flow.
- Password hashing with `passlib[bcrypt]`.
- JWT signing with `python-jose` and HS256.
- Demo in-memory user store.
- Docker and Docker Compose support.

## Project structure

```text
app/
  main.py              # FastAPI app entrypoint
  requirements.pip     # Python dependencies
  common/              # Shared config, logging, and API helpers
  db/                  # ORM and persistence layer
  model/               # Pydantic models and domain objects
  routes/              # API routers
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
  services/            # Application services
Dockerfile
docker-compose.yaml
```

## Requirements

- Python 3.12+
- `fastapi`
- `uvicorn`
- `python-jose[cryptography]`
- `passlib[bcrypt]`
- `bcrypt==4.0.1`
- `python-multipart`

## Installation

```bash
cd app
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.pip
```

## Running locally

From the `app/` directory:

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

The app also works with the existing Docker setup.

## Docker

Build and run with Docker Compose:

```bash
docker compose up --build
```

`docker-compose.yaml` expects:

- an `.env` file for optional overrides
- an external Docker network named `db-test-net`

## Configuration

The existing app bootstrap uses environment variables in `app/common/config.py`:

- `DB_HOST`
- `DB_PORT`
- `DB_USER`
- `DB_PSWD`
- `DB_NAME`
- `SECRET_KEY`
- `LOGGING_LEVEL`

The auth demo module also generates its own JWT secret key at startup with Python's `secrets` module. For a real deployment, move that secret to an environment variable so tokens remain valid across restarts.

## Authentication flow

The auth demo lives in `app/routes/auth.py` and provides:

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

The OAuth2 dependency is configured with `OAuth2PasswordBearer(tokenUrl="/auth/login")` in code, while the router is mounted under the existing `/api/v1` prefix.

### Demo user

The in-memory store contains one user:

- username: `alice`
- password: `supersecret`

### Login request

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
  "token_type": "bearer"
}
```

### Protected request

Use the token in the `Authorization` header:

```bash
curl http://localhost:8080/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

Response:

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "full_name": "Alice Example"
}
```

## API modules

The current route set includes:

- auth
- billing periods
- dashboards
- households
- household tariffs
- meter readings
- tariff ranges
- tariff versions
- tariffs

Each router is registered through `app/routes/api.py`.

## Notes

- The current auth store is in memory, so users are reset when the app restarts.
- JWTs expire after 12 hours.
- `bcrypt==4.0.1` is pinned because newer bcrypt versions are not compatible with `passlib 1.7.4` in this project.
