# ADR-0009: Optimistic locking for admin edits

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-014, D-071, D-075, D-078, D-080 |

## Context

Two admins can edit the same product at the same time. A checkout can also change a product's stock while an admin has the edit form open.

## Decision

- **Every product has a `version`.**
  - `PUT` must send the version it read.
  - The update runs as one statement: `UPDATE … WHERE id = :id AND version = :loaded RETURNING version`.
  - A mismatch returns 409 `version-conflict` with `current_version`.
- **A retried `PUT` that would change nothing returns 200** with the current product. That is what a retry after a timeout looks like, and no one's change is lost.
- **The edit form keeps the version it was opened with.** A background refresh never changes it; only **Reload** does. A test caught the first design silently overwriting another admin's change (D-080).
- **Checkout doesn't use versions.** It locks rows instead ([ADR-0019](0019-no-overselling-row-locks.md)).

## Alternatives discarded

- **Last write wins:** concurrent admin edits are silently lost.
- **Row locks for admin edits:** a form can stay open for minutes; holding a database lock that long blocks the shop.

## Consequences

- An admin who loses the race sees a reload banner instead of overwriting.
- Every change returns the product with its new version, so the screen never needs a second request.
