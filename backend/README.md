# Cadence — backend

FastAPI service for the Cadence change management system. See the [root README](../README.md) for project context.

## Requirements

- Python 3.11+
- PostgreSQL 16 (provided via `docker-compose` from the repo root)
- Redis 7 (provided via `docker-compose`)

## Local development

From the repository root, start the supporting services:

```bash
docker compose up -d postgres redis
```

Then from `backend/`:

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt

# Configure environment
cp .env.example .env
# edit .env as needed

# Application code lands in Phase 2. The server will then start with:
# uvicorn app.main:app --reload
```

## Tooling

| Tool   | Purpose            | Command                       |
| ------ | ------------------ | ----------------------------- |
| Ruff   | Linting + imports  | `ruff check .` / `ruff format .` |
| Black  | Formatting         | `black .`                     |
| Mypy   | Static type checks | `mypy app`                    |
| Pytest | Testing            | `pytest`                      |

Configuration for all four lives in `pyproject.toml`.
