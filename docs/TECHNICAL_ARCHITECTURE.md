# Technical Architecture

> **Status:** Proposed, pending review. No code has been written yet.
>
> | Revision | Date | What changed |
> |---|---|---|
> | 1 | 2026-11-21 | Initial proposal. |
> | 2 | 2026-11-21 | Your answers to Q-01, Q-03, Q-06, Q-08, Q-09 and Q-10 are incorporated: PostgreSQL, the import review workflow, the gift tag, the `testing/` runner, and `Documents/` kept out of git. |
> | 3 | 2026-11-21 | Q-14 answered. Added an **append-only audit trail** that records how every value was and what it became (§6.4). Q-02, Q-07, Q-11, Q-12 and Q-13 are closed on their defaults. |
> | 4 | 2026-11-21 | Went deeper on four points: the idempotency key (§7.2), preventing oversold stock (§7.3), one error format for everything (§4.6), and CSV warnings versus errors plus the SKU identity check (§6.2, §6.5). The sample's expected numbers were updated (§2). |
>
> Every decision here also appears in [JOURNAL.md](JOURNAL.md) with its context and the alternatives considered.

---

## 1. Ground rules (we never cross these)

### 1.1 Code challenge rules (from `Documents/Code Challenge..pdf`)

| ID | Rule | How we satisfy it |
|----|------|-------------------|
| **CC-01** | Must use a **local DB** (SQL or NoSQL). | PostgreSQL runs locally in its own container, accessed through SQLAlchemy and migrated with Alembic. See §4.4. |
| **CC-02** | **CRUD for Products.** | The `catalog` bounded context, with REST endpoints and an admin UI. |
| **CC-03** | Products can be **imported from a CSV** with the columns `name, sku, description, category, price, stock, weight_kg`. | An import workflow: upload → review (corrections and confirmations) → commit. See §6. |
| **CC-04** | Use the provided example CSV, and state in the README **the date it was downloaded**. | Downloaded **2026-11-20**; the README states this date. The sample is the golden test fixture. |
| **CC-05** | **Search for Products.** | `GET /api/v1/products?q=…` with filters and pagination, plus a storefront search UI. |
| **CC-06** | **Purchase products**, with the payment faked (no real provider). | The `ordering` bounded context, with a `PaymentGateway` port and a `FakePaymentGateway`. |
| **CC-07** | **UI required** for product CRUD, search and purchase. | A React SPA with two areas: Admin (CRUD and import review) and Storefront (search, cart and checkout). |
| **CC-08** | The application must be **runnable as a Docker container**. | The application ships as **one Docker image** that serves both the API and the SPA. Its PostgreSQL runs as a companion container, and one command starts both: `docker compose up`. See §10 and Q-13. |
| **CC-09** | The README documents **decisions, approach and alternatives considered**. | The README summarises them and links to `docs/JOURNAL.md`. |
| **CC-10** | AI is allowed, but **comments must be removed from the code**. | Source and test code contain zero comments. This is enforced by `testing/scripts/check_no_comments.py` in CI. See §8.4. |
| **CC-11** | The solution is delivered in a **GitHub repository**. | `github.com/Ortiz-100323/E-commerce`, which is already set as `origin`. |
| **CC-12** | The README has **instructions to run the project locally**. | Two ways to run it: with Docker Compose, or natively (`docker compose up db`, then `uv` and `npm`). |
| **CC-13** | The app must be **"enterprise-grade"**, and the reviewer values **asking the right questions**. | DDD layering, TDD, explicit domain rules, a data-quality review workflow, concurrency safety and observability. There is also a register of **questions for the customer** (§11.3). |

### 1.2 Project rules (set by us)

| ID | Rule |
|----|------|
| **PR-01** | **TDD.** Every behaviour starts as a failing test (red). Then we write the minimum code to pass (green), then refactor. No production code is written without a failing test that demands it. |
| **PR-02** | **DDD layering.** The domain depends on nothing. The application layer depends only on the domain. Infrastructure and the API depend inward. `import-linter` enforces this automatically (§8.3). |
| **PR-03** | **`testing/` holds every test and every script.** That covers backend, frontend and E2E tests, fixtures, and every Python helper script. Application source code is the only Python outside it. |
| **PR-04** | **One entry point for running things: `testing/run.py`.** The AI never runs inline `python -c` snippets or throwaway scripts. Any analysis or check it needs becomes a file in `testing/scripts/`, executed through the runner (§8.5). |
| **PR-05** | **Every decision is logged** in `docs/JOURNAL.md`. |
| **PR-06** | **Every interaction is logged word for word** in `docs/PROMPT_HISTORY.md`. |
| **PR-07** | **The server is the source of truth.** The client never decides prices, totals or stock. |
| **PR-08** | **Money is never a float.** It is `Decimal` in the domain and `NUMERIC` in the DB. |
| **PR-09** | **Business rules that the customer may want changed are policies, not hard-coded `if`s.** They are selected by configuration (§6.3). |
| **PR-10** | **`Documents/` is never committed.** It is git-ignored. |
| **PR-11** | **Use the GitHub account `Ortiz-100323` only**, as set in `C:\Personal\CLAUDE.md`. |
| **PR-12** | **Nothing is committed or pushed without explicit approval.** |
| **PR-13** | **Every data change is traceable.** Each correction, confirmation and product change is written to an append-only audit log, with the value before and after, who made the change, and when (§6.4). Audit entries are never updated or deleted. |

---

## 2. What the sample CSV taught us

The sample is deliberately dirty. It tests judgement, not just parsing. Here is a profile of `Code Challenge E-Commerce.csv`.

**Format**
- UTF-8 with no BOM.
- **CRLF** line endings, and no newline at the end of the file.
- 97 data rows plus 1 header row.

**CSV mechanics it exercises**
- Quoted fields containing commas: `"Comma, In Product Name"`.
- Escaped quotes: `"Quote ""Inside"" Name"`.
- Non-ASCII characters: `—` and `™`.

| File line | SKU | Problem | Outcome (revision 2) |
|-----------|-----|---------|-----------------------|
| 4 | WM-042 | The price is `$29.99`. | **Ready.** The leading `$` is stripped, and a warning is recorded. |
| 7 | YM-015 | The price is `free`. | **Needs review.** Suggested: price `0.00` with the GIFT tag. The user either confirms it as a gift or corrects the price. |
| 16 | DL-007 | The stock is `-5`. | **Rejected.** Stock cannot be negative. The row is listed with its reason. |
| 20 | XS-001 | The name is `<script>alert('xss')</script>`. | **Rejected.** Markup is not allowed in names (see Q-02). |
| 25 | HD-099 | The name is empty. | **Needs review.** The user fills in the name. |
| 29 | SQL-001 | The name is `Robert'); DROP TABLE products;--`. | **Ready, stored as plain text.** Parameterised queries make it harmless, and a test proves the table survives. |
| 41 | WS-001 | The name is only whitespace. | **Needs review.** After trimming, the name is empty. |
| 47 | MB-001 | The price is `0.00`. | **Needs review.** The user confirms it as a gift or corrects the price. |
| 50 | GK-088 | The weight is empty. | **Needs review.** The user fills in the weight. |
| 52 | GC-025 | The category is empty, the stock is `99999` and the weight is `0`. | **Needs review.** The user fills in the category and confirms the zero weight (a digital product; see Q-12). |
| 62–63 | — | Both rows are completely empty. | **Blank.** They are skipped silently. |
| 2 → 36 | RS-001 | The SKU is duplicated, and the second row is an "Updated…" version. | **The last row wins.** A warning is recorded and shown in the review. |
| 11 → 56 → 89 | BS-021 | The SKU appears 3 times, and the third row is identical to the first. | **The last row wins.** A warning is recorded and shown in the review. |
| various | — | Some names repeat with different SKUs (Running Shoes ×3, Bluetooth Speaker ×4). | **Valid.** Names are not unique; the SKU is the identity. |
| 51 | VC-001 | The stock is `0`. | **Valid.** The product is out of stock and cannot be purchased. Zero stock is a normal state, so it is not flagged. |

**Expected report for the sample on an empty database (revision 4)**

| Outcome | Rows |
|---------|------|
| `blank` | **2** (lines 62–63) |
| `rejected` | **2** (DL-007 negative stock, XS-001 markup) |
| `needs_review` | **6** (YM-015, HD-099, WS-001, MB-001, GK-088, GC-025) |
| `create` | **84** |
| `superseded` | **3** (RS-001 line 2, and BS-021 lines 11 and 56, replaced by later rows) |
| **Total** | **97** |

