# ECOM-007: Admin product UI: table, form, gift dialog, history

| Field | Value |
|---|---|
| Type | Story (frontend) |
| Phase | 2 |
| Status | **Backlog** |
| Depends on | ECOM-006 |
| Architecture | §5, CC-02, CC-07 |

## Context

The admin manages products through the UI, as the challenge requires.

## Scope

- `/admin/products`: table with search, create, edit, archive and restore.
- `/admin/products/new` and `/admin/products/:id/edit`: the product form; a price of 0 opens the dialog "Price is 0. Mark this product as a gift?".
- `/admin/products/:id/history`: the audit timeline with actor and time.
- A version conflict tells the admin to reload.

## Acceptance criteria

1. The admin can create, edit, archive and restore a product, and the table reflects each change.
2. Saving a price of 0 asks for gift confirmation, and refusing keeps the form open.
3. Server validation errors appear on the matching fields.
4. A 409 version conflict shows a reload message.
5. The history page lists every change, oldest first.

## Test plan

- Component specs with MSW for each criterion.

## Definition of done

- Acceptance criteria pass, written test-first; frontend coverage ≥ 80%.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
