# ECOM-004: Audit trail: append-only log and product history

| Field | Value |
|---|---|
| Type | Story (backend) |
| Phase | 1 |
| Status | **Backlog** |
| Depends on | ECOM-003 |
| Architecture | §6.4, PR-13 |

## Context

Every data change must be traceable: what the value was, what it became, who changed it and when.

## Scope

- `audit_log` table, with a trigger that raises an error on any `UPDATE` or `DELETE`.
- The Unit of Work writes the aggregates' domain events to `audit_log` in the same transaction as the change.
- The `X-Actor-Name` header is required on every change request, and is stored as the actor.
- `GetProductHistory` use case and `GET /api/v1/products/{id}/history`.

## Acceptance criteria

1. Each product change writes one audit entry with before, after, actor and time.
2. When the transaction rolls back, its audit entry is gone too.
3. `UPDATE` and `DELETE` on `audit_log` fail.
4. A change request without `X-Actor-Name` returns 422.
5. The history endpoint returns the product's entries, oldest first.

## Test plan

- Integration tests for the same-transaction write, the rollback and the trigger.
- API tests for the header rule and the history endpoint.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
