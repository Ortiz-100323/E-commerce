# Decision Journal

Every decision taken on this project is logged here, newest at the bottom. Entries are never deleted. When a decision changes, a new entry supersedes the old one.

**Status values:**
- `Accepted (user)`: decided by the project owner.
- `Proposed`: recommended by the AI, awaiting review.
- `Accepted`: reviewed and approved.
- `Superseded by D-xxx`

Template:

```
### D-xxx — Title
- Date: YYYY-MM-DD
- Status:
- Context:
- Decision:
- Alternatives considered:
- Consequences:
```

---

## 2026-11-21: Session 1 (inputs analysis and planning)

### D-001: Backend framework: FastAPI
- **Date:** 2026-11-21
- **Status:** Accepted (user)
- **Decision:** The backend is built with FastAPI (Python).
- **Consequences:** Pydantic v2 is used for API schemas only. The domain stays framework-free (see D-002).

### D-002: Domain-Driven Design with strict layering
- **Date:** 2026-11-21
- **Status:** Accepted (user). The layering details are Proposed.
- **Context:** The challenge asks for "enterprise-grade". The user chose DDD.
- **Decision:** A modular monolith with the bounded contexts `catalog` and `ordering` plus a `shared_kernel`. Each context has the layers `domain → application → infrastructure/api`. Layering is enforced by `import-linter` in CI.
- **Alternatives considered:**
  - A single flat "products" module with an order table, which is fastest but shows no design.
  - Microservices per context, which is overkill and conflicts with "a docker container".
- **Consequences:** More files up front. Business rules are testable without I/O, and contexts could be split later.

### D-003: Frontend framework: React
- **Date:** 2026-11-21
- **Status:** Accepted (user). The tooling details are Proposed.
- **Decision:** React with TypeScript (strict), built with Vite. TanStack Query for server state, React Router, react-hook-form and zod, CSS Modules.
- **Alternatives considered:**
  - Next.js: SSR is not needed, and a second runtime complicates the single container.
  - Redux: there is no complex client state beyond the cart.
  - A UI kit such as MUI or Chakra: a heavier bundle, and the screens are simple.

### D-004: Test-driven development as a hard rule
- **Date:** 2026-11-21
- **Status:** Accepted (user)
- **Decision:** Every behaviour starts with a failing test (red → green → refactor). Where practical, `test:` commits come before `feat:` commits so the history shows it. Coverage gates are domain and application ≥ 95%, backend ≥ 85%, frontend ≥ 80%.
- **Alternatives considered:** Writing tests after the code, which is faster but defeats the challenge focus.

### D-005: Documentation set in `docs/`
- **Date:** 2026-11-21
- **Status:** Accepted (user)
- **Decision:** Three documents:
  - `TECHNICAL_ARCHITECTURE.md`: structure, plus the challenge rules as non-negotiables.
  - `JOURNAL.md`: this file.
  - `PROMPT_HISTORY.md`: every interaction, word for word.

  The README (required by the challenge) summarises these and links to them.

### D-006: All tests and Python/helper scripts live in `testing/`
- **Date:** 2026-11-21
- **Status:** Accepted (user). Clarified by D-024.
- **Context:** The user wants no scripts scattered around the project.
- **Decision:** `testing/` contains these subfolders:
  - `backend/` (unit, integration, api, architecture)
  - `frontend/` (Vitest specs)
  - `e2e/` (Playwright)
  - `fixtures/`
  - `scripts/`

  Application source code is the only Python outside `testing/`.
- **Alternatives considered:** Keeping only ad-hoc scripts in `testing/` and putting tests next to the code (`backend/tests`, `*.test.tsx`), which is the conventional layout.
- **Consequences:** Vitest must resolve `frontend/node_modules` for specs that sit outside `frontend/`. This is verified in Phase 0, and a fallback is logged if it proves fragile. `testing/` is excluded from the Docker image.

### D-007: Challenge rules are codified as non-negotiables CC-01…CC-13
- **Date:** 2026-11-21
- **Status:** Proposed
- **Decision:** Every requirement in the PDF becomes a numbered rule in `TECHNICAL_ARCHITECTURE.md §1.1`, mapped to how it is satisfied. Every phase exit criterion references those IDs.

### D-008: Local DB is SQLite (via SQLAlchemy and Alembic)
- **Date:** 2026-11-21
- **Status:** Superseded by D-025
- **Context:** The challenge requires a "local DB" and a "docker container" (singular).
- **Decision:**
  - Use SQLite in a Docker volume, with WAL mode, foreign keys on, and `BEGIN IMMEDIATE` for write transactions.
  - Map the domain to tables with SQLAlchemy 2 using imperative mapping, so the domain classes are not ORM classes.
  - Manage the schema with Alembic migrations.
- **Alternatives considered:**
  - PostgreSQL via docker-compose: more production-like and has real `NUMERIC`, but needs two containers.
  - A NoSQL store such as TinyDB or Mongo: weak transactional guarantees for stock updates.
- **Consequences:** It is a drop-in to switch to Postgres later, thanks to the repository ports.

### D-009: Money as Decimal in the domain, integer cents in the DB; weight in integer grams
- **Date:** 2026-11-21
- **Status:** Partially superseded by D-026. The storage part changed; Decimal in the domain still stands.
- **Context:** SQLite has no exact decimal type, and floats corrupt money.
- **Decision:** Money is `Decimal` (at most 2 dp) in the domain and integer minor units in storage. Weight is `Decimal` kg (at most 3 dp) stored as integer grams. The API serialises money as strings.
- **Alternatives considered:**
  - `NUMERIC` columns: SQLite stores these with float affinity.
  - Storing text: this loses ordering and arithmetic in SQL.

### D-010: SKU is the natural key; product names are not unique
- **Date:** 2026-11-21
- **Status:** Proposed
- **Context:** The sample has "Running Shoes" ×3 and "Bluetooth Speaker" ×4 under different SKUs.
- **Decision:** `Sku` is unique (normalised by trimming and upper-casing). `ProductId` (UUID) is the internal identity.

### D-011: CSV import policy: partial success, per-row report, upsert by SKU, last row wins
- **Date:** 2026-11-21
- **Status:** Superseded by D-030, D-031, D-032 and D-033
- **Context:** The sample contains currency symbols, words as prices, negative stock, missing fields, blank rows, XSS and SQL-injection strings, and duplicate SKUs (including an "Updated…" row).
- **Decision:**
  - Invalid rows are reported with their line number and reason. They never block valid rows.
  - Blank rows are skipped silently.
  - A leading `$` is stripped from prices, with a warning.
  - Duplicate SKUs within the file: the last row wins, with a warning.
  - Against the DB: upsert by SKU.
  - All valid rows are written in one transaction.
  - A dry-run preview is available.
  - Validation reuses the domain value objects, so there is one source of truth with the CRUD API.
- **Alternatives considered:**
  - Reject the whole file on the first error: too punitive for real catalog feeds.
  - First row wins on duplicates: this contradicts the "Updated…" row's evident intent.
  - Reject all rows of a conflicting SKU: safe but unhelpful.
  - Create-only mode: makes re-imports impossible.
- **Consequences:** The expected outcome on the sample is verified by simulation:
  - 97 rows in total.
  - 2 blank rows skipped.
  - 8 rows rejected.
  - 87 valid rows. Of these, 3 are duplicate-SKU overrides, leaving 84 products.
  - 1 warning.

  This becomes the golden test.

### D-012: Product validation rules
- **Date:** 2026-11-21
- **Status:** Amended by D-031 (price ≥ 0 with GIFT) and D-032 (empty fields go to review). The name, XSS and SQL rules still stand, and Q-02 is now accepted (D-038).
- **Decision:**
  - **Name:** trimmed, 1–200 characters, no `<` or `>`, no control characters.
  - **Price:** greater than 0, at most 2 dp.
  - **Stock:** integer, 0 or more. Zero means "out of stock", which is valid.
  - **Weight:** required, 0 or more (0 is valid for digital goods), at most 3 dp.
  - **Category:** required. It is free-form, normalised, and compared case-insensitively.
  - **Description:** optional, up to 2000 characters.
- **Rationale:**
  - **XSS:** defended in three ways. Product names never need angle brackets, React escapes output, and `dangerouslySetInnerHTML` is banned by lint.
  - **SQL injection:** defended by parameterised queries. A text such as `Robert'); DROP TABLE products;--` is legitimate data, so it is accepted, and a test proves the table survives.
- **Alternatives considered:**
  - An allow-list of characters for names: this would wrongly reject legitimate apostrophes such as O'Brien.
  - Rejecting the SQL-looking row as well: security theatre that protects nothing.
  - A fixed category enum: every new category would need a code change.

### D-013: Product deletion is a soft delete (archive)
- **Date:** 2026-11-21
- **Status:** Proposed
- **Context:** Orders must keep referencing what was bought.
- **Decision:** `DELETE` archives the product. Archived products are hidden from the storefront and are not purchasable. Their SKU stays reserved, and they can be restored. Order lines snapshot the SKU, name and unit price.
- **Alternatives considered:** A hard delete with `ON DELETE SET NULL` on order lines, which loses product context.

### D-014: Optimistic locking on Product
- **Date:** 2026-11-21
- **Status:** Amended by D-027. Optimistic locking stays for admin edits; checkout uses row locks.
- **Decision:** Each product has a `version` column. `PUT` must send the version it read, and a mismatch returns 409. Stock decrements at checkout also go through the version check.
- **Alternatives considered:**
  - Last-write-wins: silently loses concurrent admin edits.
  - Pessimistic row locks: SQLite has no row locks.

### D-015: Purchase flow: server-side pricing, idempotent checkout, fake payment behind a port
- **Date:** 2026-11-21
- **Status:** Accepted. Q-11 was accepted on its default (D-038). Amended by D-027 (locking) and D-031 (zero-total gift orders).
- **Decision:**
  - **Cart:** lives on the client in `localStorage`. The server re-validates and re-prices it at checkout.
  - **Idempotency:** `POST /orders` requires an `Idempotency-Key` header, to protect against double-clicks and retries.
  - **Payment:** the `PaymentGateway` port is implemented by `FakePaymentGateway`, using test cards: 4242… is approved and 4000…0002 is declined. Only `last4` is stored, and card numbers are never logged.
  - **Transaction:** if the payment is approved, stock is decremented and the order is set to PAID, all in one transaction. If it is declined, the order is recorded as PAYMENT_FAILED and stock is untouched (HTTP 402).
  - **Concurrency:** a dedicated test proves there is no oversell.
- **Alternatives considered:**
  - A server-side cart: requires sessions or users.
  - A "simulate decline" toggle instead of test cards: less realistic and does not exercise a real port contract.
  - Reserving stock and then paying asynchronously: unnecessary for a synchronous fake.

### D-016: Ordering talks to Catalog through an anti-corruption port
- **Date:** 2026-11-21
- **Status:** Proposed
- **Decision:** `ordering` depends on a `CatalogGateway` port (`get_sellable`, `decrease_stock`), never on `catalog.domain`. Both contexts share one Unit of Work and transaction, as a pragmatic choice for a monolith.
- **Alternatives considered:** Domain events with eventual consistency, which is overkill in a single process with one DB.

### D-017: API conventions
- **Date:** 2026-11-21
- **Status:** Proposed. Amended by D-028 (search engine), D-030 (import endpoints) and D-046 (error format).
- **Decision:**
  - REST under `/api/v1`.
  - RFC 9457 Problem Details for errors.
  - Offset pagination with a total count.
  - Search with `q` over name, SKU and description, plus `category`, price-range and `in_stock` filters. LIKE wildcards in user input are escaped.
  - `/health` and `/ready` endpoints.
- **Alternatives considered:**
  - GraphQL: adds nothing for this scope.
  - SQLite FTS5: worth revisiting only if the catalog grows. LIKE is adequate for hundreds or thousands of rows.

### D-018: Single Docker image serving API and SPA
- **Date:** 2026-11-21
- **Status:** Superseded by D-053. (Earlier: partially superseded by D-029; the single app image stood and the database became a companion container.)
- **Decision:** A multi-stage build (node build → Python runtime). FastAPI serves `/api` and the static SPA, which means same-origin and no CORS in production. The image runs as a non-root user, has a `HEALTHCHECK`, runs Alembic on start, and keeps the SQLite file in the `/data` volume. Optional `SEED_SAMPLE_CSV` defaults to off.
- **Alternatives considered:**
  - Separate nginx and API containers: more moving parts, and the challenge says "a docker container".

### D-019: "No comments in code" is enforced automatically
- **Date:** 2026-11-21
- **Status:** Proposed
- **Context:** CC-10: AI is used, so comments must be removed.
- **Decision:** `testing/scripts/check_no_comments.py` tokenizes Python and TS/TSX. Docstrings count as comments. It fails CI and runs as a pre-commit hook. Explanations live in `docs/` and the README.
- **Alternatives considered:** Manual review only, which is error-prone.

### D-020: Delivery in vertical-slice phases with a review gate after each
- **Date:** 2026-11-21
- **Status:** Proposed
- **Decision:** The project is delivered in these phases:
  - Phase 0: walking skeleton.
  - Phase 1: catalog backend.
  - Phase 2: catalog UI.
  - Phase 3: CSV import.
  - Phase 4: purchase.
  - Phase 5: hardening and E2E.
  - Phase 6: docs and delivery.

  Each phase ends with green CI and an explicit user review before the next one starts.
- **Alternatives considered:**
  - Building by layers (all backend first, then all UI): this delays feedback and integration risk to the end.

### D-021: No authentication (pending confirmation)
- **Date:** 2026-11-21
- **Status:** Accepted on its default (D-038). See also D-040 for who is recorded as making each change.
- **Decision:** The challenge does not ask for authentication. The admin area is open, and this is documented in the README as a known gap with the intended approach: OAuth2/JWT with an admin role.
- **Alternatives considered:** Basic auth for `/admin`. It is cheap, but it adds credentials handling to the run instructions.