The import also produces **3 warnings**:
- 1 `currency_symbol_stripped` on line 4.
- 2 `duplicate_sku_in_file`, on the winning rows: line 36 and line 89.

The SKU identity check (§6.5) fires **0** times, because every in-file duplicate keeps the same name.

The 2 blank and 3 superseded rows came from the profile verified in Session 1. The new warning taxonomy (§6.2) was counted by hand. Phase 0 re-verifies all of it with `testing/scripts/simulate_import.py`.

After the user resolves the 6 review rows, the import can create up to **90 products**. Re-importing the same file afterwards reports **84 unchanged**.

This becomes the golden acceptance test for the importer.

---

## 3. High-level architecture

The system is a **modular monolith**: one application image, two bounded contexts and a shared kernel. It is backed by PostgreSQL.

```
                ┌──────────────────────────────────────────────┐
  Browser ───▶  │  app container (FastAPI)                     │
  (React SPA)   │   /            → static SPA (built React)    │
                │   /api/v1/*    → REST API                    │
                │   /health /ready                             │
                │                                              │
                │  ┌───────────── catalog ──────────────┐      │
                │  │ Product, ImportBatch               │      │
                │  │ api → application → domain         │      │
                │  │ infrastructure (SQLAlchemy, CSV)   │      │
                │  └────────────────────────────────────┘      │
                │  ┌───────────── ordering ─────────────┐      │
                │  │ Order                              │      │
                │  │ api → application → domain         │      │
                │  │ infrastructure (SQLAlchemy,        │      │
                │  │   FakePaymentGateway, CatalogACL)  │      │
                │  └────────────────────────────────────┘      │
                │  shared_kernel (Money, errors, UoW port)     │
                └───────────────────┬──────────────────────────┘
                                    │ psycopg 3 (async)
                ┌───────────────────▼──────────────────────────┐
                │  db container: PostgreSQL 17 (named volume)  │
                └──────────────────────────────────────────────┘
```

### 3.1 Bounded contexts

| Context | Responsibility | Aggregates |
|---------|----------------|------------|
| **catalog** | Products, categories, tags, stock levels, the CSV import workflow and search. | `Product`, `ImportBatch` |
| **ordering** | Checkout, orders and payment orchestration (faked). | `Order` (contains `OrderLine`) |
| **shared_kernel** | Value objects and abstractions that both contexts use. | — |

`ordering` never imports catalog's domain. It reaches the catalog through an **anti-corruption port** called `CatalogGateway`, which offers two operations: get a sellable product snapshot, and lock and decrease stock.

Both contexts share one database transaction through a Unit of Work.

### 3.2 Layers (per context)

| Layer | Contains | May import |
|-------|----------|------------|
| `domain` | Entities, value objects, aggregates, **policies**, domain errors, repository **interfaces** | `shared_kernel.domain` and the standard library only. **No** FastAPI, SQLAlchemy or Pydantic. |
| `application` | Use cases (commands and queries), DTOs, and ports (UoW, PaymentGateway, CatalogGateway, Clock) | `domain`, `shared_kernel` |
| `infrastructure` | SQLAlchemy mappings and repositories, the CSV reader, the fake payment gateway and settings | `application`, `domain` |
| `api` | FastAPI routers, Pydantic schemas and error mapping | `application` (and `domain` errors, for mapping) |
| `main.py` | The composition root: wires adapters and the configured policies | everything |

---

## 4. Backend

### 4.1 Stack

| Concern | Choice |
|---------|--------|
| Runtime | Python **3.13**, managed with **uv** |
| Web | **FastAPI**, with Pydantic v2 |
| ORM and migrations | **SQLAlchemy 2.x async**, using imperative mapping so the domain stays free of ORM classes. **Alembic** handles migrations. |
| DB | **PostgreSQL 17**, using the **psycopg 3** driver (async for the app, sync for Alembic) |
| Settings | `pydantic-settings`, read from environment variables. This includes the import policies. |
| Logging | Structured JSON, plus a request-ID middleware |
| Quality | `ruff` (lint and format), `mypy --strict`, `import-linter` |
| Tests | `pytest`, `pytest-asyncio`, `pytest-cov`, `hypothesis` (property-based) and `httpx`. **Testcontainers** provides a real PostgreSQL. |

Exact versions are pinned in Phase 0 and logged in the journal.

### 4.2 Domain model

**Value objects.** They are immutable and validated when constructed, so an invalid instance can never exist.

| VO | Rules |
|----|-------|
| `Sku` | Trimmed and upper-cased. Must match `^[A-Z0-9]+(-[A-Z0-9]+)*$`. Length 1–64. |
| `ProductName` | Trimmed, 1–200 characters. No `<` or `>`, and no control characters. |
| `Description` | Trimmed, 0–2000 characters. No control characters except newline. |
| `Category` | Trimmed, 1–80 characters. Compared case-insensitively. The canonical form is the first spelling seen. |
| `Money` | A `Decimal` with at most 2 decimal places, in currency `USD` (CQ-06). |
| `Price` | `Money` that is **≥ 0**. A price of 0 is only legal together with the GIFT tag (see the invariant below). |
| `StockQuantity` | An integer ≥ 0. |
| `Weight` | A `Decimal` in kg, ≥ 0, with at most 3 decimal places. |
| `ProductTag` | A closed enum. It currently has one value, `GIFT`, and grows only when needed. |

**The `Product` aggregate** belongs to catalog.
- **Identity:** `ProductId` (a UUID). The natural key is `Sku`, which is unique.
- **State:** name, description, category, price, stock, weight, `tags`, `status` (`ACTIVE` or `ARCHIVED`), `version` (for optimistic locking) and timestamps.
- **Invariant:** `price == 0 ⇒ GIFT ∈ tags`. Removing the GIFT tag requires a price above 0.
- **Behaviour:**
  - `rename`, `reprice`, `recategorize`, `restock`
  - `mark_as_gift`, `unmark_gift`
  - `decrease_stock(qty)`, which raises `InsufficientStock`
  - `archive`, `restore`
  - `is_sellable`, true when the product is active and stock is above 0
- **Domain events:** every change records an event, which feeds the audit log (§6.4):
  - `ProductCreated`
  - `ProductChanged`, which carries each changed field's value before and after
  - `ProductArchived`, `ProductRestored`
  - `StockDecreased`, which carries the order reference

**The `ImportBatch` aggregate** also belongs to catalog. It models the review workflow described in §6.
- **State:** `ImportBatchId`, file name, file SHA-256, upload time, `reviewer`, `status` and `rows[]`.
  - `status` is one of `PENDING_REVIEW`, `COMMITTED`, `DISCARDED` or `EXPIRED`.
  - Each row (`ImportRow`) holds:
    - the line number;
    - the **raw line text, verbatim**, and the raw values. Both are immutable;
    - the normalised values and the `outcome`;
    - the issues and warnings;
    - the version of the target product captured at preview time;
    - the **resolution history**: every confirm, correct or skip, with the values before and after.
- **Domain events:** `ImportStarted`, `ImportRowConfirmed`, `ImportRowCorrected` (with the values before and after, and the original issue), `ImportRowSkipped`, `ImportCommitted` and `ImportDiscarded`.
- **Row outcomes:** `create`, `update` (which carries a field diff), `unchanged`, `needs_review`, `rejected`, `superseded` (an earlier duplicate of an SKU in the same file) and `blank`.
- **Row resolutions:** `confirm` (confirm a gift, confirm zero weight, or confirm an update), `correct(values)` (the row is validated again) and `skip`.
- **Invariant:** the batch can be committed only when no row is left in `needs_review` and every `update` row is either confirmed or skipped.

**The `Order` aggregate** belongs to ordering.
- **State:** `OrderId`, `status`, `customer` (name and email), `lines[]`, `total`, `payment_reference`, `idempotency_key` and timestamps.
  - `status` moves from `PENDING` to either `PAID` or `PAYMENT_FAILED`.
- `OrderLine` is a **snapshot** of the SKU, name, unit price, quantity and gift flag at the moment of purchase.
- **Invariants:**
  - There is at least 1 line.
  - Every quantity is ≥ 1.
  - SKUs are unique within an order; duplicates are merged.
  - The total equals the sum of the lines.

### 4.3 Key use cases

