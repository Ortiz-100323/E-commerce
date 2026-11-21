# ECOM-008: Storefront search UI

| Field | Value |
|---|---|
| Type | Story (frontend) |
| Phase | 2 |
| Status | **Backlog** |
| Depends on | ECOM-006 |
| Architecture | §5, CC-05, CC-07 |

## Context

Shoppers find products by searching and filtering.

## Scope

- `/`: search box, filters (category, price range, in stock, gift), sorting and pagination, kept in the URL.
- A "Gift" badge on gift products.
- `/products/:id`: product detail; "Add to cart" is disabled when the product is out of stock.

## Acceptance criteria

1. Typing a query and applying filters updates the results and the URL.
2. Reloading the page keeps the same search.
3. Gift products show the badge.
4. Out-of-stock products cannot be added to the cart.

## Test plan

- Component specs with MSW for each criterion.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