### D-022: Do not commit the challenge PDF; keep the CSV as a test fixture
- **Date:** 2026-11-21
- **Status:** Superseded by D-036
- **Decision:** `Documents/` stays out of git, or at least the PDF does. The sample CSV is copied to `testing/fixtures/sample_products.csv`, and the README records its download date.
- **Alternatives considered:** Committing everything as received. That could expose the hiring company's material publicly.

---

## 2026-11-21: Session 1, round 2 (owner's answers to the open questions)

### D-023: The sample CSV was downloaded on 2026-11-20
- **Date:** 2026-11-21
- **Status:** Accepted (user)
- **Context:** CC-04 requires the README to state the download date. The owner says the file was downloaded "yesterday" and doesn't remember the time. The file's modification time (2026-11-20) agrees.
- **Decision:** The README states **2026-11-20** as the date only, with no time.

### D-024: `testing/` holds all tests and scripts, with one runner, `testing/run.py`
- **Date:** 2026-11-21
- **Status:** Accepted (user)
- **Context:** The owner confirmed that `testing/` holds *all* tests (backend, frontend and E2E). They also asked for a script that the AI uses to run the test and analysis work it would otherwise improvise with throwaway Python.
- **Decision:**
  - `testing/run.py` is a CLI built only on the standard library, with these subcommands: `backend`, `frontend`, `e2e`, `lint`, `typecheck`, `nocomments`, `all`, `script <name>` and `db up|down`.
  - It is the only way to run anything. That holds locally, for the AI, and in CI, where `ci.yml` calls `run.py all`, so local and CI behave the same.
  - The AI no longer uses inline `python -c`. Any analysis becomes a file in `testing/scripts/` and runs through the runner.
- **Note:** In Session 1, the CSV profiling and the import-policy simulation were done with inline `python -c` before this rule was clarified. Phase 0 turns both into `testing/scripts/profile_csv.py` and `testing/scripts/simulate_import.py`, so they are reproducible.
- **Alternatives considered:**
  - A Makefile: there is no `make` on Windows by default.
  - npm scripts: these would make the Python tooling depend on Node.
  - `nox` or `tox`: an extra dependency for what a small standard-library script can do.

### D-025: PostgreSQL is the only database
- **Date:** 2026-11-21
- **Status:** Accepted (user). This supersedes D-008.
- **Context:** The owner asked "why would we want two databases?". Q-10 was never about two databases. It was a choice between SQLite, a file inside the app container, and PostgreSQL in its own container. The owner chose PostgreSQL.
- **Decision:**
  - PostgreSQL 17 runs as the `db` service in docker-compose, with a named volume.
  - The app uses SQLAlchemy 2 in async mode with psycopg 3. Alembic uses psycopg 3 in sync mode.
  - Integration and API tests run against real PostgreSQL through Testcontainers.
  - Local development starts the database with `run.py db up`.
- **Alternatives considered:**
  - SQLite: rejected by the owner.
  - Bundling PostgreSQL inside the app image so there is literally one container: two processes under a supervisor in one container is an anti-pattern.
  - An in-memory SQLite for tests and PostgreSQL in production: dialect drift would hide bugs. Tests must use the production engine.
- **Consequences:**
  - The application is still one image, but running it now needs a second, companion container. CC-08 is therefore read as "the application runs as a Docker container, and its database runs alongside it via one `docker compose up`". This reading is pending confirmation as Q-13.
  - Docker must be running for the integration tests.

### D-026: Money and weight are stored as `NUMERIC`
- **Date:** 2026-11-21
- **Status:** Proposed. This supersedes the storage part of D-009.
- **Decision:**
  - Price is `NUMERIC(12,2)` and weight is `NUMERIC(10,3)`.
  - In the domain both remain `Decimal`, and the API serialises money as a string.
  - CHECK constraints mirror the domain invariants: price ≥ 0, stock ≥ 0, weight ≥ 0, and a price of 0 implies the GIFT tag.
- **Alternatives considered:** Integer cents and grams. These were needed only because SQLite has no exact decimal type, so they no longer add anything.

### D-027: Checkout locks rows with `SELECT … FOR UPDATE`, in SKU order
- **Date:** 2026-11-21
- **Status:** Proposed. This amends D-014 and D-015. It is detailed further in D-045.
- **Decision:**
  - Checkout locks the products involved with `FOR UPDATE`, ordered by SKU to prevent deadlocks, then validates stock and decrements it.
  - Admin edits keep the optimistic `version` check.
- **Alternatives considered:**
  - An optimistic version check with retries at checkout. Under contention it causes needless 409s for shoppers.
  - A conditional `UPDATE … WHERE stock >= qty`. It is atomic, but it bypasses the aggregate's behaviour.

### D-028: Search uses `ILIKE` with `pg_trgm` GIN indexes
- **Date:** 2026-11-21
- **Status:** Proposed. This amends D-017.
- **Decision:**
  - Search matches name, SKU and description, using trigram indexes. It is case-insensitive and Unicode-aware.
  - LIKE wildcards in user input are escaped.
- **Alternatives considered:**
  - PostgreSQL full-text search (`tsvector`). It adds stemming and ranking, but it handles partial words such as SKU prefixes poorly. It stays a later option.
  - An external engine such as Meilisearch or Elasticsearch. It is out of proportion for this project.

### D-029: Deployment is one app image plus a PostgreSQL container via compose
- **Date:** 2026-11-21
- **Status:** Superseded by D-053. (Earlier: accepted; Q-13 was accepted on its default in D-038, and this superseded the single-container part of D-018.)
- **Decision:**
  - The multi-stage app image still serves both the API and the SPA.
  - `docker-compose.yml` runs two services: `db` (postgres:17-alpine, with a healthcheck) and `app` (`depends_on: service_healthy`).
  - One command starts everything: `docker compose up --build`.
- **Alternatives considered:** See D-025.

### D-030: The CSV import is a review workflow (the `ImportBatch` aggregate)
- **Date:** 2026-11-21
- **Status:** Proposed. This supersedes D-011 and follows from the owner's answers to Q-03 and Q-06. Its row outcomes and expected numbers are amended by D-048 to D-051.
- **Context:** The owner wants zero and empty values, and updates to existing SKUs, to be confirmed or corrected by a person. They should not be decided silently.
- **Decision:**
  - An import is a server-side `ImportBatch` aggregate with these states: `PENDING_REVIEW` → `COMMITTED`, `DISCARDED` or `EXPIRED` (after 24 hours).
  - Each row gets one of these outcomes: `create`, `update` (with a field diff), `unchanged`, `needs_review`, `rejected` or `blank`.
  - The user resolves rows with `confirm`, `correct` or `skip`.
  - A commit is allowed only when nothing is left in `needs_review` and every update has been confirmed or skipped.
  - The commit runs in one transaction. Rows whose product changed since the preview go back to review, and the API returns 409.
  - Endpoints: `POST /imports`, `GET /imports/{id}`, `PATCH /imports/{id}/rows/{line}`, `POST /imports/{id}/commit` and `DELETE /imports/{id}`.
- **Alternatives considered:**
  - A stateless dry run, where the client re-uploads the file together with its resolutions. It needs no table, but it has no audit trail, the payloads are fragile, and the file is parsed twice.
  - Committing immediately and fixing data afterwards. That contradicts the owner's requirement.
- **Consequences:**
  - The workflow adds a table, `import_batches` with `import_batch_rows`, and the review screen becomes the largest UI piece.
  - The expected result for the sample on an empty database is:
    - 2 blank rows;
    - 2 rejected rows;
    - 6 rows needing review;
    - 84 rows to create, after 3 in-file overrides;
    - 1 warning.

    Once the review rows are resolved, there are up to 90 products. Re-importing the same file then reports 84 unchanged.

### D-031: A zero price goes to review and can be confirmed as a GIFT
- **Date:** 2026-11-21
- **Status:** Accepted (user), with the mechanics Proposed. This amends D-012 and D-015.
- **Context:** In the owner's words: "pop up a question to items as 0 … perhaps it is a gift to the user, we may tag it as that … a good question to ask the customer to have a different rule if necessary."
- **Decision:**
  - **Domain:**
    - `Price` is now ≥ 0.
    - A new closed enum, `ProductTag`, starts with a single value, `GIFT`.
    - A new invariant on `Product`: `price == 0 ⇒ GIFT`.
  - **Import:**
    - Prices of `0` and `free` become `needs_review`. The suggested resolution is a price of 0.00 with the GIFT tag. The user confirms it as a gift or corrects the price.
    - Interpreting `free` as a zero-price candidate is the AI's reading.
  - **Admin form:** a price of 0 opens a dialog asking whether to mark the product as a gift. The API returns 422 unless `gift: true` is sent.
  - **Checkout:** an order totalling 0 skips the payment gateway. This is the default until CQ-01 is answered.
- **Alternatives considered:**
  - Rejecting zero prices, which was the round-1 proposal. The owner overruled it.
  - Allowing zero prices silently. That risks selling items for free by mistake.

### D-032: Empty required fields go to review instead of being rejected
- **Date:** 2026-11-21
- **Status:** Accepted (user). This amends D-012.
- **Decision:**
  - If any of `name`, `sku`, `category`, `price`, `stock` or `weight_kg` is empty, the row becomes `needs_review`, and the user fills in the value in the review screen. Values made only of whitespace count as empty.
  - A weight of `0` is also flagged for review, so the user can confirm the product is non-physical. This is the AI's reading of "0 and empty", pending Q-12.
  - A stock of `0` is **not** flagged, because it is the normal "out of stock" state.
  - Invalid values stay `rejected`: negative numbers, malformed numbers, markup in names and bad SKU formats. Whether they should be editable is pending Q-14.

### D-033: An existing SKU is updated only after confirmation
- **Date:** 2026-11-21
- **Status:** Accepted (user). This supersedes the upsert part of D-011.
- **Decision:**
  - A row whose SKU already exists becomes `update` and carries an old → new diff for each field.
  - The importing user confirms each update, or uses "confirm all". If nothing differs, the row is `unchanged` and needs no action.
  - If the SKU belongs to an archived product, the update also restores the product, and the diff shows this.
  - Whether this is the right business rule is raised with the customer as CQ-03.

### D-034: Business rules are configurable policies
- **Date:** 2026-11-21
- **Status:** Proposed
- **Context:** The owner expects the customer may want "a different rule if necessary".
- **Decision:**
  - Import rules are domain strategy objects, selected from settings in the composition root:
    - zero price;
    - empty field;
    - zero weight;
    - existing SKU;
    - duplicate SKU in the same file;
    - currency symbol.
  - Every variant has its own unit tests.
  - Changing a rule is a configuration change, not a code change.
- **Alternatives considered:**
  - Hard-coded rules. Any change from the customer would mean code, tests and a redeploy.
  - A rules engine. It is overkill for six rules.

### D-035: A register of questions for the customer
- **Date:** 2026-11-21
- **Status:** Proposed
- **Context:** The challenge values "asking the right questions". Some open points belong to the business, not to engineering.
- **Decision:**
  - `TECHNICAL_ARCHITECTURE.md` §11.3 tracks business questions as **CQ-xx**, each with the default we built in the meantime. Eight are open now, including stock semantics (absolute or delta), currency, taxonomy and gift rules.
  - The README presents them as "Questions we would ask the business".
  - Engineering questions for the owner remain **Q-xx**.

### D-036: `Documents/` is kept out of git; the sample CSV is a test fixture
- **Date:** 2026-11-21
- **Status:** Accepted (user). This supersedes D-022.
- **Decision:**
  - `.gitignore` excludes the whole `Documents/` folder, which holds the challenge PDF and the CSV as received.
  - A copy of the sample CSV goes to `testing/fixtures/sample_products.csv` so CI can run the golden test.
- **Note:** If the CSV must not be in the repository at all, the golden test would have to load it from an external path and be skipped in CI. This is not recommended.

---

## 2026-11-21: Session 1, round 3 (Q-14 and the audit trail)

### D-037: Only rows flagged for a zero or empty value are editable during review
- **Date:** 2026-11-21
- **Status:** Accepted (user)
- **Context:** Q-14 asked whether rejected rows should be editable. The owner's answer: "they could edit the ones we flag as errors due to 0 or empty values. But we need to have the log of it to trace it back as how it was and how it became."
- **Decision:**
  - Rows flagged `needs_review` are editable in the review screen: corrected, confirmed or skipped. These are the rows with a zero price, a zero weight or an empty required field.
  - Rows flagged `rejected` are listed with their reason and are not editable. These are rows with negative values, malformed numbers, markup in the name or an invalid SKU. They are fixed in the source file, which is then uploaded again.
  - Every edit is audited (D-039).
- **Alternatives considered:** Making rejected rows editable too. The owner limited editing to zero and empty values, so it stays out.

### D-038: Q-02, Q-07, Q-11, Q-12 and Q-13 are closed on their proposed defaults
- **Date:** 2026-11-21
- **Status:** Accepted (user: "the rest can be default")
- **Decision:**
  - **Q-02:** a name containing markup (`<script>…`) is rejected. A name that looks like SQL is accepted as plain text.
  - **Q-07:** there is no authentication. This is documented as a known gap.
  - **Q-11:** guest checkout, asking for name and email.
  - **Q-12:** a weight of 0 is flagged for review. A stock of 0 is not flagged.
  - **Q-13:** CC-08 is read as one app image plus a PostgreSQL container, started together with `docker compose up`. *(Superseded by D-053: four containers.)*

### D-039: Append-only audit trail fed by domain events, written in the same transaction
- **Date:** 2026-11-21
- **Status:** Accepted (user requirement). The mechanism is Proposed.
- **Context:** The owner wants to "trace it back as how it was and how it became".
- **Decision:**
  - `ImportRow` keeps the raw CSV line verbatim, and the raw values, unchanged forever. It also keeps a history of every resolution.
  - Aggregates record domain events, for example `ImportRowCorrected`, `ImportRowConfirmed`, `ProductChanged` and `StockDecreased`. Each event carries the values before and after, the context (batch, line, file SHA-256 and the original issue) and the actor.
  - The Unit of Work writes the events to `audit_log` in the same transaction as the change. An audit entry therefore can never be lost, and it can never describe a change that was rolled back.
  - `audit_log` is append-only: a database trigger rejects `UPDATE` and `DELETE`.
  - `GET /products/{id}/history` and the admin History screen show the timeline: the raw line, then the corrections, then creation, then later edits.
