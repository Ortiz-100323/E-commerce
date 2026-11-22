# ADR-0029: Admins don't shop, and they see every order on a read-only screen

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-22 |
| Journal | D-117 (third choice superseded), D-118, D-119 |

## Context

At first, an admin who bought something placed a guest order. In the owner's test, an admin could add to the cart and pay. The owner decided that admins shouldn't buy, but should have an orders screen covering every order.

## Decision

- **The server refuses an admin's checkout** with 403 `admin-cannot-buy`, before anything starts. No idempotency key is stored.
- **The screens hide** Add to cart and the cart for admins, and block `/cart` and `/checkout`. A visitor's cart comes back after logging out.
- **Admin orders:**
  - `GET /api/v1/admin/orders` lists every order, with a search over customer name, email or order number, a status filter, and 20 per page, newest first;
  - `GET /api/v1/admin/orders/{id}` shows one order;
  - both are admin-only and read-only, shown in a new **Orders** tab.
- **"Guest" or "Customer account" comes from the order's `buyer_id`.** Ordering never joins the identity tables; the order already stores the customer's name and email.
- **No refunds or status changes.**

## Alternatives discarded

- **Admin purchases as guest orders** (the first choice): it blurs the two roles.
- **Hiding the buttons without a server check:** the rule would depend on the screen.
- **Reusing the public order page:** it can't list or filter, and listing every order must be admin-only.
- **Joining the account tables to show names:** it would couple ordering to identity.

## Consequences

- The two roles are fully separate: customers can't reach the admin area, and admins can't buy.
- Changing an order's status and refunds are listed as next steps.