| Use case | Notes |
|----------|-------|
| `CreateProduct`, `UpdateProduct`, `ArchiveProduct`, `RestoreProduct`, `GetProduct` | A price of 0 requires an explicit `gift: true`. Otherwise the request fails with 422 and the reason `zero_price_requires_gift_confirmation`. Updates must send the `version` they read; a mismatch returns 409. |
| `SearchProducts` | `q` searches name, SKU and description. Filters: `category`, `min_price`, `max_price`, `in_stock` and `tag`. Supports sorting and offset pagination. |
| `ListCategories` | Returns the distinct categories of active products. |
| `StartImport` | Parses the file, classifies every row using the configured policies, and persists an `ImportBatch` in the `PENDING_REVIEW` state. |
| `ResolveImportRow` | Applies `confirm`, `correct` or `skip` to a row, and re-classifies it if needed. |
| `CommitImport` | Applies all `create` rows and all confirmed `update` rows in a single transaction. If a target product changed since the preview, the affected rows go back to review and the commit returns 409. |
| `DiscardImport` | Abandons the batch. The batch and its rows are kept for audit. |
| `GetProductHistory` | Returns the product's audit timeline, oldest first. For imported products, it starts from the raw CSV line. |
| `Checkout` | See §7. |
| `GetOrder` | Used by the confirmation page. |

### 4.4 Persistence

- The database is **PostgreSQL 17**, run as the compose service `db` with a named volume and a `pg_isready` healthcheck.
- Money columns are `NUMERIC(12,2)` and weight is `NUMERIC(10,3)`.
- **CHECK constraints in the database mirror the domain invariants**, as defence in depth:
  - price ≥ 0
  - stock ≥ 0
  - weight ≥ 0
  - a price of 0 implies the gift tag
- SKUs have a unique index.
- Search uses the `pg_trgm` extension, with GIN trigram indexes on name, SKU and description. This makes `ILIKE` fast and Unicode-aware, and user input is escaped for LIKE wildcards.
- Import rows are stored in the `import_batch_rows` table, with their raw and normalised values as JSONB. Batches are never purged (CQ-09).
- The audit log lives in the `audit_log` table, which is **append-only**. A trigger raises an error on any `UPDATE` or `DELETE`. Its entries are written in the **same transaction** as the change they describe (§6.4).
- **Concurrency:**
  - Admin edits use optimistic locking (a `version` column, returning 409 on conflict).
  - Checkout and the import commit use `SELECT … FOR UPDATE` on the products involved, **ordered by SKU** to avoid deadlocks.
  - The isolation level is READ COMMITTED.
  - The full protocol is in §7.3.
- The `idempotency_keys` table holds checkout keys, their request fingerprints and their outcomes (§7.2). Rows expire after 24 hours.
- **Deletion is a soft delete (archive).** Archived products are hidden from the storefront and cannot be bought, and their SKU remains reserved.
- Alembic migrations run automatically when the app container starts.

### 4.5 API surface (`/api/v1`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/products` | Search and list. Parameters: `q`, `category`, `min_price`, `max_price`, `in_stock`, `tag`, `status`, `sort`, `page`, `page_size`. |
| POST | `/products` | Create |
| GET | `/products/{id}` | Read |
| PUT | `/products/{id}` | Full update. Requires `version`. |
| DELETE | `/products/{id}` | Archive (soft delete) |
| POST | `/products/{id}/restore` | Un-archive |
| GET | `/products/{id}/history` | The product's audit timeline |
| GET | `/categories` | List distinct categories |
| POST | `/imports` | Upload a CSV (multipart). Creates an `ImportBatch` and returns the classified report. |
| GET | `/imports/{id}` | Get the batch with all its rows and outcomes |
| PATCH | `/imports/{id}/rows/{line}` | Resolve a row: `confirm`, `correct` or `skip` |
| POST | `/imports/{id}/commit` | Apply the batch |
| DELETE | `/imports/{id}` | Discard the batch |
| POST | `/orders` | Checkout. The `Idempotency-Key` header is required. |
| GET | `/orders/{id}` | Order detail |
| GET | `/health`, `/ready` | Liveness, and readiness (the DB is reachable) |

- Every error uses one format, **RFC 9457 Problem Details**. See §4.6.

- Money is always serialised as a string (for example `"29.99"`), together with a currency code.
- Every request that changes admin or import data must send the `X-Actor-Name` header. If it is missing, the request fails with 422. The value is stored as the **actor** in the audit log (§6.4).

### 4.6 Errors: one format for everything

Every error response uses **RFC 9457 Problem Details** with `Content-Type: application/problem+json`. That covers errors raised by Pydantic, the domain, the use cases, routing, and unexpected failures. The client only ever has one shape to parse.

**Shape**

```json
{
  "type": "urn:ecommerce:problem:validation-error",
  "title": "The request is not valid.",
  "status": 422,
  "detail": "2 fields are not valid.",
  "instance": "/api/v1/products",
  "request_id": "0b9f6c1e-…",
  "errors": [
    { "location": "body", "field": "price", "code": "zero_price_requires_gift", "message": "A price of 0 must be confirmed as a gift.", "params": {} },
    { "location": "body", "field": "sku", "code": "invalid_sku_format", "message": "Use letters, digits and single hyphens only.", "params": { "pattern": "^[A-Z0-9]+(-[A-Z0-9]+)*$" } }
  ]
}
```

The response always carries `type`, `title`, `status` and `request_id`. The `errors[]` field appears only on validation problems. Other problems may add their own fields; for example, `insufficient-stock` adds `items[]`.

**Where each error comes from, and how it gets here**

| Source | Example | Converted by | Status and type |
|--------|---------|--------------|-----------------|
| A body that is not valid JSON | `{"name":` | The `RequestValidationError` handler, when the error type is `json_invalid` | **400** `malformed-request` |
| Request shape (Pydantic) | A missing field, a wrong type, an unknown field (`extra="forbid"`), a string over the size limit | The `RequestValidationError` handler, which converts each Pydantic error | **422** `validation-error` |
| The `Idempotency-Key` header | Missing, or not a UUID | Our own dependency. We override FastAPI's default 422 to follow the IETF idempotency draft. | **400** `idempotency-key-missing` / `idempotency-key-invalid` |
| A domain rule | Bad SKU format, markup in a name, a price of 0 without a gift flag | `DomainValidationError`, which carries a list of `ValidationIssue` | **422** `validation-error` (same `errors[]` shape) |
| A business conflict | Not found, version conflict, duplicate SKU, insufficient stock | Domain and application errors, through one mapping table | 404 / 409 / 402 (see the catalog below) |
| Starlette HTTP errors | An unknown route, a wrong method | The `HTTPException` handler | 404 / 405 |
| Anything unexpected | A bug, or the database is down | A catch-all handler | **500** `internal-error`, or **503** `service-unavailable`. No stack trace is returned; the client gets a `request_id` to find the logs. |

**How Pydantic errors are converted**
- **Location and field.** `loc` becomes `location` plus `field`. For example, `("body","lines",0,"quantity")` becomes location `body` and field `lines[0].quantity`. Query parameters and headers get location `query` and `header`.
- **Code.** Pydantic's `type` becomes our stable `code` through a mapping table. For example:
  - `missing` → `required`
  - `string_too_long` → `too_long`
  - `int_parsing` → `not_an_integer`
  - `decimal_parsing` → `not_a_number`
  - `decimal_max_places` → `too_many_decimal_places`
  - `greater_than_equal` → `too_small`
  - `extra_forbidden` → `unknown_field`

  A unit test fails if any of our schemas can raise a Pydantic type that has no mapping.
- **Params.** `ctx` becomes `params`, for example `{"max_length": 200}`.
- **Values are never echoed back.** Pydantic's `input` and `url` are dropped. A card number or an email address must never end up in a response, a log or a screenshot.

**Who validates what.** Each rule lives in exactly one place.
- **Pydantic checks shape.** That means JSON types, required fields, unknown fields, and abuse limits: strings up to 10,000 characters, up to 50 order lines, `page_size` up to 100.
- **The domain checks meaning.** That means the SKU format, name rules, prices of at least 0, and the gift invariant.

For example, a price of `"-1"` passes Pydantic, because it is a valid decimal, and then fails in the domain. The client still receives the same 422 format either way.

Domain validation **collects every issue before raising**, rather than stopping at the first one, so a form can show all its problems at once. `ValidationIssue {field, code, severity, message, params}` is also the structure the CSV importer uses for each row (§6.2). The frontend renders form errors and import-row issues with one component.

**Problem type catalog**

