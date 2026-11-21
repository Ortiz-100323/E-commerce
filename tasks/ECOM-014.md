# ECOM-014: Checkout safety: idempotency key and stock locking

| Field | Value |
|---|---|
| Type | Story (backend) |
| Phase | 4 |
| Status | **Backlog** |
| Depends on | ECOM-013 |
| Architecture | §7.2, §7.3 |

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

## Test plan

- Every test listed in §7.2 and §7.3, on real PostgreSQL, including the latch test with no `sleep`.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
