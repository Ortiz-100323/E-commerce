# ECOM-013: Ordering: Order aggregate, fake payment and checkout

| Field | Value |
|---|---|
| Type | Story (backend) |
| Phase | 4 |
| Status | **Done**: accepted by the owner after the portal test of the purchase (prompt #034) |
| Depends on | ECOM-005 |
| Architecture | §3.1, §4.2 (`Order`), §4.5, §7.1, CC-06 |
| Journal | D-095, D-096, D-099 |

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

## Plan (D-095, accepted by the owner in prompt #030)

### 1. Domain: `ordering/domain/` (no framework, imports only `shared_kernel.domain`)

- **Value objects:**
  - `OrderId` (UUID);
  - `CustomerName`: trimmed, 1–200 characters, no control characters;
  - `Email`: trimmed, lower-cased, at most 254 characters, one `@` and a dot in the domain part (no new package);
  - `Quantity`: a whole number from 1 to 10,000;
  - `PaymentCard`: 12–19 digits after removing spaces and dashes, Luhn-valid, an expiry month and year not in the past, and a 3–4 digit CVC. Its text form shows only the last 4 digits, so a card can never be logged by accident. The CVC is never stored anywhere.
- **`merge_lines(requested)`:** merges duplicate SKUs (upper-cased) and sorts them by SKU, so the products are locked in SKU order.
- **`Order` aggregate:**
  - `Order.place(order_id, customer, lines, at)` creates a `PENDING` order. Each `OrderLine` is a snapshot of the SKU, product id, name, unit price, quantity and gift flag. The line total is the unit price × quantity, and the order total is the sum of the lines.
  - `mark_paid(payment_reference, card_last4, at)` and `mark_payment_failed(reason, card_last4, at)`. Only a `PENDING` order can move, and only once.
  - Invariants: at least 1 line, quantities ≥ 1, unique SKUs, total = sum of lines.
  - Events: `OrderPaid` and `OrderPaymentFailed`, each with the lines and total, for the audit log.
- **Errors:** `OrderNotFound` (404), `ProductsNotSellable(items)` and `NotEnoughStock(items)` (409). Bad card or customer values are `DomainValidationError` (422).
- **`OrderRepository`** port: `add`, `get`.

### 2. Application: `ordering/application/`

- **Ports:**
  - `CatalogGateway`, the anti-corruption port: `lock_for_sale(skus) -> dict[str, SaleProduct]` and `decrease_stock(sku, quantity, order_reference)`. `SaleProduct` is ordering's own snapshot (product id, SKU, name, price, stock, gift, active), so `ordering` never sees catalog's `Product`.
  - `PaymentGateway`: `charge(amount, card, reference) -> PaymentResult(approved, reference, decline_reason)`.
  - `OrderingUnitOfWork`: `orders`, `catalog`, `commit`, `rollback`.
- **`Checkout`**, following §7.1 without the idempotency step (that is ECOM-014):
  1. merge the lines;
  2. lock the products in SKU order;
  3. check every line: unknown, archived or out of stock → `ProductsNotSellable` (all items at once); more than available → `NotEnoughStock` (all items at once); nothing is written;
  4. price every line **from the locked rows**; the client never sends a price we read;
  5. place the order;
  6. total 0 → `PAID` with no card needed and no gateway call (CQ-01); otherwise the card is required (422 `payment` `required`), then the gateway is charged:
     - approved → decrease the stock of each line → `PAID`;
     - declined → `PAYMENT_FAILED`, stock untouched;
  7. save and commit; return the order.
- **`GetOrder`**.

### 3. Infrastructure

- **Migration 0007:** `orders` (id, status, customer name, email, total, currency, payment reference, card last 4, decline reason, created and paid times) and `order_lines` (order id, SKU, product id, name, unit price, quantity, gift, line total). CHECKs mirror the invariants: known status, total ≥ 0, quantity ≥ 1, unit price ≥ 0, last 4 = exactly 4 digits, one line per SKU per order.
- `SqlAlchemyOrderRepository`, `FakePaymentGateway` (`4242 4242 4242 4242` approved, `4000 0000 0000 0002` declined, other Luhn-valid numbers approved).
- `SqlAlchemyOrderingUnitOfWork`: one session for the order and the catalog, so the order, the stock change and the audit entries are committed together, or not at all.
- **Where the catalog adapter lives:** `ecommerce/integration/catalog_sales.py`, outside both contexts. It implements `CatalogGateway` with the catalog's existing `lock_by_skus` (row locks plus SKU advisory locks, D-093) and `Product.decrease_stock`, and passes the `StockDecreased` events on to the audit log. `main.py` wires it in. This way `ordering` doesn't import catalog at all, not even indirectly.

### 4. API

- **`POST /orders`:**
  - body `{customer: {name, email}, lines: [{sku, quantity}], payment?: {card_number, expiry_month, expiry_year, cvc}}`, with 1 to 50 lines;
  - unknown fields in a line (such as a `unit_price`) are ignored, so they are never read (AC1); unknown fields elsewhere give 422;
  - 201 with `Location` and the order (`PAID`); 402 `payment-declined` with `order_id` and the order (`PAYMENT_FAILED`); 409 `product-not-sellable` or `insufficient-stock`; 422 for bad input.
  - No `X-Actor-Name`: shoppers don't log in. The audit actor is **"Shop checkout"**, and the order id goes in the entry's context.
- **`GET /orders/{id}`:** 200 with the order, or 404.
- **An order in a response:** id, status, customer, lines (SKU, name, unit price, quantity, gift, line total), total, currency, card last 4, payment reference, created and paid times. Money is sent as strings.
- **Problem catalog:** `product-not-sellable` gains the reason `unknown` for a SKU that doesn't exist, so a cart gets every problem in one answer (instead of a 404 for the first unknown SKU).
- **Import contracts:**
  - ordering layers;
  - `ordering` must not import `ecommerce.catalog` (stricter than §8.3);
  - `catalog` must not import `ecommerce.ordering`;
  - `ordering.domain` imports only `shared_kernel.domain`;
  - `ordering`'s domain and application stay free of frameworks.

### 5. Tests, written first

- Unit tests: value objects (Luhn, expiry, email, masking), `merge_lines` and the `Order` aggregate.
- Use-case tests with in-memory fakes: every path of `Checkout`.
- Integration tests on PostgreSQL: the repository, migration 0007 round trip, the CHECK constraints, and the adapter decreasing stock with an audit entry.
- API tests on PostgreSQL: every acceptance criterion and every failure case below.
- The contract test: `POST /orders` errors are Problem Details.
- A card-number test: the full number appears in no response, no log line and no database table (a dump of every text column is searched).

## Failure cases and retries (D-072)

| Situation | What the caller gets | Result |
|---|---|---|
| No lines, more than 50 lines, quantity 0, negative or not a whole number | 422 on the line field; nothing written | Pass |
| Bad name or email | 422 on `customer.name` / `customer.email` | Pass |
| Card number not Luhn-valid, expired card, bad CVC | 422 on the `payment` field; **the number is not echoed**; no order is created | Pass |
| A cart with a price above 0 and no card | 422 `payment` `required`; nothing written | Pass |
| A SKU that doesn't exist, an archived product, or one with 0 stock | 409 `product-not-sellable` with `items[] {sku, reason}` (`unknown`, `archived`, `out_of_stock`); nothing written | Pass |
| A quantity above the stock | 409 `insufficient-stock` with `items[] {sku, requested, available}`; nothing written | Pass |
| A client-sent price | Ignored; the order is priced from the database | Pass |
| Declined card (`4000 0000 0000 0002`) | 402 `payment-declined` with `order_id`; the order is stored as `PAYMENT_FAILED`; stock unchanged; one audit entry | Pass |
| Unknown order id / malformed id on `GET` | 404 / 422 | Pass |
| Database down | 503 `service-unavailable` (existing handler) | Pass |
| **Retry:** the same checkout sent twice | Built together with ECOM-014: the `Idempotency-Key` turns a retry into a replay of the first answer, with no second order, charge or stock change | Pass (see ECOM-014) |
| **Stock:** two checkouts for the same product | Products are locked in SKU order for the whole checkout, and stock is decreased only after the payment is approved, in the same transaction. The database CHECK `stock >= 0` is the last guard. The 20-parallel-checkout race test is ECOM-014's AC5. | Pass |

## Verification (2026-11-22)

Written test-first: the new tests were run before any ordering code existed and failed (the modules didn't exist), then the code was written until they passed.

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | Lines are priced from the database; prices sent by the client are ignored | **Pass** | API test: a line sent with `unit_price`, `price` and `total` of 0.01 is priced at 89.99 from the catalog; the order total is 179.98. Use-case test: the order is priced from the locked products. |
| 2 | A declined card returns 402, the order is `PAYMENT_FAILED` and stock is unchanged | **Pass** | API test on PostgreSQL: 402 `payment-declined` with `order_id` and the order; `GET /orders/{id}` shows `PAYMENT_FAILED`, `card_declined`, last 4 `0002`; stock stays 10; no `product.stock_decreased` entry; one `order.payment_failed` entry. |
| 3 | An approved card returns 201, the order is `PAID` and stock decreases, with an audit entry | **Pass** | API test: 201 with `Location`; `PAID`, last 4 `4242`, a `fake_…` payment reference; stock 10 → 8; exactly one `product.stock_decreased` entry by "Shop checkout" naming the order, plus one `order.paid` entry. |
| 4 | A zero-total gift order is paid without calling the gateway | **Pass** | API and use-case tests with a gateway that fails if it is called: a gift order with no card is `PAID`, total 0.00, and takes its stock. |
| 5 | An archived or out-of-stock product returns 409 `product-not-sellable` | **Pass** | API test: one cart with an archived, an out-of-stock and an unknown SKU gets one 409 listing all three reasons; no order and no key are stored. The live smoke check also buys the archived SMOKE-TEST product and gets this 409. |
| 6 | The full card number appears nowhere in the database, responses or logs | **Pass** | API test: an approved, a declined and two invalid checkouts, then every text, varchar, JSON and array column of every table is searched, with every response body and the captured logs (DEBUG level), for each full number with and without spaces. None is found; a CVC is never echoed either. Unit test: a card prints as `PaymentCard(**** 4242)`. |

**Also proven:** orders round-trip through PostgreSQL; migration 0007 downgrades and upgrades cleanly; the database refuses an unknown status, a non-digit last 4, a negative total, a quantity of 0, a negative price and a line total that doesn't match; 8 import-linter contracts hold, including "ordering and catalog never import each other".

**Totals after code review (ECOM-013 and ECOM-014 together):** 132 new backend tests and 2 live smoke checks. The complete suite passes 866 backend tests with 99.62% scoped coverage. The backend container is rebuilt and the owner's database is on migration 0008.

## Business view

- **What was built:** the shop's checkout, behind the scenes.
  - An order is priced by the shop from its own catalog, never from what the browser sends.
  - The fake card is charged, and only an approved payment takes the stock.
  - A declined card is kept as a failed order and takes nothing.
  - Free gift orders go through without a card.
  - Only the last 4 digits of a card are kept.
- **Why:** challenge rule CC-06 (purchase products with a fake payment).
- **Main goal:** an order can never be paid at a price the shop didn't set, never sells stock that isn't there, and never stores a card number.
- **Human testable or background:** testable in **Swagger** (http://localhost:8001/docs, section **orders**). The checkout screens come in ECOM-015.
- **What to test:** see prompt #030 of the prompt history.

## Test plan

- Aggregate unit tests; use-case tests with fakes; API tests on real PostgreSQL; an import-linter contract that `ordering` does not import `catalog.domain`.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.

## Code review round 3 (2026-11-22)

Two boundary defects were reproduced and fixed:

- An email containing a NUL control character passed the simple email pattern and reached PostgreSQL, which cannot store that byte. Email validation now rejects every control character with a normal 422 before locking, charging or writing anything.
- The largest cart allowed by the public limits (50 lines, maximum catalog price and quantity 10,000) produced a valid domain total that overflowed `orders.total numeric(16,2)` during commit. Migration 0008 widens the total to `numeric(18,2)`, which exactly covers the maximum valid order; a PostgreSQL round-trip regression proves it.

No other defect was found in the order aggregate, server-side pricing, payment outcomes, stock changes, audit mapping or sensitive-value handling.
