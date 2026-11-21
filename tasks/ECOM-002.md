# ECOM-002: Catalog domain: value objects and the Product aggregate

| Field | Value |
|---|---|
| Type | Story (backend) |
| Phase | 1 |
| Status | **Backlog** |
| Depends on | ECOM-001 |
| Architecture | §4.2 |

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

## Definition of done

- Acceptance criteria pass, written test-first; domain coverage ≥ 95%.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
