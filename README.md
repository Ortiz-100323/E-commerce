# E-commerce

A small online shop, built as a code challenge to an enterprise standard:

- **Backend:** FastAPI with Domain-Driven Design (three bounded contexts behind strict layers) and PostgreSQL 17.
- **Frontend:** React 19 and TypeScript.
- **Everything runs in Docker with one command.** The work was done test-first, with every decision recorded.

**What you can do with it:**
- **Admins** manage products (with a full audit history) and import products from CSV through a review step that catches bad rows. They create other admins and see every order.
- **Customers** search the shop, buy with a fake card, create an account and find their orders in **My orders**. Guests can buy too.
- **One login page** serves both: the account's role decides where you land, and customers can never reach the admin side.

The sample CSV provided with the challenge was downloaded on **2026-11-20**. It is kept as the golden test fixture: [`testing/fixtures/csv/sample-products.csv`](testing/fixtures/csv/sample-products.csv).

## Run it with Docker

Requirements: Docker with Compose v2. Ports 3000, 8001 and 5433 must be free.

```bash
git clone https://github.com/Ortiz-100323/E-commerce.git
cd E-commerce
docker compose up --build
```

The first build takes a few minutes. Compose starts four containers:

| Service | URL | What it is |
|---|---|---|
| `frontend` | http://localhost:3000 | The shop and the admin area. nginx serves the React app and forwards `/api/` to the backend on the same origin. |
| `backend` | http://localhost:8001/docs | FastAPI, with Swagger. It migrates the database and creates the first admin on start. The health check is `GET /api/v1/health`. |
| `db` | `localhost:5433` | PostgreSQL 17 (user, password and database: `ecommerce`) |
| `ci` | — | Runs every check once against the running stack (lint, tests, smoke checks), then exits. Exit code 0 means everything passed. |

**Log in as the admin** at http://localhost:3000/login with `admin@example.com` / `local-admin-password-change-me`. These are public development values from `docker-compose.yml` (`ADMIN_SEED_EMAIL`, `ADMIN_SEED_PASSWORD`). Change them for anything real; see [Before a real deployment](#before-a-real-deployment).

Other commands:
- Run the checks again: `docker compose run --rm ci` (`echo $?` prints 0 when all passed).
- Run the browser tests: `docker compose --profile e2e run --rm --build e2e`. These are Playwright, on a desktop and a phone; they are kept out of the default run so `docker compose up` never downloads a browser.
- Stop everything and keep the data: `docker compose down`. Add `-v` to delete the data too.

### A five-minute tour

1. **Admin → Import CSV:** upload the sample file.
   - Rows with problems are held for review: a zero price can be confirmed as a gift; empty fields can be completed; an SKU that names a different product is rejected.
   - Fix or skip them, then **Commit import**.
2. **Admin → Products:** edit a product, then open its **History** to see who changed what, before and after.
3. **Log out, open the shop:** search, filter, add to the cart.
4. **Log in → Create an account**, then pay with the test card `4242 4242 4242 4242`. Any future expiry date and any CVC work.
   - `4000 0000 0000 0002` is always declined.
   - The order appears in **My orders**.
5. **Log in as the admin → Admin → Orders:** the order is there, marked **Customer account**.

## Run it natively

