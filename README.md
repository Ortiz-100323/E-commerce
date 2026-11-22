# E-commerce

A small online shop with an admin area, built as a code challenge:
- **Backend:** FastAPI with Domain-Driven Design and PostgreSQL 17.
- **Frontend:** React 19 with TypeScript.
- **Running it:** everything runs in Docker with one command.

## What was built

- **Product management.** Admins create, edit, archive and restore products. Every change is kept in an append-only history: who changed what, with the values before and after.
- **CSV import with review.** Admins upload a CSV and see each row classified before anything is saved:
  - rows to create, to update, unchanged, held for review, rejected, superseded or blank;
  - zero prices, zero weights and empty fields are held for a person to correct, confirm or skip;
  - updates to existing products need confirmation;
  - invalid rows are rejected with their reasons;
  - the import is committed all or nothing.
- **Search.** The shop searches name, SKU and description, with filters (category, price range, in stock, gifts), sorting and pages.
- **Purchase with a fake payment.**
  - **Cart and prices:** the cart is priced by the server, and stock is checked before payment.
  - **Payment:** a fake card gateway approves or declines.
  - **Retries:** checkout is safe to retry and never oversells.
  - **Who can buy:** guests and customer accounts can buy.
- **Accounts.**
  - One login page for admins and customers; the account's role decides where you land.
  - Customers sign up and see their orders in **My orders**.
  - Admins create other admins, see every order, and can't buy.

## Quick start

You need Docker with Compose v2, and ports 3000, 8001 and 5433 free.

```bash
git clone https://github.com/Ortiz-100323/E-commerce.git
cd E-commerce
docker compose up --build
```

The first build takes a few minutes. On start, the backend applies the database migrations and creates the first admin. No products are created: import the sample CSV yourself (see below).

| Service | Address | What it is |
|---|---|---|
| `frontend` | http://localhost:3000 | The shop and the admin area. nginx serves the React app and forwards `/api/` to the backend. |
| `backend` | http://localhost:8001/docs | FastAPI, with Swagger. Health check: `GET /api/v1/health`. |
| `db` | `localhost:5433` | PostgreSQL 17. User, password and database: `ecommerce`. |
| `ci` | — | Runs every check once against the running stack, then exits. Exit code 0 means everything passed. |

**Admin login:** http://localhost:3000/login with `admin@example.com` / `local-admin-password-change-me`. These are public development values from `docker-compose.yml` (`ADMIN_SEED_EMAIL`, `ADMIN_SEED_PASSWORD`). Change them for anything real.

**Try it:**
1. **Admin → Import CSV:** upload [`testing/fixtures/csv/sample-products.csv`](testing/fixtures/csv/sample-products.csv). On an empty shop, it shows 84 rows to create, 6 to review and 2 rejected. Resolve the review rows, then **Commit import**.
2. **Admin → Products:** edit a product, then open its **History**.
3. **Log out and open the shop:** search, filter, and add to the cart.
4. **Log in → Create an account,** then pay with the test card `4242 4242 4242 4242`, any future expiry date and any CVC. `4000 0000 0000 0002` is always declined. The order appears in **My orders**.
5. **Log in as the admin → Admin → Orders:** the order is there.

To stop, run `docker compose down`. Add `-v` to delete the data too.

## Running without Docker

