# scrapling-api — Agent Instructions

A Flask REST API that accepts a list of sequential scraping commands, executes them with [Scrapling](https://scrapling.readthedocs.io/), and returns ordered results — with optional Redis caching and MongoDB persistence.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests (no live services required — all I/O is mocked)
pytest
pytest -v
pytest tests/test_routes.py   # single file

# Dev server
python wsgi.py

# Docker (first run)
cp .env.example .env
docker compose up --build

# Docker (subsequent)
docker compose up
docker compose down
```

## Architecture

```
POST /api/v1/runs
    │
    ├── Pydantic v2 validation (RunRequest / AnyCommand discriminated union)
    ├── Redis cache check (keyed by SHA-256 of request body)
    ├── execute_commands() — sequential, halts on first error
    ├── MongoDB persistence (save_run)
    └── Redis cache write
```

Key files:
- [app/routes.py](app/routes.py) — all HTTP endpoints on the `api` Blueprint
- [app/schemas.py](app/schemas.py) — Pydantic v2 models; `AnyCommand` discriminated union on `"type"`
- [app/services/runner.py](app/services/runner.py) — command dispatcher, security guards, `_Context` dataclass
- [app/services/cache.py](app/services/cache.py) — Redis helpers (lazy connect, soft-fail)
- [app/services/store.py](app/services/store.py) — MongoDB helpers (lazy connect, soft-fail)
- [app/config.py](app/config.py) — all env vars with defaults
- [docs/openapi.yaml](docs/openapi.yaml) — OpenAPI spec (served at `GET /api/v1/docs`)

## Conventions

**Request validation** — Use Pydantic v2. `RunRequest.commands` is `list[AnyCommand]`, where `AnyCommand` is a discriminated union keyed on `"type"`. Add new command types by creating a new model in `schemas.py` and adding it to `AnyCommand`.

**Adding a command type** — three touch-points:
1. New model in `app/schemas.py` (add to `AnyCommand` union)
2. New handler `_run_<type>()` in `app/services/runner.py`
3. Register in `_HANDLERS` dict in `runner.py`

**Error handling** — the runner catches all exceptions per command, stores `CommandResult(status="error")`, and **halts** (no subsequent commands run). Routes never raise unhandled exceptions.

**Redis / MongoDB failures are soft** — both services log a warning and return `None`; the API continues without caching or persistence. Always null-guard before using the client.

**URL security** — every URL field on command models is validated by `_validate_url()` (only `http`/`https`, non-empty netloc). At runtime, `_check_host()` in the runner enforces `BLOCKED_HOSTS` and `ALLOWED_HOSTS` (with subdomain matching).

**Output truncation** — `_truncate()` caps strings at `MAX_OUTPUT_LENGTH` chars and lists by total character budget. Always use `_truncate()` on command output before storing it in `CommandResult`.

**Config** — all settings live in `app/config.py` as class attributes read from env vars. Tests subclass `Config` (see `tests/conftest.py`).

## Testing

All external I/O (Scrapling, Redis, MongoDB) is mocked via `unittest.mock.patch`. Tests run without live services.

- `tests/conftest.py` — `TestConfig` (cache/persist disabled), `app` and `client` fixtures
- Tests patch at the import site (e.g. `app.services.runner.StealthyFetcher`)

## Environment Variables

See [app/config.py](app/config.py) for all variables and defaults. Critical ones:

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | `change-me-in-production` | **Change in production** |
| `REDIS_URL` | `redis://localhost:6379/0` | Docker overrides to `redis://redis:6379/0` |
| `MONGO_URI` | `mongodb://localhost:27017` | Docker overrides to `mongodb://mongo:27017` |
| `ALLOWED_HOSTS` | *(empty = allow all)* | Comma-separated allowlist |
| `BLOCKED_HOSTS` | *(empty)* | Comma-separated blocklist, always enforced |
| `MAX_COMMANDS` | `20` | Max commands per request |

## Deployment

Docker deployment uses a 3-stage build (`deps` → `browsers` → `runtime`). The `api` service requires `shm_size: 2gb` for headless browser support. See [docker-compose.yml](docker-compose.yml) and [Dockerfile](Dockerfile).