- **Alternatives considered:**
  - Generic PostgreSQL audit triggers that capture row diffs. They capture *what* changed but lose *why*. For example, a "confirmed as gift" decision would be indistinguishable from a manual price edit. They also move logic into the database.
  - Event sourcing the `Product` aggregate. It gives a full history, but it is far heavier than this project needs.
  - Application log lines. They are not queryable, not transactional and easy to lose.

### D-040: Who made the change: a self-declared name until authentication exists
- **Date:** 2026-11-21
- **Status:** Proposed
- **Context:** An audit trail needs a "who", but there is no login (D-021).
- **Decision:**
  - The admin area asks "Who is reviewing?" once, stores the answer in `localStorage`, and sends it as the `X-Actor-Name` header on every request that changes data. If the header is missing, the request fails with 422.
  - The name is stored as `actor` and labelled as self-declared.
  - When authentication arrives, the actor will come from the token instead, and the audit format will not change.
  - The storefront actor is the order and customer reference.
- **Alternatives considered:**
  - A reviewer field on every form: repetitive, and easy to fill in inconsistently.
  - Recording the IP address or user agent: not meaningful as a "who", and it is personal data.
  - Leaving the actor empty: then the audit cannot answer "who".

### D-041: The audit covers every product change, not only import corrections
- **Date:** 2026-11-21
- **Status:** Proposed
- **Decision:** The audit trail records:
  - every import row resolution;
  - every product create, change, archive and restore, whether it comes from an import or from the admin;
  - every stock decrease caused by an order.
- **Rationale:** It is the same mechanism at almost no extra cost. A history covering only imports would show "how it became" at import time, but not what happened to the product afterwards.
- **Alternatives considered:** Auditing only import corrections, which is the strict reading of the owner's request.

### D-042: Import batches and audit entries are retained indefinitely
- **Date:** 2026-11-21
- **Status:** Proposed (CQ-09)
- **Decision:**
  - Committed, discarded and expired batches are all kept, together with their raw lines.
  - Nothing is purged.
  - How long data must be kept, and whether actor names count as personal data, are raised with the customer as CQ-09.
- **Alternatives considered:**
  - Storing the original file as a blob: redundant, because the header plus the verbatim raw lines can rebuild the file, and the SHA-256 proves it is intact.
  - Purging after N days: there is no basis for choosing N without the customer.

---

## 2026-11-21: Session 1, round 4 (deep dive on four points)

### D-043: The idempotency key is a client-generated UUID v4, one per checkout attempt
- **Date:** 2026-11-21
- **Status:** Proposed. This details the idempotency part of D-015.
- **Context:** The owner asked what the idempotency key is.
- **Decision:**
  - **What it is:** the browser creates the key with `crypto.randomUUID()` and sends it in the `Idempotency-Key` header. This follows the IETF draft *The Idempotency-Key HTTP Header Field*.
  - **When it is reused or replaced:** one key covers one checkout attempt.
    - It is reused for double-clicks, network retries and timeouts.
    - It is replaced when the cart or the form changes, and after every final answer (201 or 402).
  - **Validation:** a missing key or a key that is not a UUID gives a 400.
  - **Scope:** `POST /orders`. Keys are global while there is no login, and will become (user, key) once there is one.
  - **Retention:** 24 hours. Keys live in the `idempotency_keys` table, which stores the key, the endpoint, the request fingerprint, the outcome, the response status and the expiry.
  - **Atomicity:** the key is claimed with `INSERT … ON CONFLICT DO NOTHING` **in the same transaction** as the order. The key, the order and the stock change are committed or rolled back together.
  - **Concurrent duplicates:** if two requests arrive with the same key, the second waits on the unique index and then receives the replay. No `IN_PROGRESS` state is needed.
  - **Layering:** `IdempotentCheckout` sits in the application layer and uses an `IdempotencyStore` port. It stores the outcome of the use case, and the API maps that outcome to HTTP the same way every time.
- **Alternatives considered:**
  - Server-generated keys or tokens issued at the start of checkout. This costs an extra round trip and adds nothing over a UUID created by the client.
  - Deduplicating by cart content alone, with no key. This would block a legitimate second purchase of the same items.
  - HTTP middleware that caches raw responses. It sits outside the transaction, so a crash between the commit and the cache write breaks the guarantee.
  - A committed `IN_PROGRESS` row followed by a 409 for concurrent duplicates. This is needed only once a real payment provider makes long transactions impossible, and it is documented as the future design.

### D-044: The same key with a different body returns 422 and processes nothing; only lasting outcomes are stored
- **Date:** 2026-11-21
- **Status:** Proposed
- **Context:** The owner asked what happens when the same key comes with a different body.
- **Decision:**
  - **How a body is fingerprinted:**
    - The fingerprint is a SHA-256 over the canonical parsed request: SKUs upper-cased, lines merged and sorted, the email lower-cased, JSON keys sorted.
    - The fingerprint includes **only the last 4 digits** of the card, because a hash of a full card number can be brute-forced.
  - **Same key, same fingerprint:** replay the stored outcome with the same status and body, plus the header `Idempotent-Replayed: true`.
  - **Same key, different fingerprint:** return **422 `idempotency-key-reused`**. Nothing is processed, and nothing about the original order is revealed.
  - **Which outcomes are stored:** only lasting ones, meaning **201 (PAID)** and **402 (PAYMENT_FAILED)**.
    - Results such as 422, 404 or 409 roll back, so the key stays free and can be retried after the cart is fixed.
    - A 402 is replayed on retry. Trying a different card needs a new key, which the UI creates automatically.
- **Alternatives considered:**
  - **409 Conflict for a reused key.** The IETF draft uses 422 for a mismatched payload and 409 for a request still in progress. We follow the draft.
  - **Silently processing the new body as a new order.** This defeats the purpose of the key.
  - **Fingerprinting the raw bytes.** A whitespace or key-order change in the JSON would then be treated as a different request.
  - **Storing failures as well.** A shopper with an out-of-stock item would then be stuck with a key that always replays the failure.

### D-045: Preventing oversold stock: lock with `FOR UPDATE` in SKU order, with timeouts, one retry and a database guard
- **Date:** 2026-11-21
- **Status:** Proposed. This details D-027.
- **Context:** The owner asked how we stop two purchases from reading the same stock at the same time.
- **Decision:**
  - **Locking order.** Every writer that changes the same product rows (checkout and the import commit) locks them with `SELECT … FOR UPDATE ORDER BY sku`. A second checkout blocks, then re-reads the committed row under READ COMMITTED, then fails with 409 `insufficient-stock`, which lists each item's `{sku, requested, available}`.
  - **Admin edits.** They change one row and keep the optimistic `version` check, which also catches an edit made after a checkout changed the row.
  - **Deadlocks.** The consistent locking order means none should happen. If PostgreSQL still reports one (`40P01`), the whole transaction is retried once.
  - **Lock timeout.** `lock_timeout` is set to 5 s. A longer wait returns 503 with `Retry-After: 1`.
  - **Who decides.** The domain does: `Product.decrease_stock` raises `InsufficientStock`. The database guards: `CHECK (stock >= 0)` is the last line of defence, and if it ever fires it is logged as a bug.
  - **Payment.** The payment call happens inside the lock only because the gateway is an in-process fake. With a real provider, the design changes to reserving stock with an expiry, paying, then confirming or releasing.
- **Alternatives considered:**
  - A conditional `UPDATE … WHERE stock >= :q`. It is atomic, but it bypasses the aggregate.
  - Optimistic retries. These cause 409s for shoppers when many check out at once.
  - `SERIALIZABLE` isolation. Every caller would need a retry loop.
  - An in-process mutex. It breaks as soon as there is more than one worker.
  - A Redis lock. It adds infrastructure we don't need.
- **Tests:**
  - A race of 20 parallel checkouts for the last unit: exactly 1 succeeds and 19 get 409.
  - A deterministic test where a payment latch holds the first checkout inside the lock, with no sleeps.
  - Two carts locking the same items in opposite order: neither deadlocks.
  - An admin edit made with a stale version: it is rejected.
  - The CHECK constraint: it blocks negative stock.

### D-046: One error format: RFC 9457 Problem Details for every error
- **Date:** 2026-11-21
- **Status:** Proposed. This amends D-017.
- **Context:** The owner asked how to return the right errors from Pydantic validation, in one consistent format.
- **Decision:**
  - **Coverage.** Every error is `application/problem+json`, whatever produced it: Pydantic, the domain, the application layer, Starlette, or an unexpected failure. Each response carries `type` (`urn:ecommerce:problem:<name>`), `title`, `status`, `detail`, `instance` and `request_id`. Validation errors add `errors[] {location, field, code, message, params}`.
  - **Converting Pydantic errors:**
    - `loc` becomes `location` plus a field path such as `lines[0].quantity`.
    - Pydantic's `type` becomes our stable `code` through a mapping table, and a test fails if any type is missing from it.
    - `ctx` becomes `params`.
    - `input` and `url` are dropped, so **values are never echoed back**. This keeps card numbers and personal data out of responses and logs.
  - **Status codes:**
    - Unparseable JSON gives **400** `malformed-request`.
    - Parseable but invalid input gives **422** `validation-error`.
    - The `Idempotency-Key` header gives **400**, overriding FastAPI's default 422, to follow the IETF draft.
  - **Who checks what.** Pydantic checks *shape*: types, required fields, `extra="forbid"` and abuse limits. The domain checks *meaning*. Each rule lives in one place, and both produce the same 422 shape.
  - **All issues at once.** Domain validation collects every issue before raising, so forms show all their errors together.
  - **Catalog.** A catalog of problem types (§4.6) lists each type's status and extra fields, such as `items[]` for insufficient stock and `current_version` for version conflicts.
  - **Frontend.** One `ApiError` parser maps `errors[].field` onto react-hook-form fields. Every other problem appears as a notification.
- **Alternatives considered:**
  - FastAPI's default `{"detail": [...]}` for validation, alongside custom shapes elsewhere. That is two formats for clients to handle.
  - A custom error envelope. It reinvents a standard.
  - `about:blank` as the type for every error. Clients then cannot branch on the type.
  - Echoing the rejected value. It is convenient for debugging, but it leaks sensitive data.

### D-047: One `ValidationIssue` vocabulary for API errors and import rows
- **Date:** 2026-11-21
- **Status:** Proposed
- **Decision:**
  - The domain reports problems as `ValidationIssue {field, code, severity, message, params}`.
  - The API's `errors[]` and the import report's per-row issues use the same structure and the same codes.
  - The frontend renders both with one component.
- **Alternatives considered:** Separate vocabularies for the API and the import. They would drift apart, and the same rule would show up under two different names.

### D-048: CSV issue taxonomy: warning (imported), review (held for a person) and error (rejected)
- **Date:** 2026-11-21
- **Status:** Proposed. This refines D-030 and D-032.
- **Context:** The owner asked what counts as a warning (row imported) and what counts as an error (row rejected).
- **Decision:**
  - **Three severities.** The row's outcome follows its most severe issue, and all issues are collected rather than stopping at the first.
    - **Warnings are lossless fixes only.** The row is imported. The codes are `currency_symbol_stripped`, `sku_normalized`, `integer_normalized`, `duplicate_sku_in_file` and `restores_archived_product`.
    - **Review is for values that are 0 or empty.** The row is held for a person (D-037). The codes are `empty_required_field`, `zero_price` and `zero_weight`.
    - **Errors are for anything invalid or dangerous.** The row is rejected and cannot be edited. The codes are:
      - `wrong_field_count`, `invalid_number`, `unsupported_currency`, `negative_value`
      - `too_many_decimal_places`, `not_an_integer`, `value_out_of_range`, `value_too_long`
      - `invalid_sku_format`, `markup_in_name`, `control_characters`
      - `sku_conflict_in_file`, `sku_belongs_to_different_product`
  - **File-level errors refuse the whole upload.** The codes are `file_too_large` (413), `unsupported_media_type` (415), `invalid_encoding`, `empty_file`, `missing_columns`, `duplicate_columns`, `too_many_rows` (10,000) and `malformed_csv`.
  - **File-level warnings** are `unknown_column_ignored` and `same_file_already_pending`.
  - **Guiding rule: never silently change what a value means.** Rounding, truncating, or guessing a currency or decimal separator are errors, never warnings.
    - `NaN`, `Infinity`, exponent notation, thousands separators and decimal commas are rejected. Python's `Decimal` accepts some of these, so we check for them explicitly.
    - Trimming whitespace, removing a BOM and handling line endings are silent.
- **Alternatives considered:**
  - Treating trimming as a warning: every report would fill up with noise.
  - Rounding `9.999` to `10.00` with a warning: money would change without anyone noticing.
  - Accepting `1,299.99`: in some locales the comma is the decimal separator, so the value is ambiguous.

### D-049: Duplicate SKUs within one file: earlier rows are `superseded`, a failed winner brings nothing back, and differing names are a conflict
- **Date:** 2026-11-21
- **Status:** Proposed. This refines the in-file part of D-011 and D-030.
- **Decision:**
  - **Last row wins.** When rows share an SKU and describe the same product (the identity check in D-050), the last row is imported. It carries the warning `duplicate_sku_in_file`, and the earlier rows get the new outcome `superseded`.
  - **No fallback.** If the last row is rejected or needs review, the earlier rows are **not** used instead, because the file meant to replace them.
  - **Different products.** If rows with the same SKU describe different products, every one of them gets the error `sku_conflict_in_file`.