You need Python 3.13, [uv](https://docs.astral.sh/uv/) and Node 22. The database still runs in Docker.

```bash
docker compose up -d db
cd backend
uv sync
export CHECKOUT_FINGERPRINT_SECRET=local-development-checkout-secret-change-me
export ADMIN_SEED_EMAIL=admin@example.com
export ADMIN_SEED_PASSWORD=local-admin-password-change-me
uv run alembic upgrade head
uv run python -m ecommerce.identity.seed
uv run python -m ecommerce.serve
```

The database URL defaults to the compose database on `localhost:5433`.

- **The start command:** `python -m ecommerce.serve` runs the backend on http://127.0.0.1:8001. Use `--host` and `--port` to change that.
- **On Windows:** the command picks an event loop the database driver supports.
  - Plain `uvicorn` doesn't, so on Windows it can't reach the database.
  - In PowerShell, use `$env:NAME = "value"` instead of `export`.
- **If the Docker stack is also running,** stop its backend first (`docker compose stop backend`), because both use port 8001.

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

The app is then at http://localhost:5173. Vite forwards `/api` to the backend on port 8001.

## Running the tests

All tests and scripts live in [`testing/`](testing/). Everything runs through one entry point, `testing/run.py`.

**With Docker only,** while the stack is up:

```bash
docker compose run --rm ci
docker compose --profile e2e run --rm --build e2e
```

The first command runs every check below except the browser tests. The second runs the browser tests (Playwright, on a desktop and a phone). They are kept out of `docker compose up` so it never downloads a browser.

**On your machine,** from the repository root, with the backend and frontend dependencies installed as above, and `docker compose up -d db` running:

```bash
python testing/run.py all
```

| Command | What it runs | Result at delivery |
|---|---|---|
| `lint` | ruff, mypy (strict), import-linter (11 architecture contracts), the TypeScript check, Prettier and a raw-HTML check | Passing |
| `nocomments` | Fails if any source or test file contains a comment | Passing |
| `tooling` | Tests for the runner and the helper scripts | 79 tests |
| `backend` | pytest: domain, use cases, PostgreSQL integration, API and contract tests, with a 95% coverage gate on domain and application code | 1,099 tests, 99% |
| `frontend` | Vitest with Testing Library and MSW, with an 80% coverage gate | 204 tests, 96% |
| `smoke` | Live checks through http://localhost:3000. Needs the full stack. | 14 checks |
| `containers`, `images`, `docs` | Host checks: no container runs as root, the image sizes stay within budget, and every link and decision record in the README and `docs/adr` is consistent | Passing |

The browser tests (`testing/e2e/`) cover buying, importing, the product card, logins and roles: 44 tests, with 5 skipped by design because they run on one device only. GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the stack, the `ci` container, the host checks and the browser tests on every push to `main` and every pull request.

## The sample CSV

The sample CSV provided with the challenge was downloaded on **2026-11-20**.

It is kept unchanged as the golden test fixture: [`testing/fixtures/csv/sample-products.csv`](testing/fixtures/csv/sample-products.csv). On an empty catalog, the import must classify its 97 rows as follows:
- 84 to create;
- 6 to review;
- 2 rejected;
- 3 superseded;
- 2 blank;
- and 3 warnings.

## Architecture

```
browser ──▶ frontend (nginx + React) ──/api──▶ backend (FastAPI) ──▶ PostgreSQL 17

backend (one deployable, three bounded contexts)
  catalog    products, search, CSV import review, audit history
  ordering   cart quote, checkout, fake payment, orders
  identity   accounts with a role, sessions, login throttle
  shared kernel: Money, Actor, Principal, Problem Details, Unit of Work, audit log
  integration: the adapter that lets ordering read the catalog
```

- **Contexts never import each other.**
  - Ordering reads the catalog through its own port.
  - Logins reach the other contexts through an `Authenticator` port.
  - Each context is layered domain → application → API and infrastructure.
  - import-linter enforces all of this in CI.
- **One transaction per use case.** A change, its audit entries and, at checkout, the idempotency key commit or roll back together.
- **One error format:** RFC 9457 Problem Details, with field-level issues and a request id.
- **The API is on the same origin as the app.** nginx forwards `/api/` to the backend, so there is no CORS and the frontend build doesn't depend on the environment.

| Path | What it holds |
|---|---|
| [`backend/`](backend/) | The FastAPI app (`src/ecommerce/{catalog,ordering,identity,shared_kernel,integration}`) and the Alembic migrations |
| [`frontend/`](frontend/) | The React app, the nginx configuration and the security headers |
| [`testing/`](testing/) | Every test (backend, frontend, browser, tooling), the fixtures, the scripts and `run.py` |
| [`docs/`](docs/) | The architecture, the decision records, the journal and the prompt history |
| [`tasks/`](tasks/) | The ticket board, one file per ticket, and each ticket's test evidence |

Full detail is in [docs/TECHNICAL_ARCHITECTURE.md](docs/TECHNICAL_ARCHITECTURE.md).

## Decisions and alternatives

Each decision has its own record in [docs/adr](docs/adr/README.md), with its context, the alternatives discarded and its consequences.

| ADR | Decision | Main alternatives discarded |
|---|---|---|
| [0001](docs/adr/0001-modular-monolith-with-ddd.md) | Modular monolith with DDD bounded contexts, layers enforced by import-linter | A flat CRUD app; microservices |
| [0002](docs/adr/0002-fastapi-backend.md) | FastAPI, with Pydantic at the edge only | Django REST Framework; Flask |
| [0003](docs/adr/0003-react-spa.md) | React SPA with TanStack Query, react-hook-form and zod | Next.js; Redux; a UI kit |
| [0004](docs/adr/0004-postgresql-only.md) | PostgreSQL only, also for the tests | SQLite; SQLite in tests only; Testcontainers |
| [0005](docs/adr/0005-sqlalchemy-core-mapping.md) | SQLAlchemy Core with explicit mapping | ORM imperative mapping; raw SQL strings |
| [0006](docs/adr/0006-money-and-weight-as-decimal.md) | Money and weight as exact decimals (`NUMERIC`) | Integer cents; floats |
| [0007](docs/adr/0007-sku-is-the-natural-key.md) | The SKU is the natural key; names aren't unique | Unique names; editable SKUs |
| [0008](docs/adr/0008-archive-instead-of-delete.md) | Delete archives | Hard delete |
| [0009](docs/adr/0009-optimistic-locking-for-admin-edits.md) | Optimistic locking for admin edits | Last write wins; row locks held by a form |
| [0010](docs/adr/0010-search-with-ilike-and-trigrams.md) | `ILIKE` with `pg_trgm` indexes | Full-text search; Elasticsearch or Meilisearch |
| [0011](docs/adr/0011-csv-import-review-workflow.md) | CSV import as a review workflow, committed all or nothing | Partial import with a report; stateless dry run |
| [0012](docs/adr/0012-csv-issue-taxonomy.md) | Warnings, review items and errors; values never silently changed | Rounding with a warning; accepting `1,299.99` |
| [0013](docs/adr/0013-sku-identity-check.md) | An SKU that names a different product is rejected | Trusting the SKU; exact names only |
| [0014](docs/adr/0014-configurable-business-policies.md) | Business rules as configurable policies | Hard-coded rules; a rules engine |
| [0015](docs/adr/0015-gifts-are-always-free.md) | A gift if and only if the price is zero | Rejecting zero prices; paid gifts |
| [0016](docs/adr/0016-append-only-audit-trail.md) | Append-only audit trail in the same transaction | Database triggers; event sourcing; log lines |
| [0017](docs/adr/0017-checkout-and-fake-payment.md) | Server-side pricing; fake payment behind a port | Client-side totals; a "decline" switch |
| [0018](docs/adr/0018-idempotent-checkout.md) | Idempotency key claimed in the order's transaction | Server-issued keys; response-caching middleware |
| [0019](docs/adr/0019-no-overselling-row-locks.md) | Row locks in SKU order, with a timeout, one retry and a CHECK | Optimistic retries; `SERIALIZABLE`; a Redis lock |
| [0020](docs/adr/0020-problem-details-errors.md) | RFC 9457 Problem Details for every error | FastAPI's default errors; a custom envelope |
| [0021](docs/adr/0021-request-ids-and-json-logs.md) | Request IDs and JSON logs | `BaseHTTPMiddleware`; split health endpoints |
| [0022](docs/adr/0022-four-containers-and-same-origin-proxy.md) | Four containers; API on the same origin through nginx | One image for API and SPA; CORS |
| [0023](docs/adr/0023-test-first-and-one-runner.md) | Test-first; all tests in `testing/`; one runner | Tests next to the code; a Makefile; tox |
| [0024](docs/adr/0024-browser-tests-in-their-own-service.md) | Playwright in its own compose profile | Playwright in the `ci` image |
| [0025](docs/adr/0025-no-comments-in-code.md) | No comments, enforced by a check | Manual review |
| [0026](docs/adr/0026-raw-html-check-instead-of-eslint.md) | A raw-HTML check instead of ESLint (TypeScript 7) | Downgrading TypeScript; forcing peer dependencies |
| [0027](docs/adr/0027-no-authentication-and-self-declared-actor.md) | No authentication, with a self-declared actor (superseded by 0028) | HTTP Basic auth |
| [0028](docs/adr/0028-one-login-with-roles.md) | One login with a fixed role; server-side sessions | Two login systems; a JWT in local storage |
| [0029](docs/adr/0029-admins-dont-shop.md) | Admins don't shop; a read-only orders screen | Admin purchases as guest orders |
| [0030](docs/adr/0030-first-run-migrations-and-admin-only.md) | First run: migrations and the first admin, no products | Seeding the sample CSV on the first run |

Some rules belong to the business, so each one has a working default until the business answers. The questions are listed in [§11.3 of the architecture document](docs/TECHNICAL_ARCHITECTURE.md#113-questions-for-the-customer-business-stakeholder):
- are zero-price products gifts;
- is the CSV stock on hand or received;
- which duplicate row wins;
- is the store USD only;
- how long is the audit kept;
- do suppliers reuse SKUs.

Most of these defaults can be changed with the `IMPORT_*` settings.

## Out of scope

- **Real payments.** The payment is fake by design. There are no refunds, and an order's status can't be changed.
- **Account management:**
  - email confirmation;
  - password reset;
  - profile editing;
  - removing or deactivating accounts.
- **Product images as files.** A product image is an HTTPS address. Images aren't uploaded or stored.
- **Taxes, shipping, discounts and more than one currency (USD only).**
- **Stock reservations.** Stock is decreased at payment, not held while a customer checks out.
- **Production deployment:**
  - HTTPS;
  - managed secrets;
  - backups;
  - monitoring.

## Next steps

1. **A real payment provider:**
   - reserve stock with an expiry, then take payment, then confirm or release the stock;
   - give checkout a committed "in progress" state for the idempotency key, because the payment can no longer run inside one database transaction ([ADR-0018](docs/adr/0018-idempotent-checkout.md), [ADR-0019](docs/adr/0019-no-overselling-row-locks.md)).
2. **Production settings:**
   - serve over HTTPS with `SESSION_COOKIE_SECURE=true` and HSTS;
   - set real values for `ADMIN_SEED_*`, `CHECKOUT_FINGERPRINT_SECRET` (at least 32 characters) and the database password;
   - give the app a database role that can only `INSERT` and `SELECT` on `audit_log`.
3. **Order management:** status changes, cancellations and refunds, all audited.
4. **Account management:** deactivating accounts, password reset by email, and email confirmation.
5. **ESLint,** once `typescript-eslint` supports TypeScript 7 ([ADR-0026](docs/adr/0026-raw-html-check-instead-of-eslint.md)).
6. **Observability:** metrics and tracing beside the JSON logs.
7. **Answers to the business questions above,** turned into the matching policy settings.

## How AI was used

The project was built in a conversation between the developer responsible for it and Claude Code (Anthropic), acting as the engineer. Codex (OpenAI) was used for independent code reviews.

- **The developer set the direction and made the business decisions:**
  - the stack;
  - the import rules;
  - the login model;
  - the priorities;
  - what was out of scope.

  Every feature started with a plan the developer approved, and ended with the developer testing it in the running app.
- **Everything is on record:**
  - every prompt and reply, word for word, in [docs/PROMPT_HISTORY.md](docs/PROMPT_HISTORY.md);
  - every decision in [docs/JOURNAL.md](docs/JOURNAL.md);
  - every ticket and its test evidence in [tasks/](tasks/README.md).
- **Guardrails kept the AI's output in check:**
  - tests first for every ticket, covering failures, retries and stock safety;
  - CI gates on types, layering, coverage and comments;
  - browser tests with screenshots before each review.
- **Bugs are recorded, not hidden.** Those found by tests, by the developer or by the four Codex review rounds have their own journal entries.
- **No AI comments are left in the code.** The `nocomments` check fails CI if one appears ([ADR-0025](docs/adr/0025-no-comments-in-code.md)).
