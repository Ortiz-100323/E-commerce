# ECOM-015: Purchase UI: cart, checkout and confirmation

| Field | Value |
|---|---|
| Type | Story (frontend) |
| Phase | 4 |
| Status | **Done**: accepted by the owner after the portal test of the purchase (prompt #034) |
| Depends on | ECOM-014, ECOM-006 |
| Architecture | §4.5, §5, §7.2 (client side), CC-06, CC-07 |
| Journal | D-085, D-097, D-099 |

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

## Plan (D-097, accepted by the owner in prompt #032)

### 1. A small backend addition: `POST /orders/quote`

§5 says the cart shows "a subtotal computed by the server", but no endpoint prices a cart without buying it. I propose one:

- Body `{lines: [{sku, quantity}]}`. No key, no card, nothing written, no lock.
- It answers with each line priced from the catalog (name, unit price, line total, gift, how many are available) and its problem, if any: `unknown`, `archived`, `out_of_stock` or `insufficient_stock`. It also returns the total and whether a card is needed (total above 0).
- `QuoteCart` in `ordering.application` uses a new read-only `CatalogGateway.products_for_sale(skus)`, with the same merging and checks as checkout, so the cart and the checkout can never disagree on a rule.
- The final answer still comes from `POST /orders`, which locks and re-checks everything.

### 2. Frontend

- **`api/orders.ts`:** the order types and `quote`, `place(body, key)` and `get(id)`. `request()` gains an `idempotencyKey` option that sends the `Idempotency-Key` header.
- **The cart:**
  - `CartContext` gains `setQuantity`, `remove` and `clear`;
  - the header's "Cart: N items" becomes a link to `/cart`.
- **`/cart`:**
  - one row per product with a quantity field and **Remove**;
  - prices, line totals and the subtotal come from the quote, which is asked again whenever the cart changes;
  - a line with a problem says so and offers the fix: "Only 3 left" → **Use 3**; "No longer sold" or "Out of stock" → **Remove**;
  - **Go to checkout** stays disabled while the cart is empty or has a problem.
- **`/checkout`:**
  - the order summary comes from the quote;
  - fields: **Name**, **Email**, **Card number**, **Expiry (MM/YY)** and **CVC**, checked in the browser with the same rules as the server, which stays authoritative;
  - for a free order the card fields are hidden ("This order is free");
  - the button reads **Pay $189.98**.
- **The idempotency key (§7.2, client side):**
  - `crypto.randomUUID()` creates a key when the checkout opens;
  - the key is reused for a double click, a network error or a 503, so a retry can never charge twice;
  - a new key is made whenever the cart or the form changes, and after a final answer (paid or declined);
  - the button is disabled while a payment is being sent.
- **Answers:**
  - **201:** the cart is emptied and the shopper lands on `/orders/:id`.
  - **402:** "Your card was declined. Nothing was charged and nothing was taken from stock. Try another card." The card fields are cleared and the rest of the form is kept.
  - **409 (`insufficient-stock` or `product-not-sellable`):** the items and what is available are listed, with **Fix my cart**. It sets each quantity to what's available, removes what can't be sold, and returns to the cart.
  - **422:** each error goes under its field (`customer.email` → Email, `payment.card_number` → Card number…).
  - **503 or no connection:** "The shop is busy. Press Pay again: you won't be charged twice." The same key is kept.
- **`/orders/:id`:** "Thank you, Ana. Your order is paid." It shows the order number, the lines, the total, the card ending in 4242 and the payment reference. An unknown id says the order wasn't found.

### 3. Tests, written first

- Backend: unit, use-case and API tests for the quote, including a test that it writes nothing.
- Frontend: component tests with a stateful MSW fake of the orders API, which replays by key like the real server. Every test keeps the page-wide error check (D-085).

## Failure cases and retries (D-072)

| Situation | What the shopper sees | Result |
|---|---|---|
| Empty cart | "Your cart is empty", with a link to the shop; no checkout | Pass |
| A product sold out or archived since it was added | The cart line says so and offers **Remove**; checkout is disabled | Pass |
| A quantity above the stock | "Only N left", with **Use N** | Pass |
| Invalid name, email, card, expiry or CVC | The message under the field; nothing is sent until the browser checks pass; a server 422 is shown the same way | Pass |
| Declined card | The declined message; card fields cleared; a new key for the next attempt | Pass |
| Stock gone between the cart and Pay (409) | The items and what's available, with **Fix my cart** | Pass |
| **Retry:** a double click on Pay | One request; even a second one would reuse the key and be replayed: one order | Pass |
| **Retry:** no connection or 503 | A "press Pay again" message; the same key, so no double charge | Pass |
| **Retry:** pressing Pay after changing the cart or the form | A new key: it's a new request | Pass |
| An unknown order address | "This order was not found." | Pass |
| **Stock:** the screen never computes stock or prices; it shows what the server answers | Prices, totals and availability all come from the quote or the order | Pass |

## Verification (2026-11-22)

Written test-first: the 19 screen tests and the quote tests were run before the screens and the endpoint existed, and failed; then the code was written until they passed.

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | A shopper can add products, pay with 4242… and see the confirmation | **Pass** | Screen test: the cart opens from the header, prices and subtotal come from the server's quote (not the price saved in the cart), **Go to checkout**, name, email and card, **Pay $179.98**; the confirmation page shows "Thank you, Ana Souza", "Your order is paid.", the order number, the total and "card ending in 4242"; the cart is emptied. The request sent carries the lines and card, never a price. |
| 2 | A double-click on pay creates one order | **Pass** | Screen test against a fake shop that replays by key like the real one: a double click gives one order, every request carries the same key, and stock drops once. |
| 3 | A declined card shows a clear message and lets the shopper try another card | **Pass** | Screen test: "Your card was declined. Nothing was charged and nothing was taken from stock. Try another card."; the card fields are cleared, the name is kept, the cart is kept; the next attempt uses a new key and is paid. |
| 4 | An insufficient-stock response shows which items and how many are available | **Pass** | Screen test: stock drops after the checkout opened; Pay gives "Running Shoes: you asked for 2, 1 available."; **Fix my cart** sets the quantity to 1 and the cart shows the new subtotal. A second test does the same for a product that sold out (removed from the cart). |

**Also proven:** the quote endpoint prices a cart from the catalog and flags every problem without writing or locking anything (unit, integration and API tests); a lost connection or a 503 keeps the same key, so pressing Pay again can't charge twice; changing the form makes a new key; server field errors appear under their fields; the browser checks the card, expiry and CVC before sending anything; free orders skip the card.

**Live check on your stack:** both containers were rebuilt. `/cart`, `/checkout` and `/orders/:id` load through the website; a quote of RS-001 ×2, TS-002 and GF-002 answers $189.98 with TS-002 flagged as out of stock; no order was created.

**Totals after code review:** 9 feature backend tests and 20 frontend tests. The complete suite totals are recorded in the review section below.

## Business view

- **What was built:** the shop's cart, checkout and confirmation screens.
  - The header's **Cart** link opens the cart. Change quantities or remove products; prices come from the shop, and sold-out or archived items get a one-click fix.
  - Checkout asks for a name, an email and a card. Free gift orders skip the card.
  - The confirmation shows the order number, the items, the total and the card's last 4 digits.
  - Every refusal says what happened and how to fix it. Pressing Pay twice, or again after a lost connection, never charges twice.
- **Why:** challenge rules CC-06 and CC-07 (purchase through a UI), and so the owner can test ECOM-013 and ECOM-014 in the portal.
- **Main goal:** a shopper can buy in a few clicks, is never charged twice, and always understands what went wrong.
- **Human testable or background:** **testable** in the portal at http://localhost:3000.
- **What to test:** see prompt #032 of the prompt history.

## Test plan

- Component specs with MSW for each criterion.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.

## Code review round 3 (2026-11-22)

- Fixed the cart allowing navigation while a visibly invalid quantity such as `0`, blank or more than 10,000 was still in the number field. The stored cart kept the previous valid quantity, so checkout could otherwise buy a quantity different from the one on screen.
- The cart is now a real form, quantity fields are required and the checkout action is its submit. Native min/max/required validation blocks navigation until the visible quantity is valid; the server quote remains authoritative afterwards.
- A component regression reproduces the old `0` case and proves that the shopper stays on `/cart` and no hidden quantity is submitted.

No other defect was found in quoting, retry-key lifetime, declined-payment recovery, stock-conflict repair or confirmation rendering.

**Review verification:** the complete suite passes all static and architecture checks, 45 tooling tests, 866 backend tests with 99.62% scoped coverage, 134 frontend tests with 95.81% line coverage, and every live smoke check. The production frontend build succeeds; both containers are healthy; the live database is on migration 0008.

## Owner's portal test (2026-11-22)

The owner bought Backpack with Collar gift ($64.99, card 4242), had a card declined for an Air Purifier (4000…0002), then paid for it with 4242. All three orders, the stock changes and the audit entries are as expected. Full record in [ECOM-015-evidence](ECOM-015-evidence/README.md). Verdict: "you can commit and go to next one". Four UX observations went to [ECOM-018](ECOM-018.md).
