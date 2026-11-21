# ECOM-015: Purchase UI: cart, checkout and confirmation

| Field | Value |
|---|---|
| Type | Story (frontend) |
| Phase | 4 |
| Status | **Backlog** |
| Depends on | ECOM-014, ECOM-006 |
| Architecture | §5, §7.2 (client side), CC-06, CC-07 |

## Context

Shoppers complete a purchase through the UI.

## Scope

- `/cart`: the cart in `localStorage`, with a subtotal from the server.
- `/checkout`: name, email, fake card and pay button; one idempotency key per attempt, reused on retry and replaced when the cart or form changes.
- `/orders/:id`: the confirmation page.
- Declined payments and stock conflicts are explained, with a way to fix the cart.

## Acceptance criteria

1. A shopper can add products, pay with 4242… and see the confirmation.
2. A double-click on pay creates one order.
3. A declined card shows a clear message and lets the shopper try another card.
4. An insufficient-stock response shows which items and how many are available.

## Test plan

- Component specs with MSW for each criterion.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