| `type` (suffix of `urn:ecommerce:problem:`) | Status | Raised when | Extra fields |
|---|---|---|---|
| `malformed-request` | 400 | The body is not valid JSON | — |
| `idempotency-key-missing`, `idempotency-key-invalid` | 400 | §7.2 | — |
| `not-found` | 404 | An unknown product, order, import or route | — |
| `method-not-allowed` | 405 | The wrong HTTP method | — |
| `payment-declined` | 402 | The fake gateway declined the card | `order_id` |
| `version-conflict` | 409 | A stale `version` on PUT | `current_version` |
| `duplicate-sku` | 409 | Creating a product with an SKU that is already taken | `sku` |
| `insufficient-stock` | 409 | Checkout (§7.3) | `items[] {sku, requested, available}` |
| `product-not-sellable` | 409 | The product is archived, or has 0 stock | `items[] {sku, reason}` |
| `import-not-committable` | 409 | Rows are still unresolved | `pending_lines[]` |
| `import-stale-rows` | 409 | A product changed after the preview | `lines[]` |
| `payload-too-large` | 413 | The upload is over 5 MB | `max_bytes` |
| `unsupported-media-type` | 415 | The upload is not a CSV | — |
| `validation-error` | 422 | Pydantic or domain validation failed | `errors[]` |
| `idempotency-key-reused` | 422 | §7.2 | — |
| `internal-error` | 500 | An unexpected failure | — |
| `service-unavailable` | 503 | The database is unreachable, or a lock wait timed out (§7.3) | Header `Retry-After` |

**Frontend.** A single `ApiError` class parses every problem response.
- Entries in `errors[].field` are mapped onto form fields with react-hook-form's `setError`.
- Every other problem is shown as a notification with its `title`. For 5xx errors, the notification also shows the `request_id`.

**Tests**
- A contract test sends bad input to every endpoint. It asserts the response is `application/problem+json` and matches the schema above.
- Unit tests cover the conversion from `loc` to `field`, and the mapping from Pydantic types to codes.
- A test sends a bad request containing a card number and proves the number appears in neither the response nor the logs.

---

## 5. Frontend

| Concern | Choice |
|---------|--------|
| Tooling | **Vite** + **React 19** + **TypeScript** in `strict` mode |
| Server state | **TanStack Query** |
| Routing | **React Router** |
| Forms | `react-hook-form` + `zod`. These mirror the server rules; the server stays authoritative. |
| Styling | CSS Modules (no UI framework) |
| Cart | Client-side, stored in `localStorage`. The server re-validates and re-prices it at checkout. |
| Quality | ESLint, including `react/no-danger`. Prettier. `tsc --noEmit`. |
| Tests | **Vitest** + **React Testing Library** + **MSW**, with specs in `testing/frontend`. **Playwright** for E2E, with specs in `testing/e2e`. |

**Screens**

| Area | Route | Purpose |
|------|-------|---------|
| Storefront | `/` | Search, filters, pagination, and a "Gift" badge on gift products |
| | `/products/:id` | Product detail and add to cart. The button is disabled when the product is out of stock. |
| | `/cart` | The cart, with a subtotal computed by the server |
| | `/checkout` | Customer name and email, the fake card, and the pay button |
| | `/orders/:id` | Order confirmation |
| Admin | (all routes) | On the first visit, the admin area asks **"Who is reviewing?"**. The name is remembered in `localStorage` and sent as `X-Actor-Name` with every change. |
| | `/admin/products` | A table with search, create, edit, archive and restore |
| | `/admin/products/:id/history` | The audit timeline: the raw CSV line, then each correction or confirmation, then later edits. Each entry shows the actor and the time. |
| | `/admin/products/new`, `/:id/edit` | The product form. If the price is 0, a dialog asks **"Price is 0. Mark this product as a gift?"** |
| | `/admin/imports/new` | Upload a CSV |
| | `/admin/imports/:id` | **Review screen**, with one tab per outcome. Needs-review rows get an inline editor plus confirm and skip actions. Update rows show an old → new diff per field with a confirm checkbox, plus "confirm all". Rejected rows show their reasons, and warnings are listed too. The commit button stays disabled until the batch can be committed. |

---

## 6. CSV import design (review workflow)

### 6.1 Flow

```
upload ──▶ parse & classify ──▶ ImportBatch(PENDING_REVIEW)
                                      │
            user resolves rows ◀──────┤  needs_review → confirm / correct / skip
            user confirms updates ◀───┤  update       → confirm / skip (field diff shown)
                                      │
                         commit ──────┴──▶ one transaction ──▶ COMMITTED
                                            (stale rows → back to review, 409)
```

1. **Upload limits.** The file must be at most 5 MB, and only `.csv` / `text/csv` is accepted.
   - The file must be UTF-8. A BOM is tolerated; any other encoding gets a clear error.
2. **Header check.** The 7 required columns must be present. Matching is case-insensitive and trims whitespace.
   - Unknown extra columns are ignored, with a warning.
   - If a required column is missing, the whole upload is rejected with 422.
3. **Parsing** uses Python's `csv` module, which handles quotes, commas inside fields, escaped quotes and CRLF line endings.
4. **Classification** runs every row through the domain value objects and the **configured policies** (§6.3). A bad row never throws; it is classified instead.
5. **Normalisations.**
   - Lossless fixes are reported as warnings, for example an upper-cased SKU or a stripped `$` (§6.2).
   - Trimming whitespace is silent.
6. **Duplicate SKUs within the file** are resolved with the configured policy and the identity check (§6.5).
   - By default the last row wins.
   - Earlier rows become `superseded`.
7. **Rows whose SKU already exists** first pass the **identity check** (§6.5). If the row describes a different product, it is rejected. Otherwise it is compared field by field:
   - identical rows become `unchanged`;
   - different rows become `update`, carrying the diff, and **need confirmation**;
   - if the existing product is archived, the update also restores it, and the diff says so (see CQ-08).
8. **Commit** happens in one transaction. Before writing, it checks again that no target product changed since the preview, using the captured version.
9. **Expiry.** Batches that sit in `PENDING_REVIEW` for more than 24 hours expire.

### 6.2 Warning, review or error: how each row is classified

**Every issue found in a row has one of three severities.** A row's outcome follows its most severe issue.

| Severity | Meaning | Row outcome | Who acts |
|----------|---------|-------------|----------|
| **Warning** | We changed nothing that matters, or we applied a lossless, obvious fix. | **Imported**, as a create or an update | Nobody. The warning appears in the report. |
| **Review** | A value is 0 or empty. It may be right, or it may be a mistake. | **Held** until a person confirms or corrects it (D-037). Skipped otherwise. | The reviewer, in the review screen |
| **Error** | The value is invalid, or importing it could damage existing data. | **Rejected**, and it is not editable | The owner of the file fixes the source and uploads it again |

**Rule: we never silently change what a value means.** Rounding, truncating, or guessing a currency or decimal separator would alter data without anyone noticing, so all of these are **errors**. Only lossless fixes count as warnings.

**Silent (not even a warning):**
- trimming surrounding whitespace;
- removing a UTF-8 BOM;
- handling CRLF or LF line endings.

#### File-level errors: the whole upload is refused and no batch is created

| Code | When | Status |
|------|------|--------|
| `file_too_large` | Over 5 MB | 413 |
| `unsupported_media_type` | Not `.csv` / `text/csv` | 415 |
| `invalid_encoding` | Not valid UTF-8 | 422 |
| `empty_file` | No header row | 422 |
| `missing_columns` | A required column is missing; the response lists which | 422 |
| `duplicate_columns` | The same column appears twice | 422 |
| `too_many_rows` | More than 10,000 data rows (this limit is a setting) | 422 |
| `malformed_csv` | For example, an unclosed quote; the response gives the line | 422 |

#### File-level warnings

| Code | When |
|------|------|
| `unknown_column_ignored` | The file has an extra column |
| `same_file_already_pending` | A batch with the same SHA-256 is still `PENDING_REVIEW` |

#### Row warnings: the row is imported

| Code | Example | What we do |
|------|---------|------------|
| `currency_symbol_stripped` | `$29.99` | Store 29.99. Only `$` is stripped (USD, CQ-06). |
| `sku_normalized` | `rs-001` | Store `RS-001` |
| `integer_normalized` | stock `12.0` | Store 12 |
| `duplicate_sku_in_file` | RS-001 appears on lines 2 and 36 | Import line 36; line 2 becomes `superseded` |
| `restores_archived_product` | The SKU belongs to an archived product | Restore the product with the update (CQ-08) |

#### Row review: the row is held for a person (the only editable rows, D-037)