- **Alternatives considered:** Falling back to the last *valid* row. That would silently import data the file had tried to supersede.

### D-050: SKU identity check: an existing SKU that names a different product is rejected
- **Date:** 2026-11-21
- **Status:** Proposed (CQ-10)
- **Context:** The owner asked us to check that an SKU in the file doesn't already belong to a different product in our database. A reused or mistyped SKU would otherwise overwrite another product, and that product's orders and audit history would no longer describe it.
- **Decision:**
  - **Normalising names.** For each row whose SKU exists in the database, active or archived, both names are compared after normalisation: NFKC, case-folding and collapsed whitespace.
  - **Comparing them:**
    - Equal names mean the same product.
    - Otherwise, a trigram similarity (the same measure as `pg_trgm`, implemented in pure Python in the domain) of **0.5 or more** is treated as a rename and goes through the confirmed `update`.
    - Below 0.5, the row is rejected with **`sku_belongs_to_different_product`**, and the message names both products.
  - **Within the file.** The same check runs on rows that share an SKU (D-049).
  - **At commit time.** The check runs again under the commit's locks. An SKU that was taken after the preview sends the row back to review and returns 409. The unique index on `sku` is the final guard.
  - **Configuration.** The policy is `IMPORT_SKU_IDENTITY_POLICY`, with the values `name_similarity` (the default), `exact_name` and `sku_only`.
- **Alternatives considered:**
  - **`sku_only`, which trusts the SKU blindly.** This risks the silent overwrite described above.
  - **`exact_name`.** Every rename would be rejected, including harmless ones like "Running Shoes" → "Running Shoes Pro".
  - **Sending conflicts to review with a "confirm it's the same product" button.** This contradicts D-037, which makes only rows with zero or empty values editable, and the fix (a new SKU) belongs in the source file.
  - **A reverse check, flagging the same name under a different SKU.** Names are not unique (D-010) and variants are normal. On the sample it would raise 2 false alarms (RS-050 and BS-099).
- **Consequences:** A drastic rename through CSV is rejected as a false positive (for example, "Cotton T-Shirt" → "Organic Tee"). The workaround is to rename the product in the admin first.

### D-051: Updated expected numbers for the golden test on the sample
- **Date:** 2026-11-21
- **Status:** Proposed. This supersedes the numbers in D-030.
- **Decision:** On an empty database, the 97 rows break down as follows:
  - 2 `blank`
  - 2 `rejected`
  - 6 `needs_review`
  - 84 `create`
  - 3 `superseded`

  There are 3 warnings: 1 `currency_symbol_stripped` on line 4, and 2 `duplicate_sku_in_file` on lines 36 and 89. The identity check produces 0 conflicts.
- **How the numbers were obtained:**
  - The row counts come from the profile verified in Session 1.
  - The way the warnings are counted changed, so those were counted by hand.
  - Phase 0's `testing/scripts/simulate_import.py` re-verifies every number before the golden test is written.
  - No ad-hoc scripts were run in this round, in line with PR-04.

---

## 2026-11-21: Session 2 (walking skeleton plan and the task board)

### D-052: ECOM-000 is a walking skeleton with a temporary weather feature
- **Date:** 2026-11-21
- **Status:** Accepted (user accepted ECOM-000 on 2026-11-21).
- **Context:** Before any business rules, the owner wants proof that the whole stack works end to end: backend, frontend, PostgreSQL and CI, each in its own container.
- **Decision:**
  - A small weather feature is the test case. The user types a city, the backend looks it up on Open-Meteo (public, no key), saves the search in PostgreSQL and returns it, and the portal shows the result and the history.
  - The backend uses the DDD layers (§3.2) inside a temporary `weather` bounded context, so the structure and `import-linter` are validated before real work.
  - **The weather feature is temporary.** ECOM-009 deletes it, with a migration that drops its table, once the catalog can play the same end-to-end role.
- **Alternatives considered:**
  - A static "hello" page with only a health check: it would not prove the database write path, an outbound HTTP call, or the layering.
  - Starting directly with products: the first business ticket would also have to debug the infrastructure.
- **Consequences:** Some throwaway code. Every container, the proxy, migrations and the CI flow are proven before ECOM-001.

### D-053: Four containers: `db`, `backend`, `frontend` and `ci`, all started by `docker compose`
- **Date:** 2026-11-21
- **Status:** Accepted (user). This supersedes D-018, D-029 and the Q-13 answer in D-038.
- **Context:** The owner asked for each part to run in its own local container.
- **Decision:**
  - `db`: `postgres:17-alpine`, a named volume, a `pg_isready` healthcheck, and an init script that also creates `ecommerce_test`. Host port 5433.
  - `backend`: Python 3.13 with uv; runs `alembic upgrade head`, then uvicorn. Host port 8001 (8000 is taken by another project), so Swagger is at `http://localhost:8001/docs`.
  - `frontend`: a multi-stage build (Node builds the SPA, nginx serves it and proxies `/api/`). Host port 3000.
  - `ci`: runs the full suite once and exits with its result (D-055).
  - `docker compose up --build` starts all four.
- **Alternatives considered:**
  - One image serving both the API and the SPA (D-018/D-029): fewer containers, but frontend and backend could not be built, scaled or replaced independently, which the owner explicitly wants.
  - A `ci` service behind a compose profile: cleaner, but the owner asked for everything to start with compose.
- **Consequences:** CC-08 is still met: the application runs locally in Docker with one command. §3, §9, §10 and §12 of the architecture describe the old single image; they get revision 5 once this plan is approved.

### D-054: The frontend reaches the API through an nginx reverse proxy on the same origin
- **Date:** 2026-11-21
- **Status:** Accepted (user accepted ECOM-000 on 2026-11-21).
- **Decision:**
  - The browser only talks to the `frontend` container. The React code calls relative URLs (`/api/v1/...`).
  - nginx forwards every `/api/` request to `http://backend:8000` over the compose network, keeping the path.
  - Natively (`npm run dev`), Vite's dev-server proxy forwards `/api` to the backend in the same way.
- **Alternatives considered:**
  - The browser calls `http://localhost:8001` directly, with CORS enabled: it needs CORS configuration and an API URL baked into the build at compile time, which differs per environment.
  - A runtime `config.js` holding the API URL: it solves the build-time URL, but still needs CORS.
- **Consequences:** No CORS, no environment-specific build, and the same relative URLs everywhere. The backend's port is published only for Swagger and debugging.

### D-055: CI runs locally in its own container through `testing/run.py`
- **Date:** 2026-11-21
- **Status:** Accepted (user accepted ECOM-000 on 2026-11-21).
- **Decision:**
  - `testing/Dockerfile` builds a `ci` image with Python 3.13, uv and Node 22, containing `backend/`, `frontend/` and `testing/`.
  - It waits for `backend` and `frontend` to be healthy, runs `python testing/run.py all`, and exits with its code. `docker compose run --rm ci` reruns it.
  - `run.py all` runs, in order: ruff, import-linter, the no-comments check, backend pytest, frontend build and Vitest, and the smoke test against the running stack.
  - GitHub Actions is deferred to ECOM-016, where it will run the same compose stack and `ci` container.
- **Alternatives considered:** Running the tests on the host only: it does not prove that the containers work together, which is the point of ECOM-000.

### D-056: One health endpoint, `GET /api/v1/health`, which also reports the database
- **Date:** 2026-11-21
- **Status:** Accepted (user accepted ECOM-000 on 2026-11-21). This refines the `/health` and `/ready` pair in §4.5.
- **Decision:** It returns 200 `{"status":"ok","database":"up"}`, or 503 with `"database":"down"`. It sits under `/api/v1`, so it shows in Swagger and is reachable through the proxy. The backend's Docker healthcheck calls it.
- **Alternatives considered:** Separate liveness and readiness endpoints: useful for an orchestrator that restarts containers, which we don't have. They can be split later without breaking clients.

### D-057: Skeleton tests mock Open-Meteo; integration tests use the compose database for now
- **Date:** 2026-11-21
- **Status:** Accepted (user accepted ECOM-000 on 2026-11-21). The Testcontainers question is decided in ECOM-001.
- **Decision:**
  - Use-case and API tests replace the `WeatherProvider` port with a fake. The Open-Meteo adapter is tested against `httpx.MockTransport`, with no extra dependency.
  - The only test that calls the real Open-Meteo is the smoke test, because it proves the backend container can reach the internet.
  - Integration tests run against the `ecommerce_test` database on the compose `db` service. Testcontainers (§4.1) would need the Docker socket inside the `ci` container, which adds risk to the skeleton; ECOM-001 decides whether to adopt it.
  - Frontend tests stub `fetch`; MSW arrives in ECOM-006.
- **Alternatives considered:** `respx` for mocking httpx: nice, but `MockTransport` is built in.

### D-058: A `tasks/` folder simulates Jira
- **Date:** 2026-11-21
- **Status:** Accepted (user)
- **Decision:**
  - One Markdown file per ticket (`ECOM-000.md`, `ECOM-001.md`, …), each with context, scope, acceptance criteria, test plan, definition of done and status.
  - `tasks/README.md` is the board, listing every ticket with its phase, dependencies and status.
  - Statuses: Backlog, To Do, In Progress, In Review, Done. A ticket reaches Done only after the owner accepts it.
  - **ECOM-000** sets up the environment. **ECOM-001 onwards** build the e-commerce application.
- **Consequences:** The ticket files and the board must be updated whenever work moves.

### D-059: ECOM-000 stays lean; the architecture's phases map to tickets ECOM-001 to ECOM-017
- **Date:** 2026-11-21
- **Status:** Accepted (user accepted ECOM-000 on 2026-11-21).
- **Context:** The owner asked for the essentials only in the skeleton.
- **Decision:**
  - ECOM-000 includes the four containers, the weather feature through every layer, Alembic, ruff, import-linter, the no-comments check, `run.py`, the smoke test and a short README.
  - Deferred from §12 Phase 0: mypy strict, the Problem Details format and Testcontainers (ECOM-001); TanStack Query and React Router (ECOM-006); `profile_csv.py` and `simulate_import.py` (ECOM-010); Playwright and GitHub Actions (ECOM-016).
  - Phases 1–6 become: Phase 1 = ECOM-001 to 005, Phase 2 = 006 to 009, Phase 3 = 010 to 012, Phase 4 = 013 to 015, Phase 5 = 016, Phase 6 = 017.
- **Alternatives considered:** The full Phase 0 from §12 in one ticket: a larger skeleton that would delay the end-to-end proof.

## 2026-11-21: Session 2, round 2 (building ECOM-000)

### D-060: Versions pinned and implementation choices made while building ECOM-000
- **Date:** 2026-11-21
- **Status:** Accepted (user accepted ECOM-000 on 2026-11-21).
- **Versions.** Lock files (`backend/uv.lock`, `frontend/package-lock.json`) hold the exact versions. The main ones:
  - Backend: Python 3.13, FastAPI 0.165.0, Starlette 1.10.0, Pydantic 2.14.4, SQLAlchemy 2.1.9, psycopg 3.3.9, Alembic 1.20.1, httpx 0.28.1, uvicorn 0.54.0. Dev: pytest 9.2.0, pytest-asyncio 1.5.0, ruff 0.17.6, import-linter 2.17.
  - Frontend: React 19.3.1, Vite 8.3.8, TypeScript 7.0.2, Vitest 5.1.1, Testing Library (React 16.3.3, user-event 14.6.13, jest-dom 8.0.0), jsdom 29.1.1.
  - Images: `postgres:17-alpine`, `python:3.13-slim`, `node:22-alpine`, `node:22-bookworm-slim`, `nginx:1.28-alpine`, `ghcr.io/astral-sh/uv:0.11.29`.
- **Choices:**
  - **Composition root with a dependencies factory.** `create_app(dependencies_factory)` receives an async context manager that yields the adapters. Production wires PostgreSQL, httpx and Open-Meteo; tests pass fakes. The routers read the adapters from `app.state` and build the use cases per request.
  - **No Unit of Work yet.** The weather repository opens its own transaction per call. The shared Unit of Work arrives in ECOM-001.
  - **SQLAlchemy Core for the weather table.** The repository maps rows to domain objects by hand. Imperative ORM mapping is kept for the real aggregates (ECOM-003).
  - **Migrations run on container start** (`alembic upgrade head`, then uvicorn), and the integration tests run them against `ecommerce_test` before testing.
  - **Windows-only test settings.** psycopg's async driver can't use Windows' default event loop, so `testing/backend/conftest.py` gives pytest-asyncio a selector loop on Windows only. The containers run Linux and are unaffected.
  - **Frontend tests in `testing/frontend`.** A small Vite plugin in `vite.config.ts` resolves the specs' package imports (`react`, Testing Library) from `frontend/node_modules`, the risk §9 flagged. `vitest` itself is left to Vitest. Vitest must also be started with the true path casing (`C:\…`); `run.py` guarantees that, while a Git Bash cwd of `c:\…` loads `vitest` twice.
  - **Ruff runs with `--config backend/pyproject.toml`** over `backend/` and `testing/`, with `ecommerce` and `fakes` declared as first-party for import sorting.
- **Known leftover:** Starlette 1.10 warns that its `TestClient` should use `httpx2`. Adding that package was blocked as unvetted, so the warning stays until the owner decides.

---

## 2026-11-21: Session 2, round 3 (ECOM-001, backend foundation)

