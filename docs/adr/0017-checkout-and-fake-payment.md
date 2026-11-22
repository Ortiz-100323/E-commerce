# ADR-0017: Checkout prices on the server, and the fake payment sits behind a port

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-015, D-095, D-097, D-099 |

## Context

The challenge asks for a purchase with a fake payment. Nothing the browser sends can be trusted for prices, and the fake must be replaceable by a real provider without touching the use case.

## Decision

- **The cart lives in the browser** (`localStorage`, with an in-memory fallback).
- **The server prices everything:**
  - `POST /orders/quote` prices a cart and reports each line's problem, without writing or locking anything;
  - `POST /orders` re-prices the cart from locked rows. Prices sent by the client are dropped by the schema, so they can never be read.
- **Every cart problem comes back in one answer:**
  - unknown, archived or out-of-stock items give 409 `product-not-sellable`;
  - quantities above the stock give 409 `insufficient-stock`, with what's available.
  - The screen offers **Fix my cart**.
- **Payment goes through a `PaymentGateway` port.** `FakePaymentGateway` approves `4242 4242 4242 4242` and declines `4000 0000 0000 0002`.
  - Card numbers are checked (Luhn, expiry, CVC length).
  - Only the last 4 digits are stored, the CVC never is, and the card can't reach a log.
- **One transaction per checkout:** lock, check, charge, decrease stock and save the order.
  - A declined card stores the order as `PAYMENT_FAILED`, leaves the stock untouched, and answers 402.
- **Guests can buy.** A logged-in customer's order is linked to their account.

## Alternatives discarded

- **A server-side cart:** it needs a session for every visitor.
- **The browser multiplying prices itself:** the client would be computing totals.
- **A "simulate decline" switch instead of test cards:** less realistic, and it doesn't exercise a real port contract.
- **Reserving stock and paying asynchronously:** unnecessary with an in-process fake. It is the design for a real provider ([ADR-0019](0019-no-overselling-row-locks.md)).

## Consequences

- Swapping in a real provider means a new adapter for the port, plus the reservation flow.
- There are no refunds or order status changes. They are out of scope.
