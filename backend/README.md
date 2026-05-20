# Cadence — backend

FastAPI service for the Cadence change management system. See the [root README](../README.md) for project context.

## Requirements

- Python 3.11+
- PostgreSQL 16 (with `pgcrypto` and `citext` extensions)
- Redis 7 (used from Phase 6 onward — not strictly required for Phase 2 but the env config expects it)

See [`../docs/LOCAL_DEV_SETUP.md`](../docs/LOCAL_DEV_SETUP.md) for two ways to get those services running locally (Docker Compose or native install).

## Local development

```bash
# From the backend/ directory:

# 1. Create a virtual environment
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows PowerShell

# 2. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt

# 3. Configure environment
cp .env.example .env
# Optional: edit .env to point at a different DB / change the JWT secret

# 4. Run database migrations
alembic upgrade head

# 5. Seed the demo users (4 users, one per role)
python -m scripts.seed_demo_data

# 6. Start the API
uvicorn app.main:app --reload
```

The API is now live at <http://localhost:8000>. Interactive docs at <http://localhost:8000/docs>.

## Demo accounts (after running the seed script)

| Role | Email | Password |
| --- | --- | --- |
| Admin | `admin@cadence.dev` | `Cadence2026!` |
| Change Manager | `manager@cadence.dev` | `Cadence2026!` |
| Approver | `approver@cadence.dev` | `Cadence2026!` |
| Requester | `requester@cadence.dev` | `Cadence2026!` |

## Running tests

The test suite runs against a real Postgres database called `cadence_test`. Create it once:

```bash
# Using psql (assumes Postgres is running locally)
psql -U postgres -c "CREATE DATABASE cadence_test OWNER cadence;"
psql -U postgres -d cadence_test -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
psql -U postgres -d cadence_test -c "CREATE EXTENSION IF NOT EXISTS citext;"
```

Then from `backend/`:

```bash
pytest                          # full suite
pytest tests/unit               # just unit tests (fast)
pytest tests/api                # just API tests
pytest --cov=app                # with coverage
pytest -k login                 # match by name
```

## Tooling

| Tool   | Purpose            | Command                       |
| ------ | ------------------ | ----------------------------- |
| Ruff   | Linting + imports  | `ruff check .` / `ruff format .` |
| Black  | Formatting         | `black .`                     |
| Mypy   | Static type checks | `mypy app`                    |
| Pytest | Testing            | `pytest`                      |
| Alembic | DB migrations     | `alembic upgrade head` / `alembic revision --autogenerate -m "msg"` |

## Directory layout

```
backend/
├── app/
│   ├── api/v1/endpoints/   # HTTP endpoints, one file per resource
│   ├── core/               # config, security, role enum
│   ├── db/                 # SQLAlchemy base + session factory
│   ├── models/             # ORM models
│   ├── schemas/            # Pydantic DTOs
│   ├── services/           # business logic
│   └── main.py             # FastAPI app factory
├── alembic/                # database migrations
├── scripts/                # one-off scripts (seed, etc.)
└── tests/
    ├── api/                # end-to-end via TestClient
    └── unit/               # service- and util-level tests
```
