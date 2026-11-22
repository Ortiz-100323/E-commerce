# ECOM-014: Checkout safety: idempotency key and stock locking

| Field | Value |
|---|---|
| Type | Story (backend) |
| Phase | 4 |
| Status | **Done**: accepted by the owner after the portal test of the purchase (prompt #034) |
| Depends on | ECOM-013 |
| Architecture | §7.2, §7.3 |
| Journal | D-072, D-095, D-096, D-099 |

## Context

A double-click must never charge twice, and two shoppers must never buy the last unit.

## Scope

- The `idempotency_keys` table, the request fingerprint and `IdempotentCheckout` wrapping `Checkout`.
- `SELECT … FOR UPDATE` in SKU order, `lock_timeout` of 5 s, and one retry on deadlock.

## Acceptance criteria

1. The same key with the same body gives one order and an identical replay with `Idempotent-Replayed: true`.
2. The same key with a different body gives 422 `idempotency-key-reused`, and nothing changes.
3. A missing or malformed key gives 400.
4. 10 parallel requests with one key create exactly one order.
5. 20 parallel checkouts for the last unit give exactly one 201 and nineteen 409s, and stock ends at 0.
6. Carts {A, B} and {B, A} in parallel both succeed without a deadlock.

## Plan as built (D-096)

Built together with ECOM-013 at the owner's request (prompt #030).

1. **The key:** `POST /orders` reads the `Idempotency-Key` header itself, so a missing or non-UUID key gets **400** (`idempotency-key-missing`, `idempotency-key-invalid`) before anything else, instead of FastAPI's default 422.
2. **`Checkout` wraps the order steps in the key's transaction:**
   1. validate the customer, the lines and the card, and compute the fingerprint;
   2. open the unit of work and claim the key;
   3. if the key exists with the same fingerprint, replay the stored order; with a different fingerprint, 422 `idempotency-key-reused`;
   4. otherwise place the order and record its id and HTTP status against the key;
   5. commit the key, the order, the stock change and the audit entries together.

   A refused checkout (409 or 422) rolls back, so its key stays free.
3. **The fingerprint after code review (D-099)** is a versioned HMAC-SHA-256 of the entire canonical request, including all payment fields. The HMAC key comes from the required `CHECKOUT_FINGERPRINT_SECRET` setting, so neither the stored fingerprint nor a database leak permits offline guessing of a card or CVC. Records made before this review remain replayable until their normal 24-hour expiry.
4. **`idempotency_keys` (migration 0007):** key, endpoint, fingerprint, order id, response status, created and expires times.
   - The claim is `INSERT … ON CONFLICT DO NOTHING`. A concurrent request with the same key waits on the primary key until the first one commits, then reads its outcome and replays it.
   - An expired key (24 hours, the `CHECKOUT_IDEMPOTENCY_KEY_HOURS` setting) is taken over with a conditional `UPDATE`, so it starts a new checkout.
5. **A replay** loads the stored order and builds the same answer: 201 with the order, or 402 with the failed order, plus `Idempotent-Replayed: true`.
6. **Locks:**
   - every checkout transaction starts with `SET LOCAL lock_timeout = 5000` (the `CHECKOUT_LOCK_TIMEOUT_MS` setting), so a longer wait gets **503** with `Retry-After: 1`;
   - products are locked with the catalog's `lock_by_skus`: SKU advisory locks, then `SELECT … FOR UPDATE`, in SKU order;
   - a deadlock (`40P01`) is retried once. The application only asks a `TransientErrors` port, and the infrastructure answers by recognising PostgreSQL's deadlock error.

## Failure cases and retries (D-072)

| Situation | What the caller gets | Result |
|---|---|---|
| No `Idempotency-Key`, or an empty one | 400 `idempotency-key-missing`; nothing processed | Pass |
| A key that is not a UUID | 400 `idempotency-key-invalid`; nothing processed | Pass |
| **Retry:** the same key and the same request | The same status and body, with `Idempotent-Replayed: true`; one order, one stock decrease, one audit entry, one charge | Pass |
| The same key with a different request | 422 `idempotency-key-reused`; nothing processed, and the first order is not revealed | Pass |
| 10 parallel requests with one key | Exactly one order; the other 9 wait and replay it | Pass |
| **Retry** after a refused checkout (409 or 422) | The key is still free; the corrected cart goes through with it | Pass |
| **Retry** after a declined card | The 402 is replayed; a new card means a new key | Pass |
| A key older than 24 hours | Treated as new: a new checkout | Pass |
| A lock held longer than 5 s | 503 `service-unavailable` with `Retry-After: 1`; nothing written by the waiting request | Pass |
| A deadlock | Retried once, then 503 | Pass (unit tests; with SKU-ordered locks it should not happen) |
| **Stock:** 20 parallel checkouts for the last unit | Exactly one 201; nineteen 409 `product-not-sellable` (`out_of_stock`); stock ends at 0 | Pass |
| **Stock:** 20 parallel checkouts of 2 units with 3 in stock | Exactly one 201; nineteen 409 `insufficient-stock` (requested 2, available 1); stock ends at 1 | Pass |
| An admin edit opened before a checkout | 409 `version-conflict` when saved: the checkout changed the product's version | Pass |
| A direct `UPDATE` to negative stock | Refused by `ck_products_stock_not_negative` | Pass |

## Verification (2026-11-22)

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | The same key with the same body gives one order and an identical replay with `Idempotent-Replayed: true` | **Pass** | API test on PostgreSQL: the second answer has the same status, body and `Location`, with the header; one order, stock decreased once, one `product.stock_decreased` entry. A declined (402) checkout is replayed the same way. |
| 2 | The same key with a different body gives 422 `idempotency-key-reused`, and nothing changes | **Pass** | API test: 422, the first order's id is not in the answer, still one order and stock 8. |
| 3 | A missing or malformed key gives 400 | **Pass** | API tests: no header, an empty header and `not-a-uuid` give 400 with the right problem type; nothing is stored; the contract test checks the same for the endpoint. |
| 4 | 10 parallel requests with one key create exactly one order | **Pass** | API test: 10 concurrent requests on separate connections, all 201 with one order id, 9 of them replays, stock decreased once. |
| 5 | 20 parallel checkouts for the last unit give exactly one 201 and nineteen 409s, and stock ends at 0 | **Pass** | API test: one 201 and nineteen 409 `product-not-sellable` (`out_of_stock`), stock 0, one stock audit entry. A second race (2 units each, 3 in stock) gives nineteen `insufficient-stock`. |
| 6 | Carts {A, B} and {B, A} in parallel both succeed without a deadlock | **Pass** | API test: 10 concurrent carts, half in each order, all 201; both products end at 0. |

**Also proven, without any `sleep` as a timing guess:**
- **The latch test.** A payment gateway double holds the first checkout inside its lock. The test waits until PostgreSQL reports a second backend waiting on a lock, checks that the second checkout hasn't finished, then releases the first. Result: 201, then 409, and one payment.
- **The lock timeout.** The same setup with a 200 ms limit gives the waiting checkout 503 with `Retry-After: 1`.
- **Key expiry.** A key older than 24 hours starts a new order.

## Business view

- **What was built:** the safety net under the checkout.
  - A double click, a refresh or a lost connection can never charge twice or create two orders. The shop recognises the same attempt and gives back the first answer.
  - Two shoppers can never buy the last unit: the second one is told it's out of stock.
- **Why:** a shop that charges twice or sells stock it doesn't have loses money and trust (challenge rule CC-13, "enterprise-grade").
- **Main goal:** every purchase happens exactly once, and stock is never oversold, even under heavy traffic.
- **Human testable or background:** mostly background. The retry behaviour can be seen in **Swagger** by sending the same request twice with the same key; the races are proven by automated tests.
- **What to test:** see prompt #030 of the prompt history.

## Test plan

- Every test listed in §7.2 and §7.3, on real PostgreSQL, including the latch test with no `sleep`.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.

## Code review round 3 (2026-11-22)

- Fixed a reused key with a different card being accepted when both cards had the same last four digits. That violated the ticket's "same key, different body" rule and replayed the first order instead of returning 422.
- New records use the full canonical checkout under a secret-keyed, versioned HMAC. The raw card and CVC still never enter the database or logs. The fingerprint column grows from 64 to 67 characters in migration 0008 for the `v2:` marker.
- The application still recognises an old last-four-only fingerprint for a record created before deployment, preserving safe retries during its remaining 24-hour lifetime. New records reject the collision, proven through the real API.

The locking order, key claim race, expiry, 402 replay, lock timeout and deadlock retry were rechecked with no further defect found.

**Review verification:** the complete suite passes all static and architecture checks, 45 tooling tests, 866 backend tests with 99.62% scoped coverage, 134 frontend tests with 95.81% line coverage, and every live smoke check.
