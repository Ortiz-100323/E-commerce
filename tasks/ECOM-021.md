# ECOM-021: Admins don't shop, and an admin orders screen with every order

| Field | Value |
|---|---|
| Type | Story (backend and frontend) |
| Phase | After the MVP |
| Status | **Backlog**: requested by the owner after validating ECOM-019 and ECOM-020 (prompt #048); not planned for the MVP, which the owner closed as complete |
| Depends on | ECOM-019, ECOM-020 |
| Journal | D-118 |
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

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` and the browser tests are green locally and on GitHub Actions.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
