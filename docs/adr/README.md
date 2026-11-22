# Architecture decision records

Each record describes one decision: its context, what was decided, the alternatives discarded and the consequences. The records are built from the decision journal, [docs/JOURNAL.md](../JOURNAL.md), and each one names the journal entries it comes from. The journal keeps the full history, including plans, bugs and housekeeping.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-modular-monolith-with-ddd.md) | A modular monolith with DDD bounded contexts and enforced layers | Accepted |
| [0002](0002-fastapi-backend.md) | FastAPI for the backend | Accepted |
| [0003](0003-react-spa.md) | A React single-page app with TanStack Query, react-hook-form and zod | Accepted |
| [0004](0004-postgresql-only.md) | PostgreSQL is the only database, in tests too | Accepted |
| [0005](0005-sqlalchemy-core-mapping.md) | Repositories on SQLAlchemy Core with explicit mapping | Accepted |
| [0006](0006-money-and-weight-as-decimal.md) | Money and weight are exact decimals, end to end | Accepted |
| [0007](0007-sku-is-the-natural-key.md) | The SKU is the natural key, and product names aren't unique | Accepted |
| [0008](0008-archive-instead-of-delete.md) | Deleting a product archives it | Accepted |
| [0009](0009-optimistic-locking-for-admin-edits.md) | Optimistic locking for admin edits | Accepted |
| [0010](0010-search-with-ilike-and-trigrams.md) | Search with `ILIKE` and `pg_trgm` indexes | Accepted |
| [0011](0011-csv-import-review-workflow.md) | The CSV import is a review workflow, committed all or nothing | Accepted |
| [0012](0012-csv-issue-taxonomy.md) | CSV issues are warnings, review items or errors, and values are never silently changed | Accepted |
| [0013](0013-sku-identity-check.md) | An existing SKU that names a different product is rejected | Accepted |
| [0014](0014-configurable-business-policies.md) | Business rules are configurable policies, with open questions for the business | Accepted |
| [0015](0015-gifts-are-always-free.md) | A product is a gift if and only if its price is zero | Accepted |
| [0016](0016-append-only-audit-trail.md) | An append-only audit trail, written in the same transaction as the change | Accepted |
| [0017](0017-checkout-and-fake-payment.md) | Checkout prices on the server, and the fake payment sits behind a port | Accepted |
| [0018](0018-idempotent-checkout.md) | Checkout is idempotent, with an `Idempotency-Key` claimed in the order's transaction | Accepted |
| [0019](0019-no-overselling-row-locks.md) | Stock never oversells: rows are locked in SKU order, with a timeout, one retry and a database guard | Accepted |
| [0020](0020-problem-details-errors.md) | One error format: RFC 9457 Problem Details, with one validation vocabulary | Accepted |
| [0021](0021-request-ids-and-json-logs.md) | Request IDs and one JSON log line per request | Accepted |
| [0022](0022-four-containers-and-same-origin-proxy.md) | Four containers with Docker Compose, and the API on the same origin through nginx | Accepted |
| [0023](0023-test-first-and-one-runner.md) | Test-first, with every test under `testing/` and one runner for local runs and CI | Accepted |
| [0024](0024-browser-tests-in-their-own-service.md) | Browser tests with Playwright, in their own compose service | Accepted |
| [0025](0025-no-comments-in-code.md) | No comments in the code, enforced by a check | Accepted |
| [0026](0026-raw-html-check-instead-of-eslint.md) | A raw-HTML check instead of ESLint, while TypeScript 7 has no ESLint support | Accepted |
| [0027](0027-no-authentication-and-self-declared-actor.md) | No authentication, with a self-declared name as the audit actor | Superseded by 0028 |
| [0028](0028-one-login-with-roles.md) | One login for admins and customers, with a fixed role and server-side sessions | Accepted |
| [0029](0029-admins-dont-shop.md) | Admins don't shop, and they see every order on a read-only screen | Accepted |
| [0030](0030-first-run-migrations-and-admin-only.md) | The first run applies migrations and seeds the first admin, but no products | Accepted |
