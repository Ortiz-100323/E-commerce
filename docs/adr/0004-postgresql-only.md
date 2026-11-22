# ADR-0004: PostgreSQL is the only database, in tests too

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-008 (superseded), D-025, D-057, D-061 |

## Context

The challenge asks for a local database, SQL or NoSQL. The first plan was SQLite inside the app container. The checkout needs row locks, money needs an exact decimal type, and search needs indexes that work for partial words.

## Decision

- **PostgreSQL 17** runs as the `db` service in Docker Compose, with a named volume.
- **The app uses SQLAlchemy 2 (async) with psycopg 3.** The schema is managed by Alembic migrations, which run when the backend starts.
- **Integration and API tests run against real PostgreSQL:** the `ecommerce_test` database on the same compose service.
  - It is migrated once per test session, and each test truncates the tables it uses.
  - The race tests use separate connections, as real buyers would.

## Alternatives discarded

- **SQLite** (the first proposal, D-008): no row locks, no exact `NUMERIC`, no trigram search.
- **SQLite in tests and PostgreSQL in production.** The differences between the two databases would hide bugs exactly where the risk is: `FOR UPDATE`, CHECK constraints, `pg_trgm` and the audit trigger.
- **Testcontainers for tests.** A fresh database per run, but the `ci` container would need the host's Docker socket, which gives it root-level control of the host.
- **A NoSQL store.** Weak transactional guarantees for stock changes.
- **PostgreSQL inside the app image.** Two processes under a supervisor in one container is an anti-pattern.

## Consequences

- Docker must be running for the backend tests (`docker compose up -d db`).
- Two test runs at the same time against the same database would interfere. That doesn't happen in this workflow.