| Code | Example | What the reviewer does |
|------|---------|------------------------|
| `empty_required_field` | `name`, `sku`, `category`, `price`, `stock` or `weight_kg` is empty or only whitespace | Fills in the value |
| `zero_price` | `0`, `0.00`, `free` | Confirms the product as a GIFT, or corrects the price |
| `zero_weight` | `0` | Confirms the product is non-physical, or corrects the weight |

An update to an existing SKU also needs confirmation. That is handled by the `update` outcome (D-033), not by an issue.

#### Row errors: the row is rejected

| Code | Examples |
|------|----------|
| `wrong_field_count` | The row has 8 values but the header has 7 |
| `invalid_number` | `abc`, `1,299.99`, `12,5`, `1e3`, `NaN`, `Infinity` |
| `unsupported_currency` | `€10`, `USD 10` |
| `negative_value` | stock `-5` |
| `too_many_decimal_places` | price `9.999`, weight `0.1234` |
| `not_an_integer` | stock `12.5` |
| `value_out_of_range` | A price above `9,999,999,999.99`, or stock above `2,147,483,647` |
| `value_too_long` | A name over 200 characters, a description over 2,000, a category over 80, or an SKU over 64 |
| `invalid_sku_format` | `RS 001`, `RS_001` |
| `markup_in_name` | `<script>alert('xss')</script>` |
| `control_characters` | A tab or NUL character in any field |
| `sku_conflict_in_file` | The same SKU is used for different products within the file (§6.5) |
| `sku_belongs_to_different_product` | The SKU already belongs to a different product in our catalog (§6.5) |

**Every issue in a row is collected, not just the first.** For example, a row with an empty category and negative stock shows both issues. Errors take precedence, so that row is `rejected`. Each issue is a `ValidationIssue {field, code, severity, message, params}`, the same structure as the API's `errors[]` (§4.6).

**Order of classification**
1. A blank row → `blank`.
2. Check the field count.
3. Parse and check each field, collecting issues.
4. The worst severity decides between `rejected`, `needs_review` and valid.
5. Resolve duplicates within the file (§6.5).
6. Compare against the database. The identity check (§6.5) gives either a conflict error, or one of `update`, `unchanged` or `create`.

**Formula injection.** Values such as `=HYPERLINK(…)` are stored as plain text. They only become dangerous when exported to a spreadsheet, and we have no export. If one is added, it must escape these values.

### 6.3 Configurable policies (PR-09)

Each policy is a domain strategy. The composition root selects one from the settings, so if the customer wants a different rule, it is a **configuration change, not a code change**. Every variant of every policy has its own unit tests.

| Setting | Default | Alternatives |
|---------|---------|--------------|
| `IMPORT_ZERO_PRICE_POLICY` | `review_as_gift` | `reject`, `accept_as_gift` |
| `IMPORT_EMPTY_FIELD_POLICY` | `review` | `reject` |
| `IMPORT_ZERO_WEIGHT_POLICY` | `review` | `accept`, `reject` |
| `IMPORT_EXISTING_SKU_POLICY` | `update_with_confirmation` | `create_only`, `update_silently` |
| `IMPORT_DUPLICATE_SKU_IN_FILE_POLICY` | `last_wins` | `first_wins`, `reject_all` |
| `IMPORT_CURRENCY_SYMBOL_POLICY` | `strip_with_warning` | `reject` |
| `IMPORT_SKU_IDENTITY_POLICY` | `name_similarity` (threshold 0.5) | `exact_name`, `sku_only` |
| `IMPORT_MAX_ROWS` | `10000` | any positive integer |

### 6.4 Audit trail (PR-13)

**What is editable during review** (this was Q-14):
- Rows flagged `needs_review` **are editable**. These are rows with a zero or empty value.
- Rows flagged `rejected` **are not editable**. These are rows with negative values, malformed numbers, markup or a bad SKU. They are listed with the reason, and the user fixes the source file and uploads it again.

**How the audit log is written**
1. Aggregates record domain events: `ImportRowCorrected`, `ProductChanged`, and so on.
2. When the Unit of Work commits, it writes those events to `audit_log` **in the same database transaction** as the change itself. If the change rolls back, its audit entry rolls back too, so an audit entry can never be lost or describe a change that never happened.
3. `audit_log` is append-only. A database trigger blocks `UPDATE` and `DELETE`.

**Shape of an audit entry**

| Field | Example |
|-------|---------|
| `occurred_at` | `2026-11-21T14:02:11Z` |
| `actor` | `Antonio` (comes from `X-Actor-Name`; see the note below) |
| `event` | `import.row.corrected` |
| `entity` / `entity_id` | `import_row` / `<batch id>:47` |
| `sku` | `MB-001` |
| `context` | `{batch_id, line, file_sha256, original_issue: "zero_price"}` |
| `before` | `{"price": "0.00", "tags": []}` |
| `after` | `{"price": "0.00", "tags": ["GIFT"]}` (confirmed as a gift) |

**The trace for a corrected row.** Take the empty-weight row for `GK-088` (line 50) as an example:

1. **Raw CSV line, kept verbatim:** `Gaming Keyboard,GK-088,…,129.99,45,`
2. `import.row.corrected`: weight goes from `""` to `1.10`. Actor: Antonio, 14:02.
3. `product.created`: the product is created from batch X, line 50, after the commit.
4. `product.changed` (later, from the admin): price goes from `129.99` to `119.99`. Actor: Maria.

**Scope.** The audit covers:
- **every** product change, whether it comes from an import or from the admin;
- every import row resolution;
- every stock decrease from an order.

**Who the actor is.** The `actor` name is entered by the reviewer, because there is no authentication yet (Q-07). When authentication is added, the actor will come from the login token instead, and the log's format will not change.

**Tests cover:**
- an audit entry is written in the same transaction, and is gone when the transaction rolls back;
- the trigger rejects `UPDATE` and `DELETE`;
- the history endpoint returns the right timeline;
- after the 6 review rows are resolved, the golden import test finds exactly 6 resolution entries.

### 6.5 SKU identity: does this SKU already belong to a different product?

The SKU is the product's identity, so a row with an existing SKU is normally an update. **The risk is a wrong SKU.** A supplier may reuse an SKU, or a typo may land on an existing one. An "update" would then silently overwrite a *different* product: its name, price and stock. Its past orders and audit history would end up describing something else.

**Against the database.** This runs for every row whose SKU already exists, whether the product is active or archived.

1. Normalise both names: apply Unicode NFKC, case-fold, and collapse whitespace.
2. If the names are equal, it is the same product, and the row becomes `update` or `unchanged`.
3. If they differ, compute their **trigram similarity**. This is the same measure as PostgreSQL's `pg_trgm`, implemented as pure Python in the domain so it can be unit-tested.
   - At **0.5 or above**, it counts as a **rename** of the same product and becomes `update`. The name change appears in the diff, and every update needs confirmation anyway.
   - Below **0.5**, it is the **error `sku_belongs_to_different_product`**, and the row is rejected with a message such as:

     > SKU RS-001 is "Running Shoes" in the catalog, but this row describes "Yoga Mat". Use another SKU, or rename the product in the admin first.

| Catalog | Row with the same SKU | Result |
|---------|----------------------|--------|
| Running Shoes | `running  shoes` | Same name after normalisation → `update` or `unchanged` |
| Running Shoes | Running Shoes Pro | Similar → `update`, with the name change in the diff |
| Running Shoes | Yoga Mat | Different → **rejected** |
| Cotton T-Shirt | Organic Tee | Different → **rejected**. This is a false positive: rename the product in the admin, then import again. |

**Why we reject instead of sending the row to review.** Under D-037, only rows with zero or empty values are editable. A conflict is fixed by choosing a different SKU, and that belongs in the source file.

**Within the file.** Rows that share an SKU get the same check against each other.
- If they all describe the same product, the last row wins with the warning `duplicate_sku_in_file`, and the earlier rows become `superseded`.
- If they describe different products, **every** row with that SKU gets the error `sku_conflict_in_file`, because we can't know which one was meant.
- If the winning (last) row is rejected or needs review, an earlier row is **not** used in its place. Importing an earlier row would bring in data the file was meant to replace.

**At commit time.** SKUs are checked again while the commit holds its locks (§7.3).
- If an SKU was taken after the preview, by another import or by the admin, the row goes back to review and the commit returns 409 `import-stale-rows`.
- The unique index on `sku` is the final guard.

