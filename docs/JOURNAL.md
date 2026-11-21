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
- **Status:** Partially superseded by D-029. The single app image stands; the database is now a companion container.
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
- **Status:** Accepted. Q-13 was accepted on its default (D-038). This supersedes the single-container part of D-018.
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
  - **Q-13:** CC-08 is read as one app image plus a PostgreSQL container, started together with `docker compose up`.

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
