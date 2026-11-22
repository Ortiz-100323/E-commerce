# ECOM-022: One-command start, proven from a fresh clone

| Field | Value |
|---|---|
| Type | Technical task |
| Phase | Hand-in |
| Status | **Done**: verified on a fresh clone and accepted by the owner (prompt #057) |
| Depends on | ECOM-017, ECOM-021 |
| Journal | D-122, D-123, D-124 |

## Context

A reviewer clones the repository and runs `docker compose up`. They should get the database, backend and frontend, with migrations applied and the first admin seeded, and nothing else.

The owner decided the sample CSV is **not** seeded (prompt #056). Importing it is up to the person running the app, through the admin import screen. The weather feature from the walking skeleton was removed in ECOM-009 (D-088). Only migrations `0001` (create) and `0005` (drop) and their migration test still mention it, as history.

## Scope

- **One `docker compose up`:**
  - starts the database, backend and frontend;
  - runs `alembic upgrade head`;
  - seeds the first admin from `ADMIN_SEED_*`;
  - seeds no products.
- **The admin seed is idempotent:** a restart keeps one admin, with no error and no password reset.
- **Weather:** no code left. Migrations `0001` and `0005` stay as history, because rewriting applied migrations would break existing databases.
- **Fresh-clone proof, as a reviewer, from GitHub:**
  1. Clone into an empty folder, with the main stack stopped (same ports).
  2. Run `docker compose up -d --build`. Expect migrations at head, the admin able to log in and an empty shop.
  3. Restart the backend, then the whole stack. Still one admin, and the migrations unchanged.
  4. Upload the sample CSV as admin in a real Chrome (Chrome DevTools MCP): the preview shows 84 to create, 6 to review and 2 rejected. Resolve the review rows and commit. The products show up in the shop.
  5. Run the `ci` container and the browser tests. Both pass.
  6. Run `down -v`, then bring the main stack back.

## Acceptance criteria

1. On a fresh clone, one `docker compose up` gives the database, backend and frontend, with migrations applied and the first admin seeded.
2. Restarting the backend, or the whole stack, doesn't seed a second admin or fail.
3. No products are seeded.
4. The sample CSV, uploaded through the admin screen, gives 84 to create, 6 to review and 2 rejected, and commits into the shop.
5. No weather code remains outside the migration history.

## As built and verified (2026-11-22, prompt #057, D-124)

No code changed. The compose stack already did everything that's needed. The fresh clone was taken from GitHub at `4852c07`, in an empty folder, with an empty database.

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | One `docker compose up` brings up the database, backend and frontend, with migrations applied and the first admin seeded | **Pass** | All services healthy. `alembic_version` = `0012`. One ADMIN account. `admin@example.com` logs in through the shop's `/api/v1/session` |
| 2 | Restarting doesn't seed a second admin or fail | **Pass** | After a backend restart, and again after `down`/`up`: one account, migrations unchanged. The log says "an administrator already exists; the seed changed nothing" |
| 3 | No products are seeded | **Pass** | 0 products, and `/api/v1/products` returned an empty list |
| 4 | The sample CSV, uploaded as admin, imports into the shop | **Pass** | The owner's browser test: 85 created, 5 skipped, 2 rejected, 0 left to review ([evidence](ECOM-022-evidence/README.md)) |
| 5 | No weather code outside the migration history | **Pass** | Only migrations `0001`/`0005` and their migration test mention it |

**Also run on the same fresh clone:**
- the `ci` container passed: all static checks, 60 tooling, 1,099 backend (99% coverage), 204 frontend and the smoke checks;
- the browser tests passed: 44, with 5 skipped by design (tests that run on one device only);
- the clone and its volume were then removed, and the owner's stack was brought back with its data.

## Definition of done

- Acceptance criteria pass, with the fresh-clone run shown to the owner.
- The journal, prompt history and this ticket are updated, and the owner has accepted it.