**What we deliberately do not check: the same name under a different SKU** (for example RS-050 "Running Shoes" alongside RS-001). Names are not unique (D-010), and product variants are normal. In the sample, this check would raise 2 false alarms.

**This rule is configurable** through `IMPORT_SKU_IDENTITY_POLICY`, and it is also a question for the customer (CQ-10).

---

## 7. Purchase flow (fake payment)

### 7.1 Checkout sequence

```
POST /api/v1/orders    Idempotency-Key: 6f1c2a…    body: {customer, lines[], payment}
── one database transaction ─────────────────────────────────────────────────
 1. Claim the idempotency key (§7.2). Replay or refuse if it was used before.
 2. Merge duplicate lines. Each quantity must be ≥ 1, with at most 50 lines.
 3. Lock the products with SELECT … FOR UPDATE, in SKU order (§7.3).
 4. Check that each product exists, is active and has enough stock.
    If not: 404 / 409, and nothing is written.
 5. Price every line from the LOCKED rows. Prices sent by the client are never read.
 6. Create the Order in the PENDING state.
 7. If the total is 0, mark it PAID without calling the gateway (CQ-01).
    Otherwise, charge the FakePaymentGateway:
      approved → decrease stock → PAID
      declined → PAYMENT_FAILED, stock unchanged
 8. Save the outcome against the idempotency key, and write the audit entries.
── COMMIT (the locks are released) ──────────────────────────────────────────
 → 201 Created (PAID)   or   402 Payment Required (PAYMENT_FAILED)
```

- **FakePaymentGateway** uses the familiar test-card numbers:
  - `4242 4242 4242 4242` is approved.
  - `4000 0000 0000 0002` is declined.
  - Any other number that passes the Luhn check is approved.
- **We never store or log a full card number.** We keep only the last 4 digits and a fake `payment_reference`.
### 7.2 Idempotency key

**What it is**
- A **UUID v4**, generated in the browser with `crypto.randomUUID()`, and sent in the `Idempotency-Key` header. It follows the IETF draft *The Idempotency-Key HTTP Header Field*.
- **One key per checkout attempt.**
  - The key is created when the checkout page opens.
  - It is **reused** for double-clicks, network retries and timeouts.
  - It is **replaced** whenever the cart or the form changes, and after every final answer (201 or 402).
- If the key is missing or is not a UUID, the request fails with **400** (`idempotency-key-missing` or `idempotency-key-invalid`).
- The key's scope is `POST /orders`.
  - Without a login, keys are global. The chance of two random UUID v4s colliding is negligible.
  - With a login, the scope will become the pair (user, key).
- Keys are kept for **24 hours** (a setting). After that the key is forgotten, and reusing it starts a new checkout.

**What we store.** The table `idempotency_keys` has these columns:
- `key` (primary key)
- `endpoint`
- `request_fingerprint`
- `outcome` (the order id and status)
- `response_status`
- `created_at`
- `expires_at`

**The request fingerprint** is a SHA-256 over the *canonical* form of the parsed request:
- SKUs in upper case;
- lines merged and sorted by SKU;
- the email in lower case;
- JSON keys sorted, with no whitespace.

The **card number is never part of the fingerprint**. Only its last 4 digits are, because a hash of a full card number can be brute-forced. As a result, retrying the same key with a different card that has the same last 4 digits counts as the same request. That trade-off is acceptable.

**What happens in each case**

| Situation | Response |
|-----------|----------|
| The key has not been seen before | Process the checkout. Store the key, fingerprint and outcome **in the same transaction** as the order. |
| The key has been seen, with the **same** fingerprint | **Replay** the stored outcome: the same status code and the same body, plus the header `Idempotent-Replayed: true`. There is no new order, no stock change and no second charge. |
| The key has been seen, with a **different** fingerprint | **422 `idempotency-key-reused`**: "This Idempotency-Key was already used for a different request." Nothing is processed, and nothing about the original order is revealed. |
| The same key arrives while the first request is still running | The second request waits on the unique index until the first one commits, then gets the replay. If the wait exceeds `lock_timeout` (5 s), it gets **503** with `Retry-After`. |
| The first attempt failed with 422, 404 or 409 (for example, out of stock) | Nothing was stored, because the transaction rolled back. The key is still free, so the client may retry with it after fixing the cart. |
| The first attempt was declined (402) | The decline is stored, so retrying with the same key replays the 402. Paying with another card is a new attempt, and the UI creates a new key for it. |

**Why use the same transaction.** The key, the order and the stock change are committed or rolled back together. There can never be an order without its key, or a key that points at nothing. The mechanism uses `INSERT … ON CONFLICT DO NOTHING` on the primary key. When two requests race, PostgreSQL makes the second wait for the first to finish, so we need no `IN_PROGRESS` state.

**Where it lives**
- `IdempotentCheckout`, in the application layer, wraps the `Checkout` use case. It uses an `IdempotencyStore` port and shares the Unit of Work.
- It stores the use case's *outcome*. The API turns that outcome into HTTP the same way every time, so a replay is identical to the original response.

**What would change with a real payment provider.** We could no longer hold a database transaction open during a network call to the provider. The flow would then become:
1. Commit the key first, with the status `IN_PROGRESS`.
2. Answer concurrent duplicates with **409** `idempotency-request-in-progress`.
3. Pass our key on to the provider as its own idempotency key.
4. Add a recovery job for requests that never finished.

None of this is needed for the fake gateway. It is recorded here so the design is ready for it.

**Tests**
- The same key with the same body gives one order, one stock decrease and an identical replay.
- The same key with a different body gives 422, and nothing changes.
- 10 parallel requests with the same key create exactly one order.
- The key can be reused after a 409 for missing stock.
- After a 402, the same key replays the 402.
- A missing or malformed key gives 400.
- An expired key is treated as new.

### 7.3 Stock: never sell what we no longer have

**The problem.** Checkouts T1 and T2 both read *stock = 1*, both pass the check, and both write *stock = 0*. Two units are sold, but only one existed.

**The lock protocol**
1. **Every writer that changes the same product rows locks them with `SELECT … FOR UPDATE`, in ascending SKU order.** These writers are checkout and the import commit.
   - Admin edits change a single row and use the `version` check instead (step 6).
   - PostgreSQL locks the rows in the order of the `ORDER BY`.
2. **The second checkout waits.** Once T1 commits, T2 acquires the lock. Under READ COMMITTED, it re-reads the *committed* row, sees stock = 0, and fails cleanly with **409 `insufficient-stock`**:

   ```json
   {
     "type": "urn:ecommerce:problem:insufficient-stock",
     "title": "Some items are no longer available in the requested quantity.",
     "status": 409,
     "items": [{ "sku": "VC-001", "requested": 2, "available": 1 }]
   }
   ```

3. **Deadlocks.** Locking in the same order everywhere means carts {A, B} and {B, A} can never deadlock. If PostgreSQL still reports a deadlock (`40P01`), the use case retries the whole transaction once. That retry is safe because the idempotency row rolled back too.
4. **Lock timeout.** `lock_timeout` is 5 s for checkout and import transactions. A longer wait returns **503 `service-unavailable`** with `Retry-After: 1`.
5. **The domain decides; the database guards.**
   - `Product.decrease_stock` raises `InsufficientStock`.
   - `CHECK (stock >= 0)` is the last line of defence. If it ever fires, that is a bug: it is logged as an error, and the client gets a 409.
6. **Admin edits.** Suppose an admin reads a product at version 5 with stock 10, and then a checkout moves it to version 6 with stock 9. When the admin saves with version 5, they get **409 `version-conflict`** and must reload. No update is lost.
7. **Locks are held for milliseconds.** They last only for the checkout transaction. Calling the payment gateway inside the lock is acceptable **only because it is the in-process fake**. With a real provider, we would reserve stock with an expiry time, pay outside the lock, and then confirm or release the reservation.
8. **It works with several processes.** The lock lives in the database, not in process memory. It holds across multiple uvicorn workers or several app containers.

**Alternatives considered**
- **Conditional `UPDATE … SET stock = stock - :q WHERE stock >= :q`.** It is atomic and fast, but it bypasses the aggregate, so the rule would live in SQL.
- **Optimistic version check with retries.** Under contention, shoppers get needless 409s or slow retry loops.
- **`SERIALIZABLE` isolation.** It is correct, but every caller needs a retry loop for serialization failures.
- **An in-process mutex or a Redis lock.** A mutex fails with more than one worker. Redis is extra infrastructure, and the database already provides row locks.

