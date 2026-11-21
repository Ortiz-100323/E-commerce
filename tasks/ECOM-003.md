# ECOM-003: Catalog persistence: schema, repository and Unit of Work

| Field | Value |
|---|---|
| Type | Story (backend) |
| Phase | 1 |
| Status | **Done** |
| Depends on | ECOM-002 |
| Architecture | §4.1, §4.4, §8.3 |
| Journal | D-071, D-072 |

## Context

Products must be stored in PostgreSQL without leaking the ORM into the domain.

## Scope

- Alembic migration: `products` table with `NUMERIC(12,2)` price and `NUMERIC(10,3)` weight, CHECK constraints mirroring the invariants, a unique index on `sku`, the `pg_trgm` extension and GIN trigram indexes on name, SKU and description.
- SQLAlchemy imperative mapping of `Product`.
- `ProductRepository` interface in the domain and its SQLAlchemy implementation.
- Optimistic locking on the `version` column.

## Acceptance criteria

1. A product round-trips through the repository with every field intact, including Decimal precision.
2. The database itself rejects a negative price, negative stock, negative weight, and a zero price without the gift tag.
3. A second product with the same SKU is rejected by the unique index.
4. Saving with a stale `version` raises a version-conflict error.
5. The migration upgrades and downgrades cleanly.

## Test plan

- Integration tests against real PostgreSQL for each criterion, including direct SQL writes that the CHECK constraints must block.

## Verification (2026-11-21)

| # | Criterion | Result |
|---|---|---|
| 1 | Round trip with every field intact | Pass. Seven product shapes (an ordinary product; a free gift with 0 stock and 0 weight; a paid gift with no description; every maximum; the smallest price and weight; Unicode text with a line break; an SQL-looking name) plus an archived product come back with identical values, versions and timestamps (to the microsecond). Decimals keep their exact digits (`89.99`, `0.800`). |
| 2 | The database rejects rule breakers | Pass. Direct SQL writes of a negative price, negative stock, negative weight, a zero price without GIFT, an unknown tag, an unknown status and version 0 are each blocked by the named CHECK constraint. An UPDATE that takes stock below 0 is blocked too. |
| 3 | Duplicate SKU rejected | Pass. Direct SQL hits `uq_products_sku`; through the repository it raises `DuplicateSku`, case-insensitively (`rs-001` against `RS-001`), and the same transaction can still save other products. |
| 4 | Stale version raises a conflict | Pass. Two readers load version 1; the first saves (version 2); the second gets `VersionConflict` (expected 1, current 2) and nothing of its change is stored. Saving a product that was never stored raises `ProductNotFound`. |
| 5 | Migration upgrades and downgrades cleanly | Pass. The test downgrades to `0001` (products gone, weather kept), upgrades again, and a second test finds no drift between the migrations and the table definitions. The live stack migrated to `0002` on start-up. |

**Also in this ticket:** the `CatalogUnitOfWork` port and its SQLAlchemy version; GIN trigram indexes on name, SKU and description (checked); a catalog layers contract.

## Failure cases and retries (added after review, D-072)

| Situation | Result | Test |
|---|---|---|
| Two buyers race for the last unit | The first sale is stored; the second save raises `VersionConflict`; stock stays 0 | Pass |
| A sale after the stock reached 0 | `InsufficientStock` (requested 1, available 0); nothing changes | Pass |
| A sale larger than the stock | `InsufficientStock` (requested 3, available 2); stored stock unchanged | Pass |
| A sale of an archived product | `ProductNotSellable` (reason `archived`); stock unchanged | Pass |
| A save refused for a stale version, retried after reloading | The retry succeeds and keeps both changes | Pass |
| The same new product added twice (a retried create) | `ProductAlreadyExists`; one row; the transaction stays usable | Pass, **bug fixed**: this used to escape as a raw database error |
| A second product with the same SKU | `DuplicateSku` | Pass (criterion 3) |
| Saving a product that was never stored | `ProductNotFound` | Pass (criterion 4) |
| Direct SQL breaking a rule (negative values, free without gift, stock below 0 by UPDATE) | Refused by the named CHECK constraint | Pass (criterion 2) |

The HTTP responses for these errors (409, 404, 422) arrive with the endpoints in ECOM-005. Checkout retries (`Idempotency-Key`) and row locking come in ECOM-014.

**Totals:** 41 new tests. The `ci` container passes: lint, mypy over 59 files, 5 contracts, no comments, 20 tooling tests, 301 backend tests with 100% domain coverage, 6 frontend tests and the smoke checks.

## Business view

- **What was built:** the product storage. Products can now be saved in the database and read back exactly as they were. The database also has its own safety net: it refuses negative prices, negative stock, free products that aren't gifts and duplicate SKUs, even if a bug or a manual SQL command tries to write them.
- **Why:** the rules from ECOM-002 lived only in memory. Now products are kept. Two admins editing the same product at the same time can't silently overwrite each other: the second save is refused, so the screen (ECOM-007) can say "this product changed, reload it". The same protection means two buyers can't both take the last unit.
- **Main goal:** products are stored safely and exactly (to the cent and the gram), and fast product search is prepared.
- **Human testable or background:** background only. The first screen and API come in ECOM-005; that's when you can test products by hand.
- **What to test:** nothing by hand yet. If you'd like a look, the empty `products` table is visible in the database (`docker compose exec db psql -U ecommerce -d ecommerce -c "\d products"`).

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
