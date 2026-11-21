# E-commerce

A code challenge: an e-commerce application with a FastAPI backend (Domain-Driven Design), a React frontend and PostgreSQL, built test-first.

> **Status:** walking skeleton ([ECOM-000](tasks/ECOM-000.md)). The only feature is a **temporary weather lookup** that proves the stack works end to end. It is removed in [ECOM-009](tasks/ECOM-009.md).

The sample CSV provided with the challenge was downloaded on **2026-11-20**.

## Run it with Docker

Requirements: Docker with Compose v2.

```bash
docker compose up --build
```

This starts four containers:

| Service | URL | What it is |
|---|---|---|
| `frontend` | http://localhost:3000 | The React portal. nginx serves it and forwards `/api/` to the backend. |
| `backend` | http://localhost:8001/docs | FastAPI, with Swagger. The health check is `GET /api/v1/health`. |
| `db` | `localhost:5433` | PostgreSQL 17 (user, password and database: `ecommerce`) |
| `ci` | — | Runs every check once, then exits. Exit code 0 means everything passed. |

To run the checks again while the stack is up:

```bash
docker compose run --rm ci
```

`docker compose down` stops everything and keeps the data. `docker compose down -v` also deletes it.

## Run it natively

Requirements: Python 3.13, [uv](https://docs.astral.sh/uv/) and Node 22.

```bash
docker compose up -d db
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn --factory ecommerce.main:create_production_app --port 8001 --no-access-log
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The portal is then at http://localhost:5173. Vite forwards `/api` to the backend on port 8001.

## Tests and checks

Everything runs through one entry point, from the repository root:

```bash
python testing/run.py all
```

| Command | What it runs |
|---|---|
| `lint` | ruff, import-linter (layer rules) and the TypeScript type check |
| `nocomments` | Fails if any source or test file contains a comment |
| `tooling` | Tests for the runner and the helper scripts |
| `backend` | pytest. The integration tests need `docker compose up -d db`. |
| `frontend` | Vitest |
| `smoke` | End-to-end checks through http://localhost:3000. Needs the full stack, and makes one real call to Open-Meteo. |

All tests live in `testing/`.

## Documentation

- [Technical architecture](docs/TECHNICAL_ARCHITECTURE.md)
- [Decision journal](docs/JOURNAL.md)
- [Prompt history](docs/PROMPT_HISTORY.md): how AI was used
- [Task board](tasks/README.md)
