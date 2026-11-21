# ECOM-002: Catalog domain: value objects and the Product aggregate

| Field | Value |
|---|---|
| Type | Story (backend) |
| Phase | 1 |
| Status | **Done** |
| Depends on | ECOM-001 |
| Architecture | §4.2, §8.3 |
| Journal | D-068, D-069, D-070 |

## Context

The catalog's business rules live in pure Python, with no framework or I/O, so they can be tested in milliseconds.

## Scope

- Value objects: `Sku`, `ProductName`, `Description`, `Category`, `Price`, `StockQuantity`, `Weight`, `ProductTag` (`GIFT`).
- The `Product` aggregate: identity, state, `version`, status `ACTIVE` / `ARCHIVED`.
- Behaviour: `rename`, `reprice`, `recategorize`, `restock`, `mark_as_gift`, `unmark_gift`, `decrease_stock`, `archive`, `restore`, `is_sellable`.
- Invariant: `price == 0 ⇒ GIFT ∈ tags`.
- Domain events: `ProductCreated`, `ProductChanged` (values before and after), `ProductArchived`, `ProductRestored`, `StockDecreased`.
- Validation collects every issue before raising.

## Acceptance criteria

1. Every rule in the §4.2 value-object table is enforced at construction.
2. A product priced at 0 cannot exist without the GIFT tag, and the tag cannot be removed while the price is 0.
3. `decrease_stock` beyond the available stock raises `InsufficientStock`.
4. Each change records exactly one event with the correct before and after values.
5. Creating a product with several invalid fields reports all of them at once.
6. The domain imports nothing outside the standard library and `shared_kernel.domain`.

## Test plan

- Unit tests for each value object and behaviour.
- Property-based tests (hypothesis) for `Sku` normalisation, `Price` and `StockQuantity`.

## Verification (2026-11-21)

| # | Criterion | Result |
|---|---|---|
| 1 | Every §4.2 value-object rule enforced at construction | Pass. 39 tests: SKU trim, upper case, pattern and length; name trim, length, markup and control characters; description length and control characters (newline allowed); category trim, length and case-insensitive comparison; price ≥ 0; stock ≥ 0; weight ≥ 0 with 3 places; GIFT as the only tag. Upper limits match the database columns (D-068). |
| 2 | Price 0 needs GIFT; GIFT can't be removed at price 0 | Pass, on creation, on `reprice`, on `unmark_gift`, on `revise`, and on rebuilding from stored state. |
| 3 | `decrease_stock` beyond stock raises `InsufficientStock` | Pass, with `sku`, `requested` and `available`; stock is unchanged. 150 generated cases prove stock never goes below 0. |
| 4 | Each change records exactly one event with before and after | Pass for every behaviour. A multi-field `revise` records one event listing only the changed fields; a no-op records nothing. |
| 5 | Several invalid fields reported at once | Pass: seven invalid fields on creation give seven issues, together with the gift rule. |
| 6 | Domain imports only the standard library and `shared_kernel.domain` | Pass. An architecture test reads every `*/domain` package, and a new import-linter contract guards `catalog.domain`. |

**Property tests and coverage (D-069):** the owner approved `hypothesis` and `pytest-cov`. Nine hypothesis properties (200 examples each) cover SKU normalisation, price, stock, and a random sequence of sales and restocks that never takes stock below 0. `run.py backend` now fails if coverage of `catalog.domain` and `shared_kernel.domain` drops below 95%; it is **100%**.

**Totals:** 94 new test functions. The `ci` container passes: lint, mypy over 50 files, 4 contracts, no comments, 20 tooling tests, 260 backend tests with 100% domain coverage, 6 frontend tests and the smoke checks.

## Business view

- **What was built:** the product rules: what makes a valid product (SKU, name, description, category, price, stock, weight, gift tag), what you can do to a product (rename, change price, change category, restock, mark or unmark as a gift, archive, restore, sell stock), and a record of every change, with its old and new value.
- **Why:** these rules are the heart of the catalog. The admin screen, the CSV import and checkout will all go through them, so a bad product can't get in by any route.
- **Main goal:** an invalid product can never exist, stock can never go negative, a free product is always a deliberate gift, and every change leaves a trace for the history.
- **Human testable or background:** background only. There is no screen or API yet; the database arrives in ECOM-003 and the API in ECOM-005, where these rules become visible.
- **What to test:** review the rules in the delivery reply and confirm they match what the business wants. Automatic tests check the behaviour.

## Definition of done

- Acceptance criteria pass, written test-first; domain coverage ≥ 95%.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
