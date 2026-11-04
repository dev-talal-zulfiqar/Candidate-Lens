# CandidateLens

CandidateLens is an AI-assisted hiring workspace that helps hiring managers
evaluate engineering resumes against a job description, with evidence-grounded
scoring and a human always in control of the final decision.

This repository is being built incrementally. So far: a React/TypeScript
frontend, a FastAPI backend with a health check, a PostgreSQL database wired
up via Docker Compose, and the full domain schema (jobs, requirements,
candidates, resumes, upload batches, applications, evaluations, requirement
results) managed through Alembic migrations. No job/resume/candidate product
features exist yet — those arrive in later milestones.

## Project structure

```text
candidate-lens/
├── frontend/   React + TypeScript + Vite + Tailwind CSS
├── backend/    FastAPI + SQLAlchemy + Alembic (Python 3.12)
│   ├── app/models/     SQLAlchemy domain models
│   └── alembic/         Database migrations
├── compose.yaml  Local PostgreSQL via Docker Compose
└── .env.example
```

## Prerequisites

- Node.js 20+ and npm
- Python 3.12+
- Docker and Docker Compose (for local PostgreSQL)

## 1. Start PostgreSQL

```bash
cp .env.example .env
docker compose up -d
```

This starts a `postgres:16-alpine` container on `localhost:5432` with the
credentials defined in `.env.example`.

## 2. Run the backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Verify it's running:

```bash
curl http://localhost:8000/api/health
# {"status":"ok","database":"ok"}
```

If PostgreSQL isn't reachable, `database` reports `"error"` instead of
failing the whole request — the backend distinguishes "the API is up" from
"the database is reachable."

Backend configuration is read from environment variables (see
`backend/app/core/config.py` and the root `.env.example`). Lint with
`ruff check app tests`.

The domain schema (`backend/app/models/`) is managed entirely through Alembic
migrations in `backend/alembic/versions/` — the app never creates tables on
startup. Model integration tests run against a separate, isolated database:

```bash
createdb -O candidatelens candidatelens_test   # one-time setup
pytest
```

Tests apply migrations to `candidatelens_test` automatically and roll back
every test's changes, so they never touch the dev database and never require
real AI provider credentials.

## 3. Run the frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open the printed local URL (default `http://localhost:5173`). The app shell
shows a live connectivity badge confirming it can reach the backend's health
endpoint, read from `VITE_API_BASE_URL`.

Lint with `npm run lint`; format with `npm run format`; type-check and
production-build with `npm run build`.

## Current status

Monorepo scaffolding, a backend health endpoint, a frontend shell, and the
full PostgreSQL domain schema (via SQLAlchemy models + Alembic migrations)
are in place. No job/resume/candidate product features, file uploads, or AI
integration exist yet — those arrive in later milestones.