Requirements: Python 3.13, [uv](https://docs.astral.sh/uv/) and Node 22. The database still runs in Docker.

```bash
docker compose up -d db
cd backend
uv sync
export CHECKOUT_FINGERPRINT_SECRET=local-development-checkout-secret-change-me
export ADMIN_SEED_EMAIL=admin@example.com
export ADMIN_SEED_PASSWORD=local-admin-password-change-me
uv run alembic upgrade head
uv run python -m ecommerce.identity.seed
uv run uvicorn --factory ecommerce.main:create_production_app --port 8001 --no-access-log
```

The database URL defaults to the compose database on `localhost:5433`. On Windows PowerShell, use `$env:NAME = "value"` instead of `export`.

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

The app is then at http://localhost:5173. Vite forwards `/api` to the backend on port 8001.

## Tests and checks

All tests and scripts live in [`testing/`](testing/), and everything runs through one entry point, from the repository root:

```bash
python testing/run.py all
```

| Command | What it runs | At delivery |
|---|---|---|
| `lint` | ruff, mypy (strict), import-linter (11 architecture contracts), the TypeScript type check, Prettier and a raw-HTML check | Passing |
| `nocomments` | Fails if any source or test file contains a comment (challenge rule CC-10) | Passing |
| `tooling` | Tests for the runner and the helper scripts | 60 tests |
| `backend` | pytest: domain, use cases, PostgreSQL integration, the API and contract tests. Needs `docker compose up -d db`. 95% coverage gate on the domain and application code. | 1,099 tests, 99% |
| `frontend` | Vitest with Testing Library and MSW; 80% coverage gate | 204 tests, 96% |
| `smoke` | Live checks through http://localhost:3000 (logins, the import upload limit, security headers, caching). Needs the full stack. | 14 checks |
| `containers`, `images` | Host checks: no container runs as root; the image sizes stay within budget | Passing |

The browser tests (`testing/e2e/`, Playwright 1.65.0) cover buying, importing, the product card, logins and roles, on a desktop and a phone: 44 tests, 5 skipped by design. GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the stack, the `ci` container, the host checks and the browser tests on every pull request.

## Architecture in one page

```
frontend (React SPA, nginx) ──/api──▶ backend (FastAPI) ──▶ PostgreSQL 17
                                        │
     ┌──────────────────────────────────┼──────────────────────────────┐
     │ catalog                          │ ordering                     │ identity
     │ products, search, audit,         │ cart quote, checkout,        │ accounts with a role,
     │ CSV import review                │ fake payment, orders         │ sessions, login throttle
     └──────────────┬───────────────────┴──────────────┬───────────────┴──────┬───────
                    └──────────── shared kernel: Money, Actor, Principal, ──────┘
                                  Problem Details, unit of work, audit log
```

- **Bounded contexts never import one another.** Ordering reaches the catalog only through an adapter behind a port, and logins reach the other contexts only through an `Authenticator` port in the shared kernel. Each context is layered domain → application → API and infrastructure. All of this is enforced by import-linter in CI.
- **Errors use one format,** RFC 9457 Problem Details, with field-level issues and a request id.
- **Every product change goes into an append-only audit log,** written in the same transaction, with the admin who made it.
- **Checkout is safe to retry and never oversells:**
  - an `Idempotency-Key` (with an HMAC fingerprint of the request) makes retries safe;
  - product rows are locked in SKU order with a lock timeout and one deadlock retry;
  - a database check means stock can never go below zero.
- **Logins:**
  - server-side sessions behind an `HttpOnly; SameSite=Strict` cookie;
  - scrypt password hashes from the standard library;
  - 5 failed attempts per email in 15 minutes lock that email;
  - a same-site check on every change;
  - the role is read from the database on every request.

Full detail: [docs/TECHNICAL_ARCHITECTURE.md](docs/TECHNICAL_ARCHITECTURE.md).

## Key decisions and the alternatives considered

Every decision, with its context and the alternatives rejected, is in [docs/JOURNAL.md](docs/JOURNAL.md) (D-001 to D-120). The main ones:

| Decision | Why | Alternatives considered | Journal |
|---|---|---|---|
| FastAPI with DDD and strict layering, enforced by import-linter | Business rules stay testable without a web framework or database | A flat CRUD app (rejected: the import and checkout rules are real domain logic) | D-001, D-002 |
| PostgreSQL only, also for the tests | Row locks, `NUMERIC` money, trigram search and the same engine in tests and production | SQLite (first choice, dropped for locking and search) | D-008, D-025 |
| The CSV import is a **review workflow**: preview, decide, commit all or nothing | The sample has zero prices, empty fields and SKUs that name a different product; these need a person, not a silent rule | Partial imports with a per-row report (the first idea) | D-030 to D-034, D-048 to D-050 |
| Business rules are **configurable policies** with safe defaults | The answers belong to the business (see the questions below) | Hard-coded rules | D-034 |
| Checkout: idempotency key, rows locked in SKU order, lock timeout and one retry | Double clicks and lost connections never charge twice; concurrent buyers never oversell | Optimistic stock checks only (rejected: a race can oversell) | D-043 to D-045, D-096 |
| One error format, RFC 9457 Problem Details | Every client handles errors one way | Ad-hoc error bodies | D-046, D-047 |
| One login for admins and customers, with a fixed role per account and server-side sessions | Simple for users; a role can't be changed by anything the browser sends; logging out ends the session at once | Two login systems; JWT in local storage (readable by scripts, hard to revoke); HTTP Basic | D-114 to D-117 |
| Admins don't shop; they see every order | Keeps the two roles fully separate | Admin purchases as guest orders (the first choice, replaced after the owner's test) | D-118, D-119 |
| Four containers, including a `ci` container that runs every check | The reviewer can verify everything with Docker alone | One image serving API and SPA (the first plan) | D-053, D-055 |
| No comments in code, enforced by a script | Challenge rule CC-10, verified on every run | A manual review | D-019 |
| Browser tests in their own compose profile | `docker compose up` stays light; CI caches the browser | Playwright in the `ci` image | D-104 |

## The challenge rules and where each is met

