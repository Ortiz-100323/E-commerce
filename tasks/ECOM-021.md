# ECOM-021: Admins don't shop, and an admin orders screen with every order

| Field | Value |
|---|---|
| Type | Story (backend and frontend) |
| Phase | After the MVP |
| Status | **Done**: accepted by the owner (prompt #051) |
| Evidence | [Playwright on desktop and phone](ECOM-021-evidence/README.md) |
| Depends on | ECOM-019, ECOM-020 |
| Journal | D-118, D-119 |
| Source | The owner's test of ECOM-020 in the portal: an admin could buy ([evidence](ECOM-020-evidence/README.md)) |

## Context

While testing ECOM-019 and ECOM-020, the owner noticed that an admin can buy in the shop. Today an admin's purchase is a guest order (D-117, the third recommendation).

The owner's direction (prompt #048):

> I think admin should not have add to the cart, but should have an orders screen same as the user, but with full perspective from what was order.

The owner also closed the MVP here ("We already created too many new functionalities … we have a full MVP cycle"), so this ticket waits until after ECOM-017.

## Scope (to be planned in detail before building)

- **Admins don't shop:**
  - an admin sees no **Add to cart** on the cards and product pages, and no cart or checkout;
  - the server refuses a checkout sent with an admin's session (403 `buyer-or-guest-required`, or similar), so the rule doesn't depend on the screen;
  - guests and customers are unchanged.
- **An admin "Orders" screen** in the admin area, like a customer's My orders but covering **every order**:
  - the customer (name, email), whether it was a guest or an account, the items, the total, the status and the payment reference;
  - newest first, with pages, and filters by status and by customer email;
  - a detail view per order;
  - `GET /api/v1/admin/orders` (admins only, 401 or 403 otherwise).

## Acceptance criteria (draft)

1. An admin sees no Add to cart, cart or checkout; a checkout request with an admin's session is refused and creates nothing.
2. Guests and customers buy exactly as before.
3. An admin's Orders screen lists every order, newest first, with the customer, items, total and status, and filters by status and email.
4. A customer or a visitor can't open the admin Orders screen or its API (403 / 401).
5. Tests first, including the access matrix for the new endpoint and a browser test on desktop and phone.

## Detailed plan (D-119, proposed in prompt #049, waiting for the owner's approval)

Branch: `feature/ECOM-021-admin-orders`, started from ECOM-019 and ECOM-020 (`35fccd2`).

### Part 1: admins don't shop

- **Server:**
  - `POST /api/v1/orders` with an admin's session answers **403 `admin-cannot-buy`**: "Administrator accounts can't place orders. Log out, or use a customer account."
  - Nothing is charged, no stock is taken, and no idempotency key is stored. The check runs before the checkout starts.
  - Guests and customers are unchanged. The cart quote stays public, because it only reads prices.
- **Screens, for an admin:**
  - product cards show the price and stock, **without Add to cart**;
  - the product page says "You're logged in as an administrator, so you can't buy here.";
  - the header's **Cart** button is hidden;
  - `/cart` and `/checkout` show "Administrator accounts can't place orders", with links to the Orders screen and to log out.
- **The cart itself:** a visitor's cart, saved in the browser, is kept but hidden while an admin is logged in, and comes back after log-out (proposed; see the decisions below).
- **D-117's third choice** ("an admin's purchase is a guest order") is superseded: an admin can no longer place one.

### Part 2: an admin Orders screen with every order

- **API (admins only; 401 or 403 otherwise):**
  - `GET /api/v1/admin/orders?q=&status=&page=` lists every order, newest first, 20 per page.
    - `q` matches the customer's name or email (contains, any letter case), or the start of the order number.
    - `status` is `PAID`, `PAYMENT_FAILED` or `PENDING`.
    - Each order has its number, date, customer name and email, **Guest** or **Customer account**, items, total, status, payment reference, the card's last 4 digits and the decline reason.
  - `GET /api/v1/admin/orders/{id}` returns one order with all of that. An unknown id gives 404.
  - Ordering reads only its own `orders` table: "Customer account" comes from `buyer_id`, so it never needs the identity context.
  - Migration 0012 adds an index on `orders.created_at` for the newest-first list.
- **Screens:**
  - a new **Orders** tab in the admin area, beside Products, Import CSV and Admins;
  - a table: date, order number, customer (name and email), Guest or Account, items, total and status;
  - a search box, a status filter and pages;
  - an empty state for "no orders match";
  - each row opens `/admin/orders/:id`, a detail view with the lines, the totals, the payment and the customer;
  - on a phone, the table becomes one card per order.
- **Read-only:** no refunds and no status changes, to keep the scope small.

### Tests first

- **API on PostgreSQL:**
  - an admin's checkout gets 403 and creates nothing (no order, no key, the stock unchanged), while a guest's and a customer's still work;
  - the admin orders list (every order, guests and customers alike, newest first, the filters, pages) and the detail (404 for an unknown id).
- **The access matrix** gains the two admin-orders endpoints (401 for a visitor, 403 for a customer); a contract test checks they document it.
- **Screens:**
  - for an admin: no Add to cart on cards or the product page, no Cart in the header, the blocked cart and checkout;
  - the Orders tab: list, search, status filter, pages, empty state and detail;
  - for customers and visitors nothing changes.
- **Browser, desktop and phone:**
  - a customer buys, then the admin finds that order in Orders and opens it;
  - an admin sees no Add to cart, and `/checkout` is blocked.

### Failure cases and retries (planned)

| Situation | Expected |
|---|---|
| An admin's checkout sent straight to the API | 403 `admin-cannot-buy`; nothing charged, no stock taken, no order |
| An admin with items in the browser's cart | The cart is hidden and kept; it comes back after log-out |
| The admin's session ends on the Orders screen | Back to the login with "Your session ended" (as in ECOM-019) |
| A search that matches nothing | "No orders match", with **Clear filters** |
| An unknown or malformed order id | 404, or 422 for a malformed id, shown as "Order not found" |
| A customer or a visitor on the admin orders API | 403 or 401 |
| **Retry:** an admin pressing Pay many times | Every attempt is refused; nothing is created |

### Owner decisions needed

1. **An admin with items already in the cart** (added before logging in): keep the cart hidden and bring it back after log-out (recommended), or empty it when an admin logs in.
2. **What an admin sees on product cards:** the price and stock with no button (recommended), or a greyed-out "Admins can't buy" button.
3. **Admin orders are read-only for now** (recommended), or should an admin also be able to mark an order (for example refunded)? That would need a status change and its audit.

### Estimated size

About 30 backend tests, 15 frontend tests and 2 browser tests (run on 2 devices). No new packages.

## As built and verified (2026-11-22, prompt #050, D-119)

The owner accepted the three recommendations:
- a visitor's cart stays hidden while an admin is logged in;
- cards show no button for admins;
- orders are read-only.

Evidence: [ECOM-021-evidence](ECOM-021-evidence/README.md).

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | An admin sees no Add to cart, cart or checkout; an admin's checkout is refused and creates nothing | **Pass** | API test on PostgreSQL: three attempts give 403 `admin-cannot-buy`, with no order, no idempotency key and the stock unchanged. Screen tests: no button on cards, a note on the product page, no Cart, `/cart` and `/checkout` blocked with the cart kept. Playwright on both devices |
| 2 | Guests and customers buy exactly as before | **Pass** | API tests; screen tests (a customer still has Add to cart and the Cart); every earlier purchase test still passes |
| 3 | The Orders screen lists every order, newest first, with customer, items, total and status; search and status filter | **Pass** | API tests: guests and customers together, newest first; search by name, email and order number (and `%_` matches nothing); the status filter; 23 orders over 2 pages; the detail and a 404. Screen tests: list, badges, search, filter, empty state, **Clear filters**, pages, detail, "Order not found". Playwright |
| 4 | Customers and visitors can't open it (403 / 401) | **Pass** | API tests; the access matrix now covers 17 admin endpoints; a screen test shows "This area is for administrators" to a customer |
| 5 | Tests first, the access matrix, and a browser test on desktop and phone | **Pass** | As above |

### Failure cases and retries (results)

| Situation | Result |
|---|---|
| An admin's checkout sent straight to the API | Pass: 403 `admin-cannot-buy`; nothing charged, no stock taken, no order or key stored |
| An admin with items in the browser's cart | Pass: the cart is hidden and kept; it comes back after log-out |
| The admin's session ends on the Orders screen | Pass: the ECOM-019 handling, back to the login with "Your session ended" |
| A search that matches nothing | Pass: "No orders match.", with **Clear filters** |
| An unknown or malformed order id | Pass: 404 (or 422), shown as "Order not found" |
| A customer or a visitor on the admin orders API | Pass: 403 or 401 |
| **Retry:** an admin pressing Pay many times | Pass: every attempt is refused; nothing is created |

**Totals:**
- 23 new backend tests (including the access-matrix cases for the 2 new endpoints), 12 new frontend tests and 1 longer browser test (run on 2 devices).
- `run.py all` passes in the `ci` container: static checks, 11 architecture contracts, 60 tooling tests, 1,099 backend tests (99% coverage), 204 frontend tests and 14 smoke checks.
- 44 browser tests pass (5 skipped by design).
- `run.py containers` and `run.py images` pass.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` and the browser tests are green locally and on GitHub Actions.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
