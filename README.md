# setiq-api

FastAPI backend for the SETIQ platform.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management
- A native Postgres 14+ install (`brew install postgresql@16` and `brew services start postgresql@16`)
- [dbmate](https://github.com/amacneil/dbmate) for migrations (`brew install dbmate`)
- Docker + Docker Compose for Redis + MailHog only

## Setup

```bash
# 1. Create the local DB
createdb setiq

# 2. Install Python dependencies
uv sync

# 3. Copy env template and edit DATABASE_URL with your local Postgres user
cp .env.example .env

# 4. Apply migrations (no-op until migration #1 is written)
dbmate up

# 5. Start Redis + MailHog
docker compose up -d

# 6. Run the API
uv run uvicorn setiq.main:app --reload
```

API runs at http://localhost:8000. Health check: http://localhost:8000/health.

Local services:
- Postgres: native, `localhost:5432`, db `setiq`
- Redis: Docker, `localhost:6379`
- MailHog SMTP: Docker, `localhost:1025`, web UI: http://localhost:8025

## Project structure

```
src/setiq/
  main.py          # FastAPI app entrypoint
  config.py        # Settings (env-driven)
  db.py            # asyncpg pool
  auth/            # JWT auth, users, RBAC
  tenants/         # Multi-tenant module
  ingestion/       # Channel webhook handlers
  conversations/   # Conversation state, messages
  crm/             # Contacts, leads, opportunities
  insights/        # Analytics, segmentation
  ai/              # Claude classification, generation
  workers/         # Arq background jobs

dbmate/migrations/ # Numbered .sql migration files
tests/             # Pytest
```

## Tests

```bash
uv run pytest
```

## Linting / type-checking

```bash
uv run ruff check .
uv run ruff format .
uv run mypy
```