| Rule | Requirement | Where it is met |
|---|---|---|
| CC-01 | A local database | PostgreSQL 17 in the `db` container; SQLAlchemy and 12 Alembic migrations |
| CC-02 | CRUD for products | `/api/v1/products` and Admin → Products, with archive and restore instead of deletion, and a full history |
| CC-03 | Import products from CSV | `/api/v1/imports`, and Admin → Import CSV with review, corrections, confirmations and an all-or-nothing commit |
| CC-04 | Use the sample CSV and state the download date | **2026-11-20** (above); the sample is the golden test fixture |
| CC-05 | Search for products | `GET /api/v1/products?q=…` with filters, sorting and pages; the shop's search panel |
| CC-06 | Purchase, with a fake payment | The `ordering` context, with a `PaymentGateway` port and a `FakePaymentGateway`; test cards above |
| CC-07 | A UI for CRUD, search and purchase | The React app: shop, cart, checkout, My orders and the admin area |
| CC-08 | Runnable as Docker containers | `docker compose up --build` |
| CC-09 | The README documents decisions, approach and alternatives | This README, and [docs/JOURNAL.md](docs/JOURNAL.md) |
| CC-10 | Comments removed from the code | `python testing/run.py nocomments`, run in CI |
| CC-11 | Delivered in a GitHub repository | `github.com/Ortiz-100323/E-commerce` |
| CC-12 | Instructions to run locally | [Run it with Docker](#run-it-with-docker) and [Run it natively](#run-it-natively) |
| CC-13 | Enterprise grade, and asking the right questions | The architecture, test-first development and CI gates above; the questions below |

## Questions we would ask the business

Each has a working default, and most are configurable (`IMPORT_*` settings):

| ID | Question | Default until answered |
|---|---|---|
| CQ-01 | Are zero-price products gifts or promotions? Can they be ordered alone, with a limit? Or should zero prices be rejected? | Reviewed and confirmed as gifts; gifts are always free |
| CQ-02 | Should staff complete rows with empty required fields during an import, or should the file be fixed at the source? | Completed during review |
| CQ-03 | When an imported SKU already exists: update after confirmation, update silently, or create only? | Update after confirmation |
| CQ-04 | Is the CSV `stock` the quantity on hand, or a quantity received to add? | The quantity on hand |
| CQ-05 | When one file repeats an SKU, which row wins? | The last row |
| CQ-06 | Is the store single-currency USD? | Yes |
| CQ-07 | Is the category list a fixed taxonomy? | Open-ended, normalised |
| CQ-08 | Should re-importing an archived product's SKU bring it back? | Yes, after confirmation |
| CQ-09 | How long must the audit log and import history be kept, and are actor names personal data that must be removable? | Kept forever |
| CQ-10 | Do suppliers reuse an SKU for a different product? How far may a CSV rename a product? | The same product only while the name stays similar (trigram similarity ≥ 0.5) |

## Known gaps

- **The payment is fake by design** (CC-06): there are no refunds, and admins can't change an order's status.
- **Accounts:**
  - no email confirmation, password reset or profile editing, by the owner's choice;
  - accounts can't be removed or deactivated, so each full browser-test run leaves one test admin and two test customers in the local database.
- **Product images:** a product image is an HTTPS address only; images aren't uploaded or stored.
- **Single currency (USD) and no taxes or shipping.**
- **Card autofill:** browsers turn it off on plain HTTP. A real deployment needs HTTPS.

## Before a real deployment

- **Set your own secrets:** `ADMIN_SEED_EMAIL`, `ADMIN_SEED_PASSWORD` and `CHECKOUT_FINGERPRINT_SECRET` (at least 32 characters). Also set the database password.
- **Serve the site over HTTPS** and set `SESSION_COOKIE_SECURE=true`.
- **Review the security headers** in [`frontend/security-headers.conf`](frontend/security-headers.conf). They already include a strict Content-Security-Policy; add HSTS once HTTPS is in place.

## How AI was used

The project was built in a conversation between the owner (the developer responsible for it) and Claude Code (Anthropic's Claude Opus) acting as the engineer. Codex (OpenAI) was used for independent code reviews.

- **Every prompt and every reply is logged verbatim** in [docs/PROMPT_HISTORY.md](docs/PROMPT_HISTORY.md), more than 50 in all. Every decision is in [docs/JOURNAL.md](docs/JOURNAL.md) with its alternatives.
- **The owner set the direction and made the business decisions:** the architecture, the import rules, the priorities and the login model. The owner reviewed a plan before each feature, and tested and accepted every ticket in the running app. Each ticket's screenshots and test notes are in `tasks/<ticket>-evidence/`.
- **Guardrails kept the AI's output honest:**
  - tests written first for every ticket, covering failures, retries and stock safety;
  - CI gates on types, layering, coverage and comments;
  - browser tests with screenshots before each review.
- **Bugs and slips are recorded, not hidden.** Those found by tests, by the owner or by the reviews have their own journal entries and evidence (for example D-080, D-081, D-084, D-100, D-102, D-112).
- **Four review rounds by Codex** (D-089, D-093, D-099, D-110) found and fixed further issues.
- **Planning:** the work was split into tickets on a simulated Jira board, [tasks/README.md](tasks/README.md), from a walking skeleton (ECOM-000) to delivery (ECOM-017).

## Repository map

| Path | What it holds |
|---|---|
| [`backend/`](backend/) | FastAPI app (`src/ecommerce/{catalog,ordering,identity,shared_kernel,integration}`) and Alembic migrations |
| [`frontend/`](frontend/) | React app, nginx configuration and security headers |
| [`testing/`](testing/) | Every test (backend, frontend, browser, tooling), the fixtures, the scripts and the `run.py` runner |
| [`docs/`](docs/) | Architecture, decision journal and prompt history |
| [`tasks/`](tasks/) | The ticket board, one file per ticket, and the evidence of each review |
| [`docker-compose.yml`](docker-compose.yml) | The four services, plus the `e2e` profile |
