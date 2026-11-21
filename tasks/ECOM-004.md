# ECOM-004: Audit trail: append-only log and product history

| Field | Value |
|---|---|
| Type | Story (backend) |
| Phase | 1 |
| Status | **Done** |
| Depends on | ECOM-003 |
| Architecture | §6.4, PR-13 |
| Journal | D-072, D-073, D-074 |

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

## Plan (D-073)

1. **Table `audit_log`** (migration 0003) with these columns:
   - `id` (bigint identity), which gives the order;
   - `occurred_at` (the event's time), `actor`, `event`, `entity`, `entity_id` and `sku`;
   - `context`, `before` and `after` (JSONB).

   An index on `(entity, entity_id, id)` serves the history query. A PL/pgSQL trigger raises an error on `UPDATE` and `DELETE`.
2. **Event to entry mapping**, in the catalog application layer (`catalog/application/audit.py`):

   | Domain event | `event` | `before` | `after` | `context` |
   |---|---|---|---|---|
   | `ProductCreated` | `product.created` | `null` | full snapshot | — |
   | `ProductChanged` | `product.changed` | changed fields' old values | changed fields' new values | — |
   | `ProductArchived` | `product.archived` | `{"status": "ACTIVE"}` | `{"status": "ARCHIVED"}` | — |
   | `ProductRestored` | `product.restored` | `{"status": "ARCHIVED"}` | `{"status": "ACTIVE"}` | — |
   | `StockDecreased` | `product.stock_decreased` | `{"stock": before}` | `{"stock": after}` | `{"quantity", "order_reference"}` |

3. **How entries are written.**
   - When an `add` or `save` succeeds, the repository takes the product's events and keeps them.
   - `commit()` turns them into rows with the actor, inserts them, and then commits, all in one transaction.
   - A product that was changed but never saved writes nothing.
   - `save` skips a product with no pending events, so a request that changes nothing creates neither a new version nor an entry.
4. **The actor is given when a unit of work is opened** for a change, because one request has one actor. A read-only unit of work needs none. Committing events without an actor raises `ActorRequired`, and nothing is stored.
5. **`Actor`** is a shared kernel value object: trimmed, 1–100 characters, no control characters.
   - The `require_actor` dependency reads `X-Actor-Name`. A missing or invalid value becomes 422 `validation-error`, with `location: "header"` and `field: "X-Actor-Name"`.
   - **Names with accents:** browsers can only send Latin-1 in headers. The frontend sends the name percent-encoded (UTF-8) and the backend decodes it; plain names arrive unchanged.
6. **`GetProductHistory`** use case and `GET /api/v1/products/{id}/history`. The response is `{product_id, entries}`, oldest first. Each entry has the event, time, actor, SKU, before, after and context.
7. **`TRUNCATE` stays possible.** The trigger blocks `UPDATE` and `DELETE`, as the ticket says. The table owner can still truncate the table, and the tests need that for cleanup. Stopping it in production needs a separate database role for the app, with only `INSERT` and `SELECT` on `audit_log`. That is noted for ECOM-016.

## Verification (2026-11-21)

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | Each product change writes one audit entry with before, after, actor and time | **Pass** | Real database:<br>• Creating a product writes `product.created`, with the full product as "after".<br>• A two-field edit writes **one** `product.changed` with only the changed fields: name and price, before and after, actor Maria, at 11:00.<br>• Archive, restore and a sale each write one entry, in order. The sale also records the quantity and the order number. |
| 2 | When the transaction rolls back, its audit entry is gone too | **Pass** | Real database:<br>• Work that is never committed, an error inside the unit of work, and an explicit rollback all leave neither the change nor its entry.<br>• It holds the other way round too: when a test trigger makes the entry fail to write, the product change is not stored either. |
| 3 | `UPDATE` and `DELETE` on `audit_log` fail | **Pass** | Real database:<br>• Four direct SQL statements are refused with "audit_log is append-only": `UPDATE` and `DELETE` on every row, and on no rows at all.<br>• The trigger works per statement, so even an edit that matches nothing is refused.<br>• The entry is unchanged afterwards. |
| 4 | A change request without `X-Actor-Name` returns 422 | **Pass** | API test on a change route built inside the test, because the product change endpoints only arrive in ECOM-005:<br>• A missing, blank or spaces-only header gives 422 `required`.<br>• A name that is too long, has control characters or is badly encoded also gives 422.<br>• Valid names, including "Łukasz", "李" and "100% sure", reach the change trimmed. |
| 5 | The history endpoint returns the product's entries, oldest first | **Pass** | API test on the real database:<br>• A product that was created and then repriced returns two entries in order, and the JSON is checked exactly.<br>• Another product's entries never appear. |

## Failure cases and retries (D-072)

| Situation | What the caller gets | Test | Result |
|---|---|---|---|
| `X-Actor-Name` missing, blank or only spaces | 422 `validation-error`, location `header`, field `X-Actor-Name`, code `required` | API | Pass |
| `X-Actor-Name` longer than 100 characters | 422, code `too_long`, `max_length: 100` | API | Pass |
| `X-Actor-Name` with control characters (`%0A`, tab, `%00`) | 422, code `control_characters_not_allowed` | API | Pass |
| `X-Actor-Name` with broken percent-encoding (`%C3`, `Jos%E9`) | 422, code `invalid_encoding` | API | Pass |
| History of a product that doesn't exist | 404 `not-found`, "Product not found." | API | Pass |
| History with an id that isn't a UUID | 422 `validation-error`, location `path`, code `not_a_uuid` | API | Pass |
| The audit entry can't be written | The change is not stored either | Integration | Pass |
| The database goes down during a change | 503 `service-unavailable` with `Retry-After: 1` | Existing mapping, tested in ECOM-001 | Pass |
| The change is refused (version conflict, duplicate SKU, already exists) | The same error as before; **no** audit entry; the rest of the work is kept | Integration | Pass |
| Someone runs `UPDATE` or `DELETE` on `audit_log` | The database refuses it | Integration | Pass |
| Committing changes without an actor | `ActorRequired`; nothing is stored | Integration | Pass |
| A read-only unit of work (no actor) | Works normally | Integration | Pass |
| **Retry:** a change that changes nothing (same name, same price, restoring an active product) | No new version, no new `updated_at`, no entry | Integration | Pass |
| **Retry:** archiving twice | One entry, one version | Integration | Pass |
| **Retry:** the same product saved twice in one unit of work | Each change logged once; a save with nothing new doesn't move the version | Integration | Pass |
| **Retry:** a refused save, retried after reloading | Only the saves that succeeded are logged | Integration | Pass |
| **Stock:** two buyers race for the last unit | One sale, one `product.stock_decreased` entry, stock 0 | Integration | Pass |

**Also in this ticket:**
- `Product.has_pending_events`.
- `catalog.application` joins the 95% coverage gate (100% today).
- The catalog layers contract now includes `catalog.api`.
- The database fixtures moved to `testing/backend/conftest.py`, so API tests can use the real database.
- A migration test for `0003`. The live stack migrated to `0003` on restart.

**Totals:** 67 new tests. The `ci` container passes:
- lint, mypy over 69 files, 5 contracts and the no-comments check;
- 20 tooling tests;
- 368 backend tests, with 100% coverage of the domain and catalog application code;
- 6 frontend tests and the smoke checks.

## Test plan

- Integration tests for the same-transaction write, the rollback and the trigger.
- API tests for the header rule and the history endpoint. The product change endpoints only arrive in ECOM-005, so the header rule is tested here on a small route built inside the test; ECOM-005's contract test then checks it on every real change endpoint.
- Every row of "Failure cases and retries" has a test.

## Business view

- **What was built:** the audit trail. Every product change is written down: what it was, what it became, who did it and when. Nobody can edit or delete those records afterwards.
- **Why:** challenge rule PR-13. Every change must be traceable, so a wrong price or stock level can always be explained.
- **Main goal:** a change and its record are saved together or not at all, so the history can be trusted.
- **Human testable or background:** mostly background. The history endpoint is in Swagger, but there are no products to look at until ECOM-005.
- **What to test:** in Swagger (http://localhost:8001/docs), open `GET /api/v1/products/{product_id}/history` and try any id. You should get a clear "Product not found." From ECOM-005 you'll edit a product and see its history there.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