**Tests**, all against real PostgreSQL through Testcontainers:
- **Race.** 20 parallel checkouts on separate connections compete for the last unit. Exactly **1 returns 201** and **19 return 409**. Afterwards the stock is 0 and there is exactly one `StockDecreased` audit entry.
- **Deterministic interleaving, with no `sleep`.** A test double of the gateway holds T1 *inside* the lock using a latch. The test asserts that T2 is still blocked, then releases the latch and asserts that T2 gets a 409.
- **Opposite order.** Carts {A, B} and {B, A} are submitted in parallel. Both succeed, and there is no deadlock.
- **Stale admin edit.** An admin saves after a checkout has changed the product, and gets 409.
- **Database guard.** A direct SQL `UPDATE` to stock = -1 is rejected by the CHECK constraint.

---

## 8. Testing strategy (TDD)

### 8.1 Test pyramid

| Level | Scope | Tooling | Speed |
|-------|-------|---------|-------|
| Unit: domain | Value objects, aggregates and policies. Pure code with no I/O, plus property-based tests. | pytest, hypothesis | ms |
| Unit: application | Use cases with **in-memory fakes** for repositories and gateways | pytest | ms |
| Integration | Repositories, migrations, CHECK constraints, locking and the CSV reader, all against **real PostgreSQL** in a Testcontainers container (one per session, isolated per test) | pytest, testcontainers | seconds |
| API | Full HTTP flow through FastAPI on real PostgreSQL, including the **golden sample-CSV review workflow** | pytest, httpx | seconds |
| Architecture | Layer rules and the no-comments rule | import-linter, script | seconds |
| Frontend component | Screens and hooks, with the API mocked by MSW | Vitest, RTL, MSW | seconds |
| E2E | The real compose stack: import → review → commit → search → buy → stock decreases | Playwright | ~1–2 min |

### 8.2 TDD discipline

- We follow the red → green → refactor cycle. Where it makes sense, the failing test gets its own `test:` commit before the `feat:` commit, so the history shows the TDD.
- Test names describe behaviour, for example `test_zero_price_row_needs_review_and_suggests_gift`.
- **Coverage gates:**
  - domain and application ≥ 95%
  - the whole backend ≥ 85%
  - the frontend ≥ 80%

### 8.3 Architecture enforcement

`import-linter` enforces three contracts:

1. `*.domain` does not import `fastapi`, `sqlalchemy`, `pydantic`, `infrastructure` or `api`.
2. `*.application` does not import `infrastructure` or `api`.
3. `ordering` does not import `catalog.domain`.

### 8.4 No-comments enforcement (CC-10)

`testing/scripts/check_no_comments.py` scans the source for comments and fails if it finds any.
- Python files are read with the `tokenize` module.
- `.ts` and `.tsx` files are read with the TypeScript scanner.
- Docstrings count as comments.

The check runs in CI and as a pre-commit hook.

### 8.5 The runner: `testing/run.py` (PR-04)

This is a standard-library-only command-line tool, and it is the single way to run anything: locally, by the AI, and in CI. Because CI calls the same runner, local runs and CI behave the same.

| Command | What it does |
|---------|--------------|
| `python testing/run.py backend [unit\|integration\|api\|arch]` | pytest suites |
| `python testing/run.py frontend` | Vitest |
| `python testing/run.py e2e` | Starts the compose stack, then runs Playwright |
| `python testing/run.py lint` / `typecheck` / `nocomments` | Static checks |
| `python testing/run.py all` | The full CI pipeline, in CI order |
| `python testing/run.py script <name> [args]` | Runs `testing/scripts/<name>.py` with an isolated interpreter (`-I`) |
| `python testing/run.py db up\|down` | Starts or stops the local dev PostgreSQL |

The first helper scripts will be:
- `profile_csv.py` and `simulate_import.py`. These turn the inline analysis done in Session 1 into proper scripts.
- `check_no_comments.py`
- `smoke_test.py`

---

## 9. Repository structure

```
E-commerce/
├── backend/
│   ├── pyproject.toml              (dependencies, ruff, mypy, import-linter, pytest config)
│   ├── alembic.ini
│   ├── migrations/
│   └── src/ecommerce/
│       ├── main.py                 (composition root / app factory)
│       ├── shared_kernel/
│       │   ├── domain/             (Money, base errors)
│       │   ├── application/        (UnitOfWork, Clock and IdempotencyStore ports)
│       │   ├── infrastructure/     (async engine, UoW implementation, idempotency store, settings, logging)
│       │   └── api/                (problem_details.py, exception handlers, Pydantic error mapping)
│       ├── catalog/
│       │   ├── domain/             (product.py, value_objects.py, import_batch.py, policies.py, repository.py, errors.py)
│       │   ├── application/        (products/, imports/, dto.py)
│       │   ├── infrastructure/     (orm.py, repositories.py, csv_reader.py)
│       │   └── api/                (products_router.py, imports_router.py, schemas.py)
│       └── ordering/
│           ├── domain/             (order.py, errors.py, repository.py)
│           ├── application/        (checkout.py, ports.py)
│           ├── infrastructure/     (orm.py, repositories.py, fake_payment_gateway.py, catalog_acl.py)
│           └── api/                (router.py, schemas.py)
├── frontend/
│   ├── package.json, vite.config.ts, tsconfig.json
│   └── src/{app,api,features,components}/
├── testing/                        ← every test and every script (PR-03, PR-04)
│   ├── run.py                      (the single runner)
│   ├── backend/{unit,integration,api,architecture}/ + conftest.py
│   ├── frontend/                   (Vitest + RTL + MSW specs)
│   ├── e2e/                        (Playwright)
│   ├── fixtures/                   (sample_products.csv + edge-case CSVs)
│   └── scripts/                    (check_no_comments.py, profile_csv.py, simulate_import.py, smoke_test.py)
├── docs/                           (TECHNICAL_ARCHITECTURE.md, JOURNAL.md, PROMPT_HISTORY.md)
├── Documents/                      (git-ignored: the challenge PDF and CSV as received)
├── Dockerfile                      (multi-stage build: node build → python runtime, non-root)
├── docker-compose.yml              (app + db)
├── .dockerignore                   (excludes testing/, docs/, Documents/, node_modules, .git)
├── .gitignore
├── .github/workflows/ci.yml        (calls testing/run.py)
└── README.md
```

**A note on `testing/frontend`.** Vitest runs from `frontend/` with `include` set to `../testing/frontend/**`. The spec files live outside `frontend/`, but imports such as `react` must still resolve from `frontend/node_modules`. A smoke spec in Phase 0 proves this works before any feature work starts. If the setup turns out to be fragile, the fallback will be logged in the journal.

---

## 10. Delivery: Docker and CI

### Dockerfile

The **Dockerfile** builds **one application image** in three stages:

1. `node:22-alpine` builds the SPA.
2. `python:3.13-slim` with `uv` installs the dependencies.
3. The runtime stage copies in the venv and the SPA's `dist` folder. It runs as a **non-root** user and has a `HEALTHCHECK` on `/health`. Its entrypoint runs `alembic upgrade head` and then starts `uvicorn`.

### docker-compose.yml

**docker-compose.yml** defines two services:
- `db`: `postgres:17-alpine`, with the named volume `pgdata` and a `pg_isready` healthcheck.
- `app`: the image above, which starts only after `db` is healthy. It reads its connection from `DATABASE_URL` and listens on port 8000.

### Running it

- **Start everything with one command:** `docker compose up --build`.
- **Run the app container alone:** `docker run -e DATABASE_URL=… -p 8000:8000 <image>` works against any reachable PostgreSQL.
- **Seed data (optional):** `SEED_SAMPLE_CSV=true` loads the sample when the stack first starts. It goes through the same import with policies set to auto-resolve. It is off by default, so reviewers can try the review workflow themselves.

### CI (GitHub Actions)

CI calls `python testing/run.py all`. The pipeline runs these steps in order:

1. ruff
2. mypy
3. import-linter
4. no-comments check
5. pytest, with Testcontainers
6. eslint, tsc and Vitest
7. docker build
8. Playwright against the compose stack

---

## 11. Questions

### 11.1 Answered (revision 2)

