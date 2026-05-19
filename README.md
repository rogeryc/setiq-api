# setiq-api

FastAPI backend for the SETIQ platform.

## Requirements

- Python 3.12+
- A native Postgres 14+ install (`brew install postgresql@16` and `brew services start postgresql@16`)
- [dbmate](https://github.com/amacneil/dbmate) for migrations (`brew install dbmate`)
- Docker + Docker Compose for Redis + MailHog only

## Setup

```bash
# 1. Create the local DB
createdb setiq

# 2. Create a virtualenv and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Copy env template and edit DATABASE_URL with your local Postgres user
cp .env.example .env

# 4. Apply migrations (schema)
dbmate up

# 5. Create the non-superuser app role used by the API runtime (one-time)
psql -d setiq -f scripts/setup_app_role.sql

# 6. Seed minimal dev data (Thalma tenant + user)
python scripts/seed_dev.py

# 7. Start Redis + MailHog
docker compose up -d

# 8. Run the API
uvicorn setiq.main:app --reload

# 9. In a separate terminal, run the Arq worker (drains classification jobs)
arq setiq.workers.runner.WorkerSettings
```

API runs at http://localhost:8000. Health check: http://localhost:8000/health.

Local services:
- Postgres: native, `localhost:5432`, db `setiq`
- Redis: Docker, `localhost:6379`
- MailHog SMTP: Docker, `localhost:1025`, web UI: http://localhost:8025

Default seeded credentials (dev only):
- email `thalma@example.com` / password `changeme123`

## Project structure

```
src/setiq/
  main.py          # FastAPI app entrypoint
  config.py        # Settings (env-driven)
  db.py            # asyncpg pool + tenant-scoped acquire
  auth/            # JWT auth, password hashing, login/me endpoints
  tenants/         # Multi-tenant module
  ingestion/       # Channel webhook handlers
  conversations/   # Conversation state, messages
  crm/             # Contacts, leads, opportunities
  insights/        # Analytics, segmentation
  ai/              # Claude classification, generation
  workers/         # Arq background jobs

dbmate/migrations/ # Numbered .sql migration files
scripts/           # One-off setup + seed scripts
tests/             # Pytest
docs/              # Architecture + planning docs (Spanish)
```

## Tests

```bash
pytest
```

## Linting / type-checking

```bash
ruff check .
ruff format .
mypy
```