### D-061: Integration tests use the compose database, not Testcontainers
- **Date:** 2026-11-21
- **Status:** Accepted (owner, prompt #009). This settles the open point in D-057 and supersedes "Testcontainers" in §4.1, §7.3 and §8.1.
- **Decision:** Integration tests run against the `ecommerce_test` database on the compose `db` service. It is migrated once per test session through Alembic, and each test truncates the tables it uses. Locally that means `docker compose up -d db` first; in the `ci` container, the database is already there.
- **Alternatives considered:**
  - **Testcontainers.** Each run gets a fresh PostgreSQL, but the `ci` container would need the host's Docker socket mounted. That gives the container root-level control of the host, and adds a second way of starting PostgreSQL to maintain.
  - **SQLite for tests.** Fast, but it can't test `FOR UPDATE`, `pg_trgm`, CHECK constraints or the audit trigger, which are the reasons we chose PostgreSQL.
- **Consequences:** The race tests in ECOM-014 run on the compose database over separate connections, which is what they need. Two test runs at once against the same database would interfere, which doesn't happen in our workflow.

### D-062: How Problem Details is built
- **Date:** 2026-11-21
- **Status:** Accepted (owner, prompt #009). This implements D-046 and D-047.
- **Decision:**
  - **Base errors in the shared kernel.** `DomainValidationError` carries one or more `ValidationIssue`s and becomes 422 `validation-error`. `NotFoundError` becomes 404 `not-found`, with an optional `detail`.
  - **Exception-to-problem tables.** Each context hands the composition root a table from its exception types to problem types, so `shared_kernel` never imports a context. Today: `WeatherUnavailable` → 502 `upstream-unavailable` (a new type in the catalog), and SQLAlchemy's `OperationalError` → 503 `service-unavailable` with `Retry-After: 1`.
  - **HTTP errors** (unknown route, wrong method) map by status. A status with no type in the catalog uses `about:blank` with the standard phrase, as RFC 9457 recommends. The `Allow` header of a 405 is kept.
  - **Broken JSON** (Pydantic's `json_invalid`) is 400 `malformed-request`, with no `errors[]`.
  - **Pydantic errors.** A table maps each Pydantic type to our code; an unknown type falls back to `invalid` rather than failing. `params` keep only plain values (strings, numbers, booleans; Decimals as strings). Pydantic's `input`, `url` and any `error` object are dropped, so a submitted value can't come back in a response.
  - **A coverage test** reads the app's OpenAPI document, works out every Pydantic error type our request schemas can raise, and fails if one has no code. New endpoints are covered automatically.
  - **500s** never show the exception. The error is logged with the request ID, and the response carries the same ID so the logs can be found.
- **Alternatives considered:**
  - A global registry that contexts add themselves to at import time: hidden coupling, and order-dependent.
  - Translating database errors inside every repository: more code for the same 503.

### D-063: Request IDs and structured logs
- **Date:** 2026-11-21
- **Status:** Accepted (owner, prompt #009)
- **Decision:**
  - A pure ASGI middleware gives every request an ID and returns it in `X-Request-ID`. An incoming `X-Request-ID` is kept only if it is 8–64 letters, digits or hyphens; anything else is replaced with a new UUID, so a client can't inject text into our logs.
  - Logs are JSON, one object per line, with `time`, `level`, `logger`, `message` and `request_id`. Each request writes exactly one line (`ecommerce.request`) with method, path, status and duration. The query string is never logged.
  - Uvicorn's own access log is silenced, because our request line replaces it.
  - `create_production_app` configures the logging; `create_app` doesn't, so tests can capture logs normally.
- **Alternatives considered:** Starlette's `BaseHTTPMiddleware`. It is simpler to write, but it has known problems with exceptions and streaming responses.

### D-064: `Money` in the shared kernel
- **Date:** 2026-11-21
- **Status:** Accepted (owner, prompt #009). This implements PR-08 and CQ-06.
- **Decision:**
  - `Money` holds a `Decimal` amount, normalised to 2 decimal places, in USD only.
  - Bad **data** raises `InvalidMoney`, a `DomainValidationError`: more than 2 decimal places, NaN or infinity, an amount beyond Decimal precision, another currency, or text that isn't a number.
  - A float or a boolean raises `TypeError` instead, because that is a programming error, never user input.
  - `Money` supports `+`, `-`, multiplication by a whole quantity, comparison and `is_zero`. It may be negative; `Price` adds the "≥ 0" rule in ECOM-002.

### D-065: A generic SQLAlchemy Unit of Work
- **Date:** 2026-11-21
- **Status:** Accepted (owner, prompt #009)
- **Decision:**
  - `UnitOfWork` is a port in `shared_kernel.application`. `SqlAlchemyUnitOfWork` opens a session on entry, commits only when `commit()` is called, and rolls back everything else on exit, including after an exception.
  - Each context's own Unit of Work (from ECOM-003) will build on it and expose that context's repositories. ECOM-004 adds writing the audit events in the same transaction.
  - The temporary weather repository keeps its own transactions; it isn't worth migrating before ECOM-009 deletes it.

### D-066: Quality gates added in ECOM-001
- **Date:** 2026-11-21
- **Status:** Accepted (owner, prompt #009)
- **Decision:**
  - `mypy --strict`, with the Pydantic plugin, over `backend/src` and `backend/migrations`. It runs in `run.py lint`, so in the `ci` container too.
  - A layers contract for `shared_kernel` (`api | infrastructure` → `application` → `domain`), and `shared_kernel.domain` joins the "free of frameworks" contract. The request-ID middleware therefore lives in `infrastructure`, and the problem handlers read the request ID from the request rather than importing it.

### D-067: Delivery reports are written from a business point of view
- **Date:** 2026-11-21
- **Status:** Accepted (requested by the owner in prompt #008)
- **Context:** The owner tests each delivery as a business person would. Technical delivery replies made it hard to compare what Claude believes it delivered with what the owner can actually check.
- **Decision:**
  - Plans stay technical and detailed, for analysis.
  - Every delivery reply answers, in simple business language: what was built, why, the main goal, whether it is human testable or background only, and what to test.
  - Each ticket gets a "Business view" section with the same five points, so the report stays with the ticket.
- **Alternatives:** keep technical replies and rely on the verification table. Rejected: the table proves the criteria but doesn't tell a business tester what to do.

### D-068: Choices made while building the catalog domain (ECOM-002)
- **Date:** 2026-11-21
- **Status:** Accepted (owner, prompt #010). The point "a paid product can also be a gift" is superseded by D-083 (gifts are always free).
- **Decision:**
  - **Upper limits that match the database columns:** price up to 9,999,999,999.99 (`NUMERIC(12,2)`), stock up to 2,147,483,647 (`INTEGER`), weight up to 9,999,999.999 kg (`NUMERIC(10,3)`). A valid domain object can then always be saved; without the limits, an oversized value would pass the domain and fail in the database as a 500. The code is `too_large`, with `max` in `params`.
  - **`revise(...)`** changes several fields in one step and records one `ProductChanged`. The admin's full edit (PUT, ECOM-005) needs it: one save becomes one history entry, every issue is reported at once, and a price of 0 can be set together with the gift tag without worrying about order. The single-field behaviours in the ticket call `revise`.
  - **`restock(n)` adds `n` units** (n ≥ 1), as the word suggests. Setting an absolute stock level is `revise(stock=…)`.
  - **No-op changes record nothing**, so the history only shows real changes. Another spelling of the same category counts as no change and keeps the original spelling, matching "the canonical form is the first spelling seen". `archive` and `restore` are idempotent.
  - **Archived products can be edited but not sold.** The admin may fix a product before restoring it; `decrease_stock` on an archived product raises `ProductNotSellable` (reason `archived`), which becomes `product-not-sellable` at checkout.
  - **The SKU is immutable.** It is the identity used by the importer (§6.5); changing it means a new product.
  - **The domain does not touch `version`.** The repository increments it when it saves (ECOM-003), so several behaviours in one request still count as one version.
  - **Time is passed in** as `at` on every behaviour; the domain never reads a clock.
  - **Events carry plain values** (strings for money and weight, integers, sorted tuples for tags), ready to be written to `audit_log` as JSON.
  - **Programming errors are not validation errors.** A float, a boolean or text where a whole number is expected raises `TypeError`; a `decrease_stock` quantity below 1 raises `ValueError` (the order validates quantities first).
  - **Text rules:** a name rejects every control character (line breaks and tabs included); a description allows `\n` only, so a carriage return is rejected. Browsers' textareas already give `\n`.
  - **`IssueCollector`** joins the shared kernel: it runs each value-object constructor and keeps the issues instead of stopping at the first one. The CSV importer (ECOM-010) will reuse it.
- **Alternatives:** separate events per field on a full edit (rejected: one save would appear as up to seven history entries); `version` incremented by every behaviour (rejected: a two-field edit would jump two versions).

### D-069: Property tests and the coverage gate without new packages, for now
- **Date:** 2026-11-21
- **Status:** Superseded by D-070
- **Context:** ECOM-002 plans `hypothesis` property tests and a 95% domain coverage gate (`pytest-cov`). Adding the two dev packages was blocked by Claude Code's permission check, so it needs the owner's approval.
- **Decision (temporary):**
  - The property tests use the standard library's `random` with a fixed seed: 300 generated cases per property for SKU normalisation, price and stock, and 150 stock-decrease cases. They are deterministic, so a failure always reproduces.
  - Coverage is **not measured** yet. Every value-object rule and every behaviour has a test, but there is no number to show.
- **Next step:** if the owner approves, add `hypothesis` and `pytest-cov`, turn the seeded tests into hypothesis strategies, and add `--cov-fail-under=95` for the domain packages to `run.py backend`.

### D-070: hypothesis and pytest-cov adopted, with a domain coverage gate
- **Date:** 2026-11-21
- **Status:** Accepted (owner approved both packages in prompt #010)
- **Decision:**
  - Dev dependencies: `hypothesis` 6.170.17 and `pytest-cov` 7.1.0.
  - The seeded generators from D-069 became hypothesis strategies. A project profile in `testing/backend/conftest.py` runs 200 examples per property, with no deadline so a slow Windows run doesn't fail spuriously. The stock property now plays a random sequence of sales and restocks, which is stronger than one decrease.
  - `run.py backend` measures `catalog.domain` and `shared_kernel.domain` and fails below **95%** (§8.2). Each context's application layer joins the gate when it arrives, and the whole-backend 85% gate comes with ECOM-016.
  - `.hypothesis/` and `.coverage` are ignored by git and Docker.
- **Result:** 100% coverage of both domain packages.

### D-071: How products are stored (ECOM-003)
- **Date:** 2026-11-21
- **Status:** Accepted (owner accepted ECOM-003 in prompt #011). Supersedes "imperative mapping" in §4.1.
- **Context:** The ticket asked for SQLAlchemy imperative mapping of `Product`. `Product` keeps its state in private attributes and a frozen `ProductDetails` of frozen value objects. Imperative mapping would have to instrument the domain class itself (adding SQLAlchemy state to its instances and intercepting its attributes) and map every value object as a composite.
- **Decision:**
  - **Core tables with explicit translation.** `SqlAlchemyProductRepository` writes rows with `insert`/`update` and rebuilds `Product` through its normal constructor. The translation is about 40 lines, checked by mypy, and keeps the domain class untouched. The weather repository already works this way.
  - **The repository runs on the Unit of Work's session.** `CatalogUnitOfWork` (an application port) exposes `products`; `SqlAlchemyCatalogUnitOfWork` builds the repository on its session, so a use case commits or rolls back everything at once.
  - **Optimistic locking in one statement:** `UPDATE … WHERE id AND version = loaded … RETURNING version`. When no row matches, one extra read tells `ProductNotFound` from `VersionConflict(expected, current)`. On success the repository calls `Product.bump_version()`, so the caller holds the new version (ECOM-005 returns it).
  - **Duplicate SKUs** are caught inside a SAVEPOINT and raised as `DuplicateSku`, identified by the constraint name `uq_products_sku`. The transaction stays usable, which the CSV import will need.
  - **Schema:** tags as `varchar[]`; CHECKs for the four domain rules, plus known tags, known status and `version ≥ 1`; every constraint named. No currency column (USD only, CQ-06; adding one later is a migration). The downgrade also drops `pg_trgm`.
  - **`ecommerce/schema.py`** gathers every table for Alembic's `env.py`. A test compares the migrated database with the table definitions (Alembic's `compare_metadata`). Alembic doesn't compare CHECK constraints, so separate tests write invalid rows with direct SQL and assert each constraint by name.
  - **Test hygiene:** the shared Unit of Work tests now drop their scratch table when they finish, so it can't show up as schema drift.
- **Alternatives:** ORM imperative mapping (rejected for the reasons above); a hand-written SQL repository without SQLAlchemy Core (rejected: Core gives typed statements and the same engine as the rest of the app).


### D-072: Every ticket tests its failures, its retries and stock safety
- **Date:** 2026-11-21
- **Status:** Accepted (owner's instruction in prompt #011)
- **Context:** The owner asked that we never forget tests for the errors that can happen and the response each produces, that we always think about idempotency, and that we never sell products we don't have.
- **Decision:**
  - Every ticket gets a **"Failure cases and retries"** section before it is built, and tests for each line of it (§8.2):
    1. every failure and what the caller gets back (a domain error, or the HTTP status and Problem Details `type` once there is an endpoint); a raw database error or a 500 for a foreseeable case counts as a bug;
    2. what happens on a retry: no duplicate, no double sale, no double audit entry; a change that changes nothing creates no new version and no audit entry;
    3. for tickets that touch stock: stock never goes below zero, including under concurrent requests.
  - Applied to ECOM-003 straight away. Seven new tests: two buyers racing for the last unit (the second gets `VersionConflict` and the stock stays 0); a sale after the stock reaches 0 is refused; a sale larger than the stock changes nothing; an archived product can't be sold; a refused save can be retried after reloading; a retried create is refused; and the new error's own test.
  - **One bug found and fixed.** Adding the same product twice hit the primary key and escaped as a raw `IntegrityError`, which the API would have turned into a 500. It is now `ProductAlreadyExists`, raised inside the SAVEPOINT so the transaction stays usable.
  - Idempotency of the checkout itself (`Idempotency-Key`) and row locking for stock stay in ECOM-014, as designed in §7.2 and §7.3.
- **Alternatives:** leaving failure tests to ECOM-016 hardening (rejected: a missing error path is cheapest to find while the ticket is open, as the primary-key bug showed).

### D-073: How the audit trail is written (ECOM-004 plan)
- **Date:** 2026-11-21
- **Status:** Accepted (owner approved the plan in prompt #012)
- **Decision:**
  - **`audit_log`** with a bigint identity `id` for ordering, the §6.4 columns, JSONB `before`/`after`/`context`, and an index on `(entity, entity_id, id)`. A trigger blocks `UPDATE` and `DELETE`.
  - **The repository remembers the products it adds or saves; `commit()` turns their events into rows and inserts them** in the same transaction. Events of a product that was never saved are not logged. `save` skips a product with no pending changes, so a no-op creates no version and no entry.
  - **The actor is given when a unit of work is opened for a change.** Committing events without an actor is a programming error and rolls everything back.
  - **`X-Actor-Name` is percent-encoded UTF-8**, decoded by the backend, because browsers only send Latin-1 header values; plain ASCII names are unchanged. `Actor` is trimmed, 1–100 characters, no control characters.
  - **The header rule is tested on a route built inside the test**, since product change endpoints only arrive in ECOM-005; ECOM-005's contract test checks it on every real endpoint.
  - **`TRUNCATE` stays possible for the table owner** (the tests clean up with it). Blocking it in production needs a separate app role with `INSERT`/`SELECT` only on `audit_log`, noted for ECOM-016.
- **Alternatives:** use cases writing audit rows themselves (rejected: easy to forget one); a trigger on `products` writing the log (rejected: it can't know the actor or the order reference, and puts the logic in SQL); an `IN_PROGRESS`-style outbox (not needed: everything is one transaction); passing the actor to `commit()` (rejected: every change path would need to remember it, and a missed one would fail only at runtime).
- **As built (ECOM-004):**
  - **The repository takes a product's events when an `add` or `save` succeeds** and keeps them until `commit()`. It doesn't hold a reference to the product. A refused save leaves the events with the product, and a `rollback()` discards the kept ones. `Product.has_pending_events` tells `save` whether there is anything to write.
  - **The repository is created once per unit of work** in `__aenter__`. Before this, each `products` access built a new one, so it couldn't keep events.
  - **The event-to-entry mapping lives in `catalog/application/audit.py`.** It is pure code, so it joins the 95% coverage gate. `AuditEntry`, `AuditLog` (the reading port) and `ActorRequired` live in `shared_kernel/application/audit.py`. The table and the writer live in `shared_kernel/infrastructure/audit.py`, ready for the import and ordering contexts.
  - **Header errors say `location: "header"`.** `require_actor` raises `InvalidHeader`, which the Problem Details handler turns into the standard 422 body. `field_error_from_issue` gained a `location` argument.
  - **The trigger works per statement** (`FOR EACH STATEMENT`), so even an `UPDATE` or `DELETE` that matches no rows is refused.
  - **The API tests on the real database** run the app's lifespan and an `httpx.ASGITransport` client in the test's own event loop, so the engine and the app share one loop. The `engine` and `test_database_url` fixtures moved to `testing/backend/conftest.py`.
  - **The DB-outage row of the failure table** relies on the `OperationalError` → 503 mapping already tested in ECOM-001. The new test forces the audit insert to fail and proves that the change is not stored either.

### D-074: Delivery replies list every acceptance criterion with its result
- **Date:** 2026-11-21
- **Status:** Accepted (owner's request in prompt #012)
- **Context:** The owner said they couldn't see, in the delivery replies, which acceptance criteria were met and how.
- **Decision:** Every delivery reply includes a table of the ticket's acceptance criteria with the result of each (Pass, or what is missing) and one plain line on how it was proven. It comes right after the business view (D-067). The ticket's "Verification" section holds the same table with the technical detail, and the failure table (D-072) shows a result per row.
- **Alternatives:** linking to the ticket only (rejected: the owner wants to see it in the reply).

### D-075: Product API choices (ECOM-005)
- **Date:** 2026-11-21
- **Status:** Accepted (owner tested ECOM-005 in Swagger and accepted it in prompt #014)
- **Decision:**
  - **The zero-price code stays `zero_price_requires_gift`.** The ticket and §4.3 said `zero_price_requires_gift_confirmation`, but §4.6, the domain (ECOM-002, D-068) and its tests already used the shorter name. One name everywhere was more important than which one; the ticket and §4.3 now match the code. Renaming it is a one-line change if the owner prefers the longer one.
  - **Every change returns the product.** `POST` gives 201 with a `Location` header; `PUT`, `DELETE` (archive) and restore give 200 with the body rather than 204. The screen always has the new `version` without a second request.
  - **`PUT` has no `sku`.** The SKU is the product's identity (§6.5), so sending it is refused as an unknown field rather than silently ignored.
  - **A retried PUT is idempotent.** If the version is stale but applying the request would change nothing, the request returns 200 with the current product. That is what a retry after a timeout looks like, and no one's change is lost. If it would change something, the request gets 409 as before.
  - **Strict JSON types for `stock`, `version` and `gift`.** `"10"`, `1.5` or `true` as a stock, or `"yes"` as a gift, give 422. Lax parsing would have turned `true` into 1, or crashed the domain's own type checks with a 500.
  - **Search reads go straight to SQL** through a `ProductQueries` port (`SqlAlchemyProductQueries` on the engine). They are read-only and need neither the aggregate nor a unit of work.
  - **The search defaults to `status=ACTIVE`.** The storefront then can't show archived products by accident; the admin asks for `ALL` or `ARCHIVED`.
  - **Pages are stable.** Every sort is tie-broken by id. `page` is capped at 100,000 and `q` at 200 characters, as abuse limits.
  - **A minimum price above the maximum is a 422 in the query** (`invalid_range`), raised where the parameters are read. Header and query errors share `InvalidParameters`, which carries its location.
  - **Problem mappings can add a `detail` and extra fields.** That gives `current_version` on `version-conflict` and `sku` on `duplicate-sku`.
  - **The contract test is generated from the OpenAPI document,** so a new endpoint is covered automatically. Another test fails if any endpoint that takes input has no bad-input case.
  - **`X-Actor-Name` is now declared required** (ECOM-004 checked it only after FastAPI). Swagger marks it as required, and a missing name is reported together with any body errors in one 422. A blank or invalid name still gets the specific messages from `Actor`.
- **Alternatives:**
  - 204 on DELETE (rejected: the client would need another GET for the version).
  - Ignoring `sku` in a PUT (rejected: a silent no-op hides client bugs).
  - Always 409 on a stale version (rejected: a retry after a timeout would show a false conflict).
  - Search through the repository (rejected: it would load whole aggregates for a read-only list).

### D-076: Frontend foundation plan (ECOM-006)
- **Date:** 2026-11-21
- **Status:** Accepted (owner approved the packages in prompt #015). The ESLint part is superseded by D-077. The package ages were wrong; corrected by D-079.
- **Context:** ECOM-006 needs the libraries chosen in §5. Adding packages needs the owner's explicit approval.
- **Decision (proposed):**
  - **Runtime packages:** `@tanstack/react-query`, `react-router`, `react-hook-form`, `zod` and `@hookform/resolvers`.
  - **Dev packages:** `msw`, `eslint`, `@eslint/js`, `typescript-eslint`, `eslint-plugin-react`, `eslint-plugin-react-hooks`, `globals` and `prettier`.
  - Every package is pinned exactly at install time, at a version at least two weeks old.
  - **One `ApiError`** for every failed call: Problem Details, an error response that isn't Problem Details, and network failures.
  - **Change functions take the actor as an argument**, so a change without a name doesn't compile. The name is percent-encoded.
  - **Queries retry up to twice, only on network errors and 5xx. Mutations never retry automatically** (D-072): a repeated change must be a person's decision.
  - **The weather page moves to `/weather`** until ECOM-009, so the smoke test keeps passing.
  - **The reviewer's name lives in `localStorage`, with an in-memory fallback** when storage is blocked.
- **Risk:** the project uses TypeScript 7 (the native compiler), and `typescript-eslint` may not support it yet. The fallback is ESLint without type-aware rules, still enforcing `react/no-danger` and the hooks rules; `tsc --noEmit` keeps doing the type checking.
- **Alternatives:** a hand-written fetch cache instead of TanStack Query (rejected: loading, error, retry and invalidation logic is exactly what the library provides, and §5 chose it); retrying mutations with the backend's protections as a safety net (rejected: the owner wants retries to be deliberate).

### D-077: A raw-HTML check instead of ESLint, while TypeScript 7 lacks ESLint support
- **Date:** 2026-11-21
- **Status:** Accepted (owner chose option A, keep the raw-HTML check, in prompt #016)
- **Context:**
  - ECOM-006 planned ESLint with `react/no-danger`.
  - At install time, the newest `typescript-eslint` (8.73.0) declared support for TypeScript `>=4.8.4 <6.1.0`. The project uses TypeScript 7 (the native compiler), whose package no longer ships the JavaScript compiler API that `typescript-eslint` needs to parse `.tsx`.
  - `eslint-plugin-react` 7.37.5 supports ESLint up to 9.
  - Without a TypeScript parser, ESLint can't read any of our files.
- **Decision:**
  - **Don't install the ESLint packages for now.** Installing them would mean forcing peer dependencies that the authors say don't work.
  - **`testing/scripts/check_no_raw_html.py`** enforces the purpose of `react/no-danger`, and a bit more. It refuses `dangerouslySetInnerHTML`, `.innerHTML`, `.outerHTML`, `insertAdjacentHTML`, `document.write(ln)` and `createContextualFragment` in `frontend/src`. It runs in `run.py lint`, with 13 tooling tests, like the no-comments check.
  - **Prettier** (approved) checks the format. `tsc --noEmit` in strict mode keeps doing the type checking.
  - **Revisit** when `typescript-eslint` supports TypeScript 7. That is a small ticket: add the packages, a flat config, and a lint step.
- **What is lost meanwhile:** the React hooks rules (hooks called conditionally, missing effect dependencies) and general lint rules. The code reviews and the tests cover them for now.
- **Alternatives:**
  - Downgrade to TypeScript 5.9 (rejected: a project-wide change for a linter).
  - Force the peer dependencies (rejected: unsupported, and likely to break).
  - `@babel/eslint-parser` with the TypeScript preset, or oxlint (not approved packages; offered to the owner as options).

### D-078: Admin product screens (ECOM-007)
- **Date:** 2026-11-21
- **Status:** Accepted (owner accepted ECOM-007 in prompt #020)
- **Decision:**
  - **The table keeps its search, status and page in the address** (`?q=…&status=ALL&page=2`), so a refresh or a shared link shows the same list.
  - **The browser checks only the obvious things** (required fields, the number formats). The server stays the authority, and its 422 messages land on the fields.
  - **The gift dialog sends nothing until the admin answers.** "Yes" saves with `gift: true`; "No" returns to the price field.
  - **The edit form keeps the version it was opened with.** A refresh in the background (after another change in the app) updates the page, but never the version the form sends. Only **Reload** rebuilds the form with the newest version. The first design rebuilt the form whenever the version changed. A test showed two consequences: the save lost its "back to the table" step, and a background refresh could have made the form send a newer version, silently overwriting someone else's change.
  - **Handled problems don't pop up twice.** The form mutations declare `meta.handledProblems` (`duplicate-sku`, `version-conflict`), so those appear only on the form (the SKU field, or the reload banner). Every other failure still goes to the notifications.
  - **After a change, every cached product list is refreshed** (`refetchType: 'all'`) before the admin is sent back, so the table never flashes the old values.
  - **Archiving asks for confirmation; restoring doesn't.** Archiving hides a product from the shop, while restoring undoes that.
  - **Times on the history page are shown in UTC,** labelled as such, so every admin reads the same time.
- **Alternatives:**
  - Rebuilding the form on every version change (rejected, see above).
  - A browser `confirm()` for the gift question (rejected: it can't be styled or tested well, and its wording can't be controlled).
  - Local time on the history page (rejected for now: admins in different time zones would see different times).

### D-079: Package ages corrected
- **Date:** 2026-11-21
- **Status:** Accepted (correction of D-076, reported to the owner in prompt #016)
- **Context:** In ECOM-006 the versions were chosen with `npm view <package> version --before 2026-11-07`, and reported as at least two weeks old. While checking the coverage package for ECOM-007, the publish dates turned out not to match. npm ignored `--before` for `view` and returned the newest versions. Six of the seven packages were between 1 and 10 days old.
- **Decision:**
  - Repinned to the newest stable release published on or before 2026-11-07, read from `npm view <package> time`: `@tanstack/react-query` 5.107.1, `react-router` 8.5.1, `react-hook-form` 7.91.0, `@hookform/resolvers` 7.0.3, `msw` 3.0.4, `prettier` 3.9.10 (`zod` 4.6.7 already qualified).
  - The full CI suite passes on these versions.
  - From now on, a version's age is checked against its publish date in `npm view <package> time`, never with `--before`.
- **Note:** Vitest 5.1.1 (from ECOM-000) was published on 2026-11-18. It predates the two-week rule and was left alone. It matters again for the coverage package (ECOM-007), which must match Vitest exactly.

### D-080: Bug: the edit form could overwrite another admin's change (found by a test, ECOM-007)
- **Date:** 2026-11-21
- **Status:** Fixed (logged at the owner's request in prompt #017)
- **How it was found:** the first edit test failed when the whole file ran. After a save, the app stayed on the edit page instead of returning to the table.
- **Cause:**
  - The edit form was tied to the product's version, and rebuilt itself whenever the version changed.
  - After a save, the refreshed product had a new version, so the form was rebuilt mid-save. The library then dropped the "go back to the table" step, which belonged to the old form.
  - Worse, the same tie meant that a refresh in the background while an admin was editing would hand the form a newer version. The save would then send that newer version, pass the conflict check, and **silently overwrite someone else's change**. That is the lost update the whole design guards against (§7.3, D-071).
- **Fix:**
  - The form keeps the product and version it was opened with.
  - Only the **Reload** button (after a conflict) rebuilds it, by bumping a counter on the page, not the version.
- **Guard:** the test "never overwrites a change made by someone else, even after a background refresh" (`testing/frontend/adminProducts.test.tsx`). It refreshes the page's data in the background, saves, and expects the conflict banner, version 1 sent, and the other change intact. With the old code put back on purpose, this test fails.

### D-081: Bug: "Something unexpected went wrong" after creating or editing a product (found by the owner, ECOM-007)
- **Date:** 2026-11-21
- **Status:** Fixed; waiting for the owner's re-test ([evidence](../tasks/ECOM-007-evidence/README.md), DEF-01)
- **Symptom:**
  - In the browser, a red "Something unexpected went wrong" appeared next to "Product created".
  - Two appeared after a gift was created, and one more after an edit. The data itself was saved correctly.
- **Cause:**
  - After a save, the app put the server's answer into the cache under `['products', 'detail', id]`. For a new product, no screen had ever loaded that entry.
  - Next, it refreshed every cached product query (`refetchType: 'all'`, added during ECOM-007 so the table never flashes old values). The new entries had no instruction for loading themselves, and each refresh failed with TanStack Query's internal "Missing queryFn" error.
  - Every product created in the session added one more failing entry, which is why the count grew.
- **Why the tests missed it:** they asserted that the success message appeared, never that no error appeared. The temporary check against the live backend was run from the edit page, where that product's entry did have a loader.
- **Fix:**
  - After a save, the app refreshes only the product lists (`['products', 'list']`, all of them), that product's history and the categories. The saved product's own entry comes straight from the server's answer, so nothing needs to reload it.
  - Errors that aren't API problems are now logged with `console.error('Unexpected error', …)`.
- **Guards:**
  - A regression test replays the owner's run (create, create a gift through the dialog, edit) and requires 3 success messages and no error.
  - `testing/frontend/setup.ts` now fails **every** frontend test in which the app logs an unexpected error.
  - With the old refresh put back on purpose, 7 tests fail on "Missing queryFn"; with the fix, all 72 pass.

### D-082: Test evidence is stored per ticket; UI polish gets its own ticket
- **Date:** 2026-11-21
- **Status:** Accepted (owner's request in prompt #017)
- **Decision:**
  - The owner's test screenshots and recordings go into `tasks/<KEY>-evidence/`, with a `README.md` written like a Jira test record: environment, steps with expected and actual results, defects (cause, fix, status), observations and a re-test checklist. ECOM-007's evidence is the first.
  - The owner's UX remarks go into a new backlog ticket, **ECOM-018 (UI polish and user experience)**:
    - the drop-downs look off;
    - the table is cramped on a narrow window;
    - notifications cover the content;
    - a duplicate SKU should show the product that already uses it.

    The owner asked for these to be addressed when the UI gets its own focus, not now.

### D-083: Gifts are always free (owner's change request, CR-01)
- **Date:** 2026-11-21
- **Status:** Accepted (owner chose it in prompt #018). Supersedes the "paid gift" point of D-068.
- **Context:** In the browser test, the owner created SP-003 "Normal shoes" at $55 with the Gift box ticked, and said a gift with a price makes no sense.
- **Decision:** a product is a gift **if and only if** its price is 0.
  - **Domain:** `gift_rule_issue` reports `zero_price_requires_gift` (price 0 without the tag, as before) and the new `gift_must_be_free` (the tag with a price above 0). The issue goes on `price` when the price changed or on create, and on `gift` otherwise, the same as the existing rule. `mark_as_gift` on a paid product is refused; making a product a free gift is one `revise(price="0", gift=True)`.
  - **API:** 422 `validation-error`, code `gift_must_be_free`, field `price`.
  - **Database:** the `CHECK ((price = 0) = ('GIFT' = ANY(tags)))`, named `ck_products_gift_if_and_only_if_free`, replaces `ck_products_zero_price_requires_gift`.
  - **Existing data:** migration 0004 removes the Gift tag from paid products. Each one's version goes up by one, and an audit entry is written in the same statement: actor "Data migration", `product.changed`, tags `["GIFT"]` → `[]`, context `{"migration": "0004", "reason": "Gifts must be free (D-083)."}`. The price is kept: the owner's intent was to sell the product, not to give it away. On the live database this changed SP-003 only.
  - **Form:** "Free gift (gifts are always priced at 0)" is the first option. Ticking it sets the price to 0 and makes the field read-only, with the hint "Gifts are always free."; unticking brings the previous price back. The form also refuses a paid gift itself, as a safety net.
- **Tests:**
  - domain: a paid gift is refused on create, on `ProductDetails`, on reprice and on `mark_as_gift`; making a product a free gift and turning a gift into a paid product each record one change;
  - API: paid gift refused on create and on edit;
  - database: the constraint refuses a paid gift row;
  - migration: a downgrade to 0003, a paid gift and a free gift inserted, then an upgrade. Only the paid one loses the tag, with exactly one audit entry;
  - frontend: the gift option comes first, locks the price, and unticking restores it; the server's refusal appears on the price field.
- **Alternatives:**
  - Deleting paid gifts (rejected: destroys data).
  - Setting their price to 0 (rejected: would give away a product the owner meant to sell).
  - Refusing the migration until someone fixes the data by hand (rejected: one clear, audited rule is simpler and leaves a trace).

### D-084: Error log: DEF-01 "came back" because the browser tab was still running the old code (DEF-02)
- **Date:** 2026-11-21
- **Status:** Fixed (logged at the owner's request in prompt #018)
- **The error:** after the DEF-01 fix was deployed, the owner created SP-02 and still saw two red "Something unexpected went wrong" messages next to "Product created".
- **What created it:**
  - Not the code: the fix was live (the served bundle `index-CfDpcUSZ.js` contains it).
  - The frontend server's access log shows the owner's browser posting the products at 19:09:53 and 19:11:13 UTC without ever downloading the new bundle after the 18:53 rebuild. The only download of it was our own `curl` at 19:12:04; the `GET /` every 5 seconds is Docker's health check (`Wget`).
  - A single-page app loads its code once per tab, so the tab kept running the old code, DEF-01 included.
  - Contributing: nginx sent no `Cache-Control` header, so even a refresh could reuse an old copy of the page.
- **Fix:**
  - nginx sends `Cache-Control: no-cache` for the page and all app routes, and `public, max-age=31536000, immutable` for `/assets/` (hashed file names).
  - The smoke test gained "the page is never served stale", which checks both on every CI run.
  - ECOM-018 gets a "new version available — reload" banner, so a long-open tab can tell the admin.
- **How to diagnose next time:** compare the bundle the server serves with the bundle requests in the frontend log (`docker compose logs frontend`), before changing any code.

### D-085: Every frontend test checks the whole page for errors
- **Date:** 2026-11-21
- **Status:** Accepted (owner's request in prompt #018: "Every test, get the whole body to check if any error message appears")
- **Decision:** `testing/frontend/setup.ts` checks the page when each test finishes, and fails the test if:
  - the body contains "Something unexpected went wrong";
  - the notification area holds a red notification, unless the test called `expectErrorNotifications()` first (8 tests do, because causing an error is their purpose);
  - the app logged `Unexpected error` to the console (from D-081).
- **Found by the new check:** the "Product not found" pages also popped up a red "The resource was not found." notification. Queries can now declare `meta.handledProblems` like mutations, and the product and history pages declare `not-found`.

### D-086: Frontend coverage gate at 80% (Vitest 5.1.0 and @vitest/coverage-v8 5.1.0)
- **Date:** 2026-11-21
- **Status:** Accepted (owner approved in prompt #019: "Yes, move it")
- **Decision:**
  - `@vitest/coverage-v8` 5.1.0 is added, and Vitest moves from 5.1.1 to 5.1.0. The coverage package must match Vitest exactly, and 5.1.1 was only 3 days old. Both were published on 2026-11-02, checked with `npm view <package> time` (D-079).
  - `vite.config.ts` measures `src/**` (except `main.tsx`) with thresholds of 80% for lines, statements, functions and branches. `run.py frontend` now runs `npm run test:coverage`, and a tooling test checks that.
  - **First measurement:** statements 95.72%, branches 89.23%, functions 96.31%, lines 95.81%.
- **npm problem met on the way:**
  - Both `npm install` and a clean install failed inside npm's own peer-dependency resolver (npm 10.9.3, "Cannot read properties of null (reading 'edgesOut')").
  - While resolving optional peers, npm reached for the newest Vitest (5.1.1) and its `@vitest/browser-playwright` peer, which clashed with the pinned 5.1.0.
  - **Fix:** `"overrides": { "vitest": "5.1.0" }` in `frontend/package.json`. The `$vitest` reference form doesn't work for dev dependencies.
  - The lock file had to be rebuilt from scratch. All direct dependencies stay pinned to their exact versions; only the packages they depend on were re-resolved, and those had already been resolved to their newest versions earlier the same day.
  - The full CI suite passes on the new lock file.

### D-087: The shop's search page and a minimal cart (ECOM-008)
- **Date:** 2026-11-21
- **Status:** Accepted (owner tested and accepted ECOM-008 in prompt #021)
- **Decision:**
  - **The whole search lives in the URL:** `q`, `category`, `min_price`, `max_price`, `in_stock`, `tag`, `sort` and `page`. Only values that differ from the defaults are written, so links stay short. Values that can't be valid (a page that isn't a number, an unknown sort or tag, a negative or non-numeric price, or a minimum above the maximum) are dropped and the defaults used, so a hand-edited link never shows an error page.
  - **The shop always asks for `status=ACTIVE`.** Archived products never appear in the list. Their product page still opens (old links keep working) but says "This product is no longer available", with the button disabled.
  - **The text filters apply on Search; the lists and check boxes apply at once.** Price fields are checked before anything is sent.
  - **A minimal cart now,** so "cannot be added to the cart" can be proven. It is kept in `localStorage` (`ecommerce.cart`), as §5 plans, with an in-memory fallback, and the header shows "Cart: N items". It never holds more than the stock shown: a click at the limit is refused, and the button says "Only N in stock". The cart page and checkout come in ECOM-015, and the server re-checks stock with row locks at checkout (ECOM-014, §7.3).
  - **Gifts show "Free"** instead of $0.00, next to the Gift badge.
  - **12 products per page,** which fits a grid of 3 or 4 columns.
  - **Read hooks are shared:** `src/api/productQueries.ts` serves both the shop and the admin area.
- **Alternatives:**
  - Searching on every keystroke (rejected for now: an explicit Search is simpler to test and sends fewer requests; it can move to ECOM-018).
  - Hiding archived product pages with a 404 (rejected: an old shared link would look broken instead of explaining).

### D-088: Removing the weather feature (ECOM-009)
- **Date:** 2026-11-21
- **Status:** Accepted (owner accepted ECOM-009 in prompt #022)
- **Decision:**
  - **Deleted:**
    - the `weather` context (domain, application, infrastructure, API);
    - its Open-Meteo client and settings (`open_meteo_*_url`, `http_timeout_seconds`);
    - the page at `/weather`, its API client;
    - its 5 test files and its fakes;
    - its import-linter contract (5 contracts become 4).
  - **Migration 0005** drops `weather_searches` and its index. Its downgrade recreates them exactly as 0001 made them, so the history stays reversible.
  - **The only remaining mentions** are the migration history (0001 creates the table, 0005 drops it) and the migration tests that check it. Rewriting history would break existing databases.
  - **`httpx` moved to the development dependencies.** Production code no longer calls out to anything; the tests still use it (TestClient, ASGITransport). The lock file changed only in that grouping.
  - **The shared error tests no longer lean on the weather endpoint.** The 7 problem-details tests that used it as a convenient target now use small routes built inside the test, and every check is kept.
  - **`upstream-unavailable` (502) stays in the problem catalog** for the real payment provider (§7.2). A test route that raises a 502 keeps it covered.
  - **The smoke test now goes through the catalog, and it is idempotent.**
    - It creates `SMOKE-TEST` once; later runs get the expected 409 `duplicate-sku` and reuse the product.
    - Before reusing it, the test checks the stable smoke name, description and category. A coincidental merchant product with that SKU makes the check stop; it is never restored or archived.
    - It then restores the product, finds it by search, archives it, and checks that it has left the shop.
    - The live database therefore holds exactly one archived "Smoke test product" (in the "Smoke tests" category, visible in admin under Status: All), whose history grows by two entries per run.
- **Alternatives:**
  - A new product per smoke run (rejected: it would fill the owner's database with test products).
  - A read-only smoke test (rejected: the ticket asks for a real create-and-find through the proxy).
  - Removing `upstream-unavailable` (rejected: checkout with a real provider will need it).

### D-089: Code review round 1 for ECOM-000 through ECOM-009
- **Date:** 2026-11-21
- **Status:** Accepted (review and fixes requested by the owner)
- **Scope:** every developed ticket, ECOM-000 through ECOM-009. The review checked each ticket against its acceptance criteria and failure table, inspected the architecture boundaries and migrations, and ran the complete quality suite.
- **Results by ticket:**
  - **ECOM-000:** container topology, proxy, database bootstrap and runner reviewed; no new defect found.
  - **ECOM-001:** shared errors, request IDs, validation conversion, logging and quality gates reviewed; no new defect found.
  - **ECOM-002:** product value objects, aggregate invariants, stock behavior and property tests reviewed; no new defect found.
  - **ECOM-003:** product schema, repository, optimistic locking and Unit of Work reviewed; no new defect found.
  - **ECOM-004:** audit mapping, transaction coupling and append-only database trigger reviewed; no new defect found.
  - **ECOM-005:** CRUD/search schemas, problem mappings, literal wildcard search, paging and API contract reviewed; no new backend defect found.
  - **ECOM-006:** client error parsing, retry rules, actor encoding/storage, routing and page-wide error guard reviewed; no new defect found.
  - **ECOM-007:** fixed an out-of-range admin page that could show a blank table. It now moves to the last real page after the response; regression test added.
  - **ECOM-008:** fixed the same out-of-range behavior in the shop; regression test added.
  - **ECOM-009:** fixed unsafe ownership by SKU in the idempotent smoke test. It now refuses to mutate a product unless its stable smoke identity also matches; two tooling tests added.
- **Why page correction waits for the real response:** TanStack Query keeps the previous page temporarily while a new request is running. Correcting against placeholder data could redirect using the old search's page count, so both screens wait for `isPlaceholderData` to be false.
- **Verification:** `python testing/run.py all` passed: all static and architecture checks, 36 tooling tests, 467 backend tests with 100% scoped coverage, 89 frontend tests with 96% line coverage, and every smoke check. The production frontend image also built successfully, the local stack is healthy, and the smoke checks passed again after deployment.

### D-090: CSV import, part 1: preview and classification (ECOM-010)
- **Date:** 2026-11-21
- **Status:** Accepted (owner tested the whole import in the portal, prompts #028 and #029)
- **Decision:**
  - **The sample was re-verified before any code.** `profile_csv.py` confirmed every format fact in §2: UTF-8 without BOM, CRLF, no final newline, 97 data rows, blank lines 62–63, and the RS-001 and BS-021 duplicates. `simulate_import.py` then reproduced the expected report exactly: 84 create, 6 review, 2 rejected, 3 superseded, 2 blank and 3 warnings. A first look with Git Bash's `sed` had suggested LF line endings; that was wrong, because `sed` strips carriage returns before showing them. The script reads the raw bytes.
  - **The rules live in the domain** (`catalog/domain/importing/`), as pure functions over strings. Field checks reuse the product's own value objects and translate their codes into the §6.2 taxonomy (`markup_not_allowed` → `markup_in_name`, `too_small` → `negative_value`, and so on), so a product rule exists in one place only. The import adds only what the value objects can't know: currency symbols, `free`, whole numbers written as `12.0`, and the empty/zero review policies.
  - **The identity check** uses a pure-Python trigram similarity built the same way as `pg_trgm`, checked against PostgreSQL's documented value (`similarity('word', 'two words') = 0.363636`), after NFKC, case-fold and whitespace normalisation.
  - **ECOM-010 ships a read-only preview,** `POST /api/v1/imports/preview`. Stored batches and the review come in ECOM-011. The owner can already try the classification in Swagger, and nothing is ever written.
  - **The file is the request body (`text/csv`), not a multipart form.** FastAPI needs the `python-multipart` package for form uploads, and adding a package needs the owner's approval; the raw body needs nothing extra. Swagger still shows a file picker. ECOM-011's `POST /imports` can use either.
  - **File-level errors:**
    - 413 `payload-too-large` (with `max_bytes`; the body stops being read once it passes the limit);
    - 415 `unsupported-media-type`;
    - the 422 cases are the standard `validation-error` with one entry on the field `file` (`invalid_encoding`, `empty_file`, `missing_columns`, `duplicate_columns`, `too_many_rows`, `malformed_csv`), so the frontend's existing form-error handling shows them without any new code.
  - **Accepted media types:** `text/csv`, `application/csv` and `application/vnd.ms-excel`. Windows browsers label `.csv` files with the last one.
  - **Codes for policy variants not named in §6.2:**
    - `sku_already_exists` (`create_only`);
    - the warning `zero_price_accepted_as_gift` (`accept_as_gift`);
    - the review codes reused as errors by the `reject` variants;
    - `duplicate_sku_in_file` as an error under `reject_all`;
    - `unsupported_currency` when the `$` is refused.
  - **Settings** are read by `ImportSettings` (prefix `IMPORT_`, as in §6.3), plus `IMPORT_SKU_SIMILARITY_THRESHOLD`. Pydantic validates them at start-up, so a typo stops the backend with the setting's name instead of silently using a default.
  - **Fixtures are byte-exact:** `.gitattributes` marks `testing/fixtures/**` as `-text`, because the repository-wide LF normalisation would otherwise rewrite the CRLF, BOM and Latin-1 test files.
  - **`same_file_already_pending`** needs stored batches, so it moves to ECOM-011.
- **Alternatives:**
  - Multipart now (rejected: a new package without approval).
  - Classifying in the database with SQL `similarity()` (rejected: the rule couldn't be unit-tested without PostgreSQL, and the preview would need a round trip per row).
  - Separate import-only validation rules (rejected: two copies of the product rules would drift apart).

### D-091: CSV import, part 2: review workflow, commit and audit (ECOM-011)
- **Date:** 2026-11-21
- **Status:** Accepted (owner tested the whole import in the portal, prompts #028 and #029)
- **Context:** the owner asked to commit ECOM-010 and close ECOM-011 and ECOM-012 together, so the whole import can be tested in the admin portal (prompt #026).
- **Decision:**
  - **Upload stays a raw `text/csv` body.** The owner didn't answer the `python-multipart` question, and a package needs explicit approval, so `POST /imports` takes the file exactly like the preview; the name travels in the `file_name` query parameter. The browser sends the chosen file as the body, so the portal needs no extra package either. §4.5 said "multipart"; it is updated.
  - **`ImportBatch` is a catalog aggregate** stored in `import_batches` and `import_batch_rows` (migration 0006). Each row keeps its raw line and raw values unchanged; the current values, outcome, issues, normalised product, field diff, target product and version, decision and resolution history are JSONB beside them. Batches are never deleted.
  - **What each row allows** (the API returns it as `actions`, so the screen never guesses):
    - a row held for review: `confirm` only when every review issue is a zero price or a zero weight; `correct` and `skip` always;
    - a row that started in review stays correctable after it moved (the reviewer can fix their own mistake);
    - an update that needs confirmation: `confirm` or `skip`, and either can replace the other;
    - create, unchanged, rejected, superseded and blank rows: nothing. A rejected row gets 409 `import-row-not-resolvable` (D-037).
  - **Confirming and correcting re-run the ECOM-010 rules** for that row, against the product that holds its SKU now. A confirmed zero price becomes a gift; a confirmation is remembered, so later corrections keep it. A correction that would be rejected is refused with a 422 on the columns and changes nothing; reusing another active row's SKU is `duplicate_sku_in_file`.
  - **Retries are safe everywhere:** confirming, skipping or sending the same correction twice records nothing new; committing a committed import returns it unchanged (200); discarding twice returns 200.
  - **Commit is one transaction:**
    - it locks the batch row first, then the products `FOR UPDATE` in SKU order (§4.4);
    - a create row whose SKU now exists, or an update row whose product version moved, is stale;
    - stale rows are checked again against the current product, lose their decision, get the warning `changed_since_preview`, and are saved; the commit then answers 409 `import-stale-rows` with the lines, and **no product is changed**.
  - **Expiry is computed:** a batch older than 24 hours reads as `EXPIRED`, and the first change attempted after that stores the status. Every change to a batch that is not pending answers 409 `import-not-pending`; its extra field is `import_status`, because `status` is already the problem's HTTP status.
  - **Audit:** `import.started`, `import.committed` and `import.discarded` on `import_batch`; `import.row.confirmed`, `import.row.corrected` and `import.row.skipped` on `import_row` (`<batch id>:<line>`), with the values before and after and the original issues. Products created or updated by a commit carry `{source, batch_id, line, file_sha256, raw}` in their entries' context, and a product's history now starts with its row's resolutions, then the creation with the raw CSV line (§6.4).
  - **Honesty about TDD:** for this ticket the tests were written right after each part of the code, not before it, to close two tickets in one session. Every acceptance criterion and failure case has its own test.
- **Alternatives:**
  - Sending a stale row literally to `needs_review` (rejected: it is not a review issue under D-037; a fresh diff that must be confirmed again is what the reviewer needs).
  - Returning the whole batch after every row change (rejected: up to 10,000 rows per click; the PATCH returns the row and the batch summary).
  - A background job for expiry (rejected: nothing to run on; reading the status at request time is exact).

### D-092: CSV import screens (ECOM-012)
- **Date:** 2026-11-21
- **Status:** Accepted (owner tested the whole import in the portal, prompts #028 and #029)
- **Decision:**
  - **Two screens under the admin area:** `/admin/imports/new` (choose a file, "Upload and check") and `/admin/imports/:id` (the review). The admin menu gains **Import CSV**. Both need the reviewer name, like every admin change.
  - **The browser sends the chosen file itself as the request body** (`Content-Type: text/csv`, `file_name` in the query), so the bytes reach the server untouched and its encoding check still works. No new package (D-091).
  - **The review screen follows the server, never guesses:**
    - one tab per outcome plus **Warnings**, each with its count from the server's summary; it opens on the first tab that needs work (review, then updates, then new);
    - buttons come from each row's `actions`: a review row has an editor with every column, **Save correction** (only the changed values are sent), **Confirm as free gift** or **Confirm weight 0** when allowed, and **Skip this row**;
    - an update shows a Now → After table and a **Confirm this update** checkbox; clearing it skips the row; **Confirm all N updates** confirms the rest one by one;
    - rejected rows show their reasons and raw line, with no editor;
    - after each decision, the row and the counts are replaced from the server's answer, so a corrected row moves to its new tab at once.
  - **Commit:** the button stays disabled until the server says the import is committable, and the hint lists the lines still waiting. A 409 is explained on the page, never as a generic pop-up: stale rows ("Nothing was imported. The rows on lines … now show the latest changes; confirm them again"), rows still pending, or an import no longer pending. After any refused commit the import is reloaded, so the screen shows the fresh diffs.
  - **Discard** asks for confirmation first. Committed, discarded and expired imports show a banner and no commit button.
  - **Product history** names the import events ("Corrected during import review"…) and the import context (CSV line, raw CSV line, import, file SHA-256).
  - **Update cards keep their identity between decisions** (keyed by line), so the checkbox doesn't lose focus; review cards are rebuilt after a decision so the editor shows the row's new values.
- **Alternatives:**
  - A "Confirm all" that skips the confirmation per row (rejected: no bulk endpoint; one request per row keeps every decision audited separately, which the audit trail requires).
  - Upload by reading the file as text in the browser (rejected: a non-UTF-8 file would be silently re-encoded and the server's `invalid_encoding` check would never fire).

### D-093: Code review round 2 for ECOM-010 through ECOM-012
- **Date:** 2026-11-21
- **Status:** Accepted (review and fixes requested by the owner)
- **Scope:** ECOM-010, ECOM-011 and ECOM-012, reviewed together because the parser, stored review workflow and portal form one import path.
- **Results by ticket:**
  - **ECOM-010:** the parser, classification policies, golden sample and file-level API errors were rechecked; no new defect was found in its domain or API code. The unsupported-media-type path exposed an ECOM-012 client defect described below.
  - **ECOM-011:** fixed an outcome-changing confirmation retry. A confirmation now carries `expected_outcome`; if the row has since moved from `needs_review` to `update`, retrying the old command cannot approve the update. It remains pending for an explicit review.
  - **ECOM-011:** fixed locking for a new SKU. Row locks cannot protect a key that does not exist, so product adds and import commit checks now share transaction-scoped PostgreSQL advisory locks keyed by SKU and acquired in sorted order.
  - **ECOM-012:** fixed uploads overwriting every selected file's media type with `text/csv`. The client preserves a browser-supplied type and uses `text/csv` only when it is empty, allowing the backend's 415 validation and the page's explanation to work.
- **Why `expected_outcome` is part of a confirm command:** idempotency must identify the state the user approved, not only the action name. The same `confirm` action can otherwise mean approving two materially different states after reclassification.
- **Why advisory locks are shared by ordinary creates and imports:** locking only the import path would not exclude an admin create. Every writer of a SKU must participate in the same lock protocol for an absent key to be protected.
- **Verification:** the focused import frontend suite passed 35 tests; the backend suite passed 725 tests with 99.61% scoped coverage. The complete quality run is recorded in the ticket and prompt history.

### D-094: Skipped import rows get their own tab (owner's change request, ECOM-012 CR-01)
- **Date:** 2026-11-22
- **Status:** Accepted; verified by the owner's re-test in prompt #029
- **Context:** the owner tested ECOM-010 to ECOM-012 in the portal and imported the sample: 88 created, 1 updated, 1 skipped ([evidence](../tasks/ECOM-012-evidence/README.md)). A skipped row stayed in **Needs review** with a "Skipped" label and its editor, and a cleared update stayed in **Updates**. The owner: "I believe those which we skipp should dissapear from screen [...] I mean dissapeared from the review screen, we can have a tab for them." This was the design of D-092, not a defect, so it is recorded as a change request.
- **Decision:**
  - A new **Skipped** tab sits between **Unchanged** and **Rejected**, so the tabs read: what will be imported, then what won't.
  - A row whose decision is `skipped` leaves its outcome tab (Needs review, Updates or New) and is listed only under **Skipped**. The outcome tabs no longer count it.
  - On the Skipped tab a decision can still be changed with the actions the server already allows: a skipped review row can be corrected or confirmed, and a skipped update can be ticked again. The row then returns to its tab. After a commit, discard or expiry the tab is read-only.
  - Tab counts are now counted from the rows the server returns, instead of the server's per-outcome summary, because that summary counts skipped rows under their outcome. Nothing is guessed in the browser: rows, decisions and allowed actions all still come from the server.
  - No backend change. The server already exposes each row's `decision`, and skipping and un-skipping were already allowed and audited (D-091).
- **Alternatives:**
  - A `skipped` count in the server's summary (rejected for now: it changes the ECOM-011 API for a pure display concern; the browser already holds every row).
  - Hiding skipped rows entirely (rejected: the reviewer would lose the way to change their mind before the commit, and the owner asked for a tab).
  - An "Undo skip" button (rejected: a skipped review row with an empty name cannot go back unchanged; correcting or confirming it is the real decision, and the server records it).
- **Test-first proof:** the 5 new or changed component tests failed on the old screen (no Skipped tab, skipped rows still in their tab) and pass now.
- **Other remarks:** the owner said the user experience needs improving. That goes to ECOM-018 (D-082), with what the screenshots show.