| ID | Answer | Journal |
|----|--------|---------|
| Q-01 | The CSV was downloaded on **2026-11-20**. The exact time is unknown, so the README gives only the date. | D-023 |
| Q-03 | Zero and empty values are **flagged for review** rather than rejected. A zero price can be confirmed as a **gift** (tagged). The rule is configurable and is raised with the customer (CQ-01, CQ-02). | D-031, D-032, D-034 |
| Q-06 | **Update** existing products, but only after the importing user **confirms** each change, shown as a field diff. The rule is configurable and is raised with the customer (CQ-03). | D-033 |
| Q-08 | `testing/` holds **all** tests and scripts, plus the `run.py` runner. | D-024 |
| Q-09 | **`Documents/` stays out of git.** | D-036 |
| Q-10 | **PostgreSQL only.** | D-025 |
| Q-14 | Rows flagged for a **zero or empty** value are editable. Rejected rows are only listed. **Every edit is audited** with its value before and after (§6.4). | D-037, D-039 |
| Q-02 | Accepted the default: the `<script>` name is **rejected**, and the SQL-looking name is accepted as plain text. | D-038 |
| Q-07 | Accepted the default: **no authentication** (a known gap). The actor is the name the reviewer enters. | D-038, D-040 |
| Q-11 | Accepted the default: **guest checkout** with name and email. | D-038 |
| Q-12 | Accepted the default: a **weight of 0 is flagged** for review. A stock of 0 is not. | D-038 |
| Q-13 | Accepted the default: **one app image plus PostgreSQL**, started together with `docker compose up`. | D-038 |

### 11.2 Still open for you

None at the moment.

### 11.3 Questions for the customer (business stakeholder)

These rules belong to the business, not to engineering. We built a working default for each and made it configurable (§6.3). The README lists them under "Questions we would ask the business".

| ID | Question | Default until answered |
|----|----------|------------------------|
| CQ-01 | Are zero-price products gifts or promotions? Can a customer order them on their own, and is there a quantity limit? Or should zero prices be rejected? | Review them as gifts. A gift is a normal product priced at 0, and an order totalling 0 skips the payment step. |
| CQ-02 | When a row has empty required fields, should staff complete it during the import, or should the row be rejected so the source file gets fixed? | Staff complete it during review. |
| CQ-03 | If an imported SKU already exists, should we update the product after confirmation, update it silently, or refuse the row (create only)? | Update after confirmation. |
| CQ-04 | Is the CSV `stock` value the **absolute** quantity on hand, or a quantity **received** that should be added to current stock? | Absolute quantity. |
| CQ-05 | If the same SKU appears more than once in one file, which row wins? | The last row. |
| CQ-06 | Is the store single-currency USD? | Yes, USD only. |
| CQ-07 | Is the category list a fixed taxonomy, or can it be open-ended? | Open-ended, normalised. |
| CQ-08 | Should re-importing an archived product's SKU bring the product back? | Yes, after confirmation (it appears in the update diff). |
| CQ-09 | How long must the audit log and import history be kept? Is there a regulatory requirement? Do the actor names count as personal data that must be removable (for example, under GDPR)? | Keep them forever, and never purge. |
| CQ-10 | Do suppliers ever reuse an SKU for a different product? Should a CSV be allowed to rename products, and how far? | Treat an SKU as the same product only while the name stays similar (trigram similarity ≥ 0.5). Anything else is rejected as `sku_belongs_to_different_product` (§6.5). |

---

## 12. Phased plan

Each phase is a vertical slice that ends with green CI and a **review gate with you**. Every phase follows TDD, with the tests in `testing/` written first.

### Phase 0: Walking skeleton

- **Repository setup**
  - The repo layout from §9.
  - `.gitignore`, which includes `Documents/`, and `.dockerignore`.
- **Runner and helper scripts.** All of these are written test-first:
  - `testing/run.py`.
  - `check_no_comments.py`.
  - `profile_csv.py` and `simulate_import.py`, which codify the Session 1 analysis.
- **Backend**
  - Set up `uv`, ruff, mypy, import-linter and pytest.
  - **First tests:** `GET /health` returns 200, and `GET /ready` reaches PostgreSQL through Testcontainers.
- **Frontend**
  - Set up Vite, React, TypeScript, ESLint and Vitest.
  - **First test:** the app shell renders from `testing/frontend`.
- **Delivery**
  - The Dockerfile and `docker-compose.yml` (app + db).
  - CI calling `run.py all`.
  - A README stub that includes the CSV download date (2026-11-20).
- **Exit criteria:** `docker compose up` shows the shell page, `/ready` is green, and CI is green.

### Phase 1: Catalog core (backend)

- Value objects, the `Product` aggregate and the GIFT invariant, covered by unit and property tests.
- The repository port, the SQLAlchemy adapter, Alembic migrations (including `pg_trgm` and the CHECK constraints) and the Unit of Work, covered by integration tests.
- The CRUD and search use cases, then the API: optimistic locking and gift confirmation for zero prices.
- **One error format (§4.6):** the Problem Details handlers, the mapping from Pydantic errors to codes, `ValidationIssue` with all issues collected, and a contract test across every endpoint.
- **Audit foundation:**
  - domain events on `Product`;
  - the Unit of Work writes them to `audit_log` in the same transaction;
  - the append-only trigger;
  - the `X-Actor-Name` header;
  - `GET /products/{id}/history`.
- **Exit criteria:** full product CRUD and search work over HTTP, every product change is audited, and all layer contracts pass.

### Phase 2: Catalog UI (admin CRUD and storefront search)

- A typed API client and TanStack Query hooks.
- The admin product table and form, including the zero-price gift dialog, archive and restore.
- The "Who is reviewing?" prompt, and the product history timeline.
- Storefront search with filters, pagination, the product detail page and the Gift badge.
- **Exit criteria:** CC-02, CC-05, and the CRUD and search parts of CC-07.

### Phase 3: CSV import with review (backend and UI)

- **Backend**
  - The policies (§6.3), each variant covered by tests.
  - The `ImportBatch` aggregate, the CSV reader adapter, and the `StartImport`, `ResolveImportRow`, `CommitImport` and `DiscardImport` use cases.
  - Stale-row detection and batch expiry.
  - Raw lines kept verbatim, the history of each row's resolutions, and the import events written to the audit log.
- **Issue catalog (§6.2):** every warning, review and error code gets its own test, as do the file-level errors.
- **SKU identity check (§6.5):** against the database, within the file, and re-checked at commit time. It has its own fixture for each case.
- **Golden test.** The sample produces:
  - 2 `blank`, 2 `rejected` and 6 `needs_review` rows;
  - 84 `create` and 3 `superseded` rows;
  - 3 warnings (1 currency, 2 duplicate SKU);
  - 0 identity conflicts.

  After the review rows are resolved, there are up to 90 products. Re-importing the same file then reports 84 unchanged.
- **Edge-case fixtures:** a BOM, a missing column, an oversized file and a non-UTF-8 file.
- **UI:** the upload screen and the review screen (inline editor, update diffs, confirm all, commit).
- **Exit criteria:** CC-03 and CC-04.

### Phase 4: Purchase (backend and UI)

- **Backend**
  - The `Order` aggregate, the `PaymentGateway` port, the `FakePaymentGateway` and the `CatalogGateway` anti-corruption layer.
  - The `Checkout` use case (§7.1): server-side pricing, zero-total gift orders and the decline path.
  - Idempotency (§7.2): the `idempotency_keys` table, the fingerprint, replay, the 422 for a reused key, and every test listed in §7.2.
  - The stock lock protocol (§7.3): SKU-ordered `FOR UPDATE`, `lock_timeout`, a single retry after a deadlock, and the race, latch, opposite-order and stale-edit tests.
- **UI:** the cart, the checkout form, the confirmation page, and handling of declined payments.
- **Exit criteria:** CC-06, and the purchase part of CC-07.

### Phase 5: Hardening and E2E

- **Playwright tests against the compose stack:**
  - import → review → commit → search → buy → stock decreases;
  - a declined card leaves stock unchanged.
- **Hardening:**
  - security headers and a CSP;
  - upload limits;
  - structured logs with request IDs.
- **Docker:** a non-root user, healthchecks, volumes, and an image size check.
- **Exit criteria:** CC-08, and the full pipeline green, including E2E.

### Phase 6: Documentation and delivery

- **README:**
  - an overview;
  - the CSV download date (2026-11-20);
  - how to run the app, via compose or natively;
  - an architecture summary, the decisions, the approach and the **alternatives considered**;
  - the **questions we would ask the business** (§11.3);
  - known gaps and next steps;
  - how AI was used, linking to `docs/PROMPT_HISTORY.md`.
- A final no-comments sweep, and a completeness check of the journal.
- Push to GitHub under `Ortiz-100323`, once you give the go-ahead.
- **Exit criteria:** CC-09 through CC-12.
