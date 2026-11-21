# ECOM-013: Ordering: Order aggregate, fake payment and checkout

| Field | Value |
|---|---|
| Type | Story (backend) |
| Phase | 4 |
| Status | **Backlog** |
| Depends on | ECOM-005 |
| Architecture | §3.1, §4.2 (`Order`), §7.1, CC-06 |

## Context

Shoppers buy products. Payment is faked, and the server decides every price.

## Scope

- The `ordering` context: the `Order` aggregate with `OrderLine` snapshots.
- The `PaymentGateway` port and `FakePaymentGateway` (4242… approved, 4000…0002 declined, other Luhn-valid numbers approved).
- The `CatalogGateway` anti-corruption port, so `ordering` never imports catalog's domain.
- The `Checkout` use case (§7.1), `POST /orders` and `GET /orders/{id}`.
- Only the last 4 card digits are stored.

## Acceptance criteria

1. Lines are priced from the database; prices sent by the client are ignored.
2. A declined card returns 402, the order is `PAYMENT_FAILED` and stock is unchanged.
3. An approved card returns 201, the order is `PAID` and stock decreases, with an audit entry.
4. A zero-total gift order is paid without calling the gateway.
5. An archived or out-of-stock product returns 409 `product-not-sellable`.
6. The full card number appears nowhere in the database, responses or logs.

## Test plan

- Aggregate unit tests; use-case tests with fakes; API tests on real PostgreSQL; an import-linter contract that `ordering` does not import `catalog.domain`.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
