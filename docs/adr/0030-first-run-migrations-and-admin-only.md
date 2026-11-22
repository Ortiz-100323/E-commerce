# ADR-0030: The first run applies migrations and seeds the first admin, but no products

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-22 |
| Journal | D-018 (superseded), D-060, D-117, D-122 (partly superseded), D-123, D-124 |

## Context

Anyone who clones the repository should get a working system from one `docker compose up`. One option was to also import the sample CSV on the first run, guarded so it never runs twice.

## Decision

- **On every start, the backend runs `alembic upgrade head`, then the admin seed, then the server.** Both steps are safe to repeat:
  - Alembic applies only the missing migrations;
  - the seed creates the first admin only when no admin exists.
- **No products are seeded.** Importing the sample CSV is up to the person running the app, through **Admin → Import CSV**, which also shows the review workflow.
- **This was proven from a fresh clone** in an empty folder with an empty database:
  - one `docker compose up` gave healthy services, migrations at head, one admin able to log in, and an empty shop;
  - a restart and a full `down`/`up` kept one admin;
  - the sample imported through the admin screen.

## Alternatives discarded

- **Seeding the sample on the first run, recorded in a `seed_runs` table under an advisory lock:** the owner chose to leave the import to the user.
- **Seeding with SQL in a Postgres init script:** it would bypass the import rules and the audit.
- **Deciding "already seeded" by counting products:** an admin who archives everything would get the sample back.

## Consequences

- A new install starts with an empty shop and one admin.
- The sample CSV is in the repository as the golden test fixture, `testing/fixtures/csv/sample-products.csv`.
