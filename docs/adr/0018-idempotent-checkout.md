# ADR-0018: Checkout is idempotent, with an `Idempotency-Key` claimed in the order's transaction

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-043, D-044, D-096, D-099, D-102, D-117 |

## Context

A double click, a lost connection or a timeout must never charge twice or create two orders. The answer to a retry must be the original outcome.

## Decision

- **The key:**
  - the checkout screen creates a UUID v4 when it opens, and sends it as `Idempotency-Key` on `POST /orders`;
  - the same key is reused for double clicks, network errors and 503s;
  - a new key is made when the cart or form changes, and after every final answer.
  - A missing or malformed key gives 400.
- **Claiming the key:**
  - `INSERT … ON CONFLICT DO NOTHING`, in the same transaction as the order, the stock change and the audit entries. They all commit or roll back together.
  - A concurrent duplicate waits on the unique index, then replays the stored outcome. No "in progress" state is needed.
- **Only lasting outcomes are stored:** 201 (paid) and 402 (declined).
  - A 409 or 422 rolls back, so the same key can be retried after the cart is fixed.
  - A replay rebuilds the answer from the stored order and adds `Idempotent-Replayed: true`.
- **The same key with a different body gives 422 `idempotency-key-reused`.** Nothing is processed, and nothing about the first order is revealed.
  - The body is compared by fingerprint: an HMAC-SHA-256 of the canonical request, including the card, under `CHECKOUT_FINGERPRINT_SECRET`.
  - The database stores neither the card nor a guessable hash of it.
- **Keys last 24 hours.** An expired key is taken over on its next use, so no clean-up job is needed.
- **A logged-in customer's keys are scoped to them,** so two customers sending the same key get two orders.

## Alternatives discarded

- **Keys issued by the server:** an extra round trip, and nothing gained over a UUID made by the client.
- **De-duplicating by cart content:** it would block a legitimate second purchase of the same items.
- **HTTP middleware that caches responses:** it sits outside the transaction, so a crash between commit and cache breaks the guarantee.
- **409 for a reused key:** the IETF draft uses 422 for a different body.
- **A fingerprint of the card's last 4 digits only:** a code review found that two cards ending in the same digits collided (D-099).

## Consequences

- Retrying is always safe for the shopper and the shop.
- A real payment provider will need a committed "in progress" record, because the payment can't happen inside a database transaction.
