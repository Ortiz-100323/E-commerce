# ADR-0016: An append-only audit trail, written in the same transaction as the change

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-039, D-041, D-042, D-073 |

## Context

The owner wants to trace every imported value back: what it was, and how it became what it is. The audit needs the reason for a change (for example "confirmed as gift"), not only the new values.

## Decision

- **Aggregates record domain events** such as `ProductChanged`, `StockDecreased`, `ImportRowCorrected` and `ImportRowConfirmed`. Each carries the values before and after, the context (batch, CSV line, raw line, file SHA-256) and the actor.
- **The Unit of Work writes the events to `audit_log` in the same transaction as the change.** An entry can't be lost, and it can't describe a change that was rolled back.
- **The log can't be changed.** A database trigger refuses `UPDATE` and `DELETE` on `audit_log`.
- **It covers every product change:**
  - import row decisions;
  - create, edit, archive and restore, from the admin or an import;
  - stock decreases from orders;
  - logins and failed logins.
- **The actor:**
  - for an admin change, the logged-in admin's name;
  - for a purchase, "Shop checkout", which keeps customer data out of a log that can never be edited.
- **Opening a change without an actor is a programming error,** and it rolls everything back.
- **Nothing is purged.** Batches, raw lines and audit entries are kept forever until the business sets a retention period (CQ-09).
- **A product's History screen shows its timeline:** the raw CSV line, the corrections, the creation, then later edits.

## Alternatives discarded

- **Generic database triggers that capture row diffs:** they lose the reason ("confirmed as gift" looks like a price edit), can't know the actor, and move logic into SQL.
- **Event sourcing the product:** a full history, but far heavier than needed.
- **Application log lines:** not queryable, not transactional, easy to lose.
- **Use cases writing audit rows themselves:** easy to forget one.

## Consequences

- A change with no real effect writes no version and no entry, so the history shows real changes only.
- The database owner can still `TRUNCATE` the table, because the tests clean up with it. Production needs a separate database role with only `INSERT` and `SELECT` on `audit_log` (listed in the README's next steps).
