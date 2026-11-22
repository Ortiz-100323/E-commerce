# ADR-0019: Stock never oversells: rows are locked in SKU order, with a timeout, one retry and a database guard

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-027, D-045, D-072, D-096 |

## Context

Two buyers may try to buy the last unit at the same moment. They must not both succeed, and buyers shouldn't get needless errors when many check out at once.

## Decision

- **Every writer that changes product rows** (checkout and the import commit) locks them with `SELECT … FOR UPDATE ORDER BY sku`.
  - A second checkout waits, re-reads the committed stock, and gets a clear 409 if nothing is left.
- **The domain decides:** `Product.decrease_stock` refuses to go below zero.
- **The database guards:** `CHECK (stock >= 0)` is the last line of defence.
- **The locking order is the same everywhere,** so deadlocks shouldn't happen. If PostgreSQL still reports one, the transaction is retried once. The application asks a `TransientErrors` port, so it never imports the database driver.
- **The lock timeout is 5 seconds** (`CHECKOUT_LOCK_TIMEOUT_MS`). A longer wait gives 503 with `Retry-After: 1`.
- **Admin edits keep optimistic locking** ([ADR-0009](0009-optimistic-locking-for-admin-edits.md)). It also catches an edit made after a checkout changed the row.

## Alternatives discarded

- **Optimistic version checks at checkout:** needless 409s for shoppers under load.
- **A conditional `UPDATE … WHERE stock >= :q`:** atomic, but it bypasses the aggregate's rules and audit events.
- **`SERIALIZABLE` isolation:** every caller would need a retry loop.
- **An in-process lock:** it breaks with more than one worker.
- **A Redis lock:** more infrastructure for no gain.

## Consequences

- **Tests prove it on real PostgreSQL:**
  - 20 parallel checkouts for the last unit give exactly 1 success;
  - a held lock is observed deterministically, with no sleeps;
  - two carts locking items in opposite order don't deadlock;
  - the CHECK constraint refuses negative stock.
- The fake payment runs inside the lock only because it is in-process. A real provider needs stock reserved with an expiry, then a payment, then a confirm or release.
