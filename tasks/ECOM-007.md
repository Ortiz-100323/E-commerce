# ECOM-007: Admin product UI: table, form, gift dialog, history

| Field | Value |
|---|---|
| Type | Story (frontend) |
| Phase | 2 |
| Status | **Done** |
| Depends on | ECOM-006 |
| Architecture | §5, CC-02, CC-07 |
| Journal | D-072, D-078 to D-086, D-089 |
| Evidence | [ECOM-007-evidence](ECOM-007-evidence/README.md) |

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

## Plan (D-078)

1. **Table** (`/admin/products`)
   - The search box (name, SKU, description), the status filter (Active, Archived, All) and the page number live in the address, so a refresh or a shared link keeps them.
   - Columns: SKU, name, category, price (with currency), stock (with an "Out of stock" badge at 0), status and a "Gift" badge.
   - Row actions: **Edit**, **History**, and **Archive** or **Restore**. Archiving asks for confirmation first.
   - Previous and Next buttons, with "Page 1 of 3 · 42 products". An empty result says so.
   - After every change, the table and the product are reloaded from the server.
2. **Form** (`/new` and `/:id/edit`)
   - Fields: SKU (create only; shown read-only when editing), name, description, category (with suggestions from `/categories`), price, stock, weight and "Free gift".
   - The browser checks only the obvious things: required fields, a price with at most 2 decimals, a whole stock, a weight with at most 3 decimals. The server checks everything else.
   - The edit form sends the `version` it loaded.
3. **Gift dialog:** when saving with price 0 and "Free gift" unticked, a dialog asks **"Price is 0. Mark this product as a gift?"**
   - **"Yes, mark as gift"** saves with `gift: true`.
   - **"No, go back"** sends nothing and returns to the price field.
4. **Errors**
   - 422 errors land on their fields, and the rest are listed at the top.
   - 409 `duplicate-sku` lands on the SKU field.
   - 409 `version-conflict` shows a banner: "This product was changed by someone else since you opened it. Reload to see the latest version; your unsaved changes will be lost." It has a **Reload** button.
   - These handled problems don't also pop up as notifications. Mutations declare them in `meta.handledProblems`.
5. **History** (`/:id/history`): the timeline, oldest first. Each entry shows the time, the person, what happened (Created, Changed, Archived, Restored, Stock decreased) and every field's value before and after.
6. **Success messages:** "Product created", "Changes saved", "Product archived" and "Product restored". Notifications gain a `tone` (success or error).

7. **The edit form keeps the version it was opened with** (found during the work). Only **Reload** rebuilds it with the newest version, so a background refresh can never make a save overwrite someone else's change.

## Verification (2026-11-21)

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | The admin can create, edit, archive and restore a product, and the table reflects each change | **Pass** | The tests run against an in-memory fake of the API that keeps versions, duplicate SKUs, the gift rule and the history:<br>• **Create:** the form → back to the table, where the new row appears, with "Product created". The request carried the reviewer "Łukasz" encoded, and the exact body.<br>• **Edit:** the new name and price appear in the row, and version 1 was sent (the product is now at 2).<br>• **Archive** (after confirming) and **Restore:** the row's status changes each time. |
| 2 | Saving a price of 0 asks for gift confirmation, and refusing keeps the form open | **Pass** | Price 0 without the gift box opens "Price is 0. Mark this product as a gift?".<br>• "No, go back": the dialog closes, the form keeps its values, the cursor is in the price field and **nothing was sent**.<br>• "Yes": the product is saved with `gift: true` and shows the Gift badge.<br>• With the box already ticked there is no dialog. Unticking it on a free product asks again. |
| 3 | Server validation errors appear on the matching fields | **Pass** | A name with HTML comes back as a 422. The Name field is marked, shows "Remove < and > from the name.", gets the cursor, and the other values stay. A duplicate SKU appears under the SKU field. Neither causes a pop-up. |
| 4 | A 409 version conflict shows a reload message | **Pass** | Someone else edits the product while it is open. Save shows "This product was changed by someone else since you opened it… your unsaved changes will be lost", with no pop-up. **Reload** brings the newest name and values and clears the message. A second test refreshes the page in the background before saving: the save still sends version 1 and gets the conflict, and the other person's change survives. |
| 5 | The history page lists every change, oldest first | **Pass** | After create → someone else's edit → archive, the page lists Created (by Maria, with all the values), Changed (by Someone else: "Price 89.99 → 79.99", "Stock 10 → 3") and Archived ("Status ACTIVE → ARCHIVED"), in that order, each with its time. |

### Code review round 1 (2026-11-21)

**Fixed:** a hand-edited admin URL such as `?page=999` returned a valid empty page even when products existed. After a non-placeholder response, the table now replaces the URL with the last real page and loads it. A regression test starts beyond a two-page result and proves page 2 and its final product appear.

## Failure cases and retries (D-072)

| Situation | What the admin sees | Result |
|---|---|---|
| 422 from the server | Each message under its field; the others at the top; the values typed are kept | Pass |
| 409 `duplicate-sku` on create | "SKU RS-001 is already taken." under the SKU field; no pop-up | Pass |
| 409 `version-conflict` on save | The reload banner; Reload loads the newest version | Pass |
| A refresh in the background while editing | The save still sends the version that was opened; conflict instead of overwrite | Pass |
| Product not found (bad link) on edit or history | "Product not found", with a link back to the table | Pass |
| 5xx on save | A notification with the reference; values kept; Save works again; one request | Pass |
| The table fails to load | A notification with the reference and "We couldn't load the products." with **Try again**, which works | Pass |
| Price 0, gift unticked | The gift dialog; "No" sends nothing | Pass |
| Price 0, gift ticked | No dialog; saved as a gift | Pass |
| Archive, then Cancel | Nothing is sent | Pass |
| **Double click** on Save or on the archive confirmation | One request | Pass |
| **Retry** after a failed save | Only when the admin clicks Save again | Pass |
| **Stock:** stock 0, or a negative, decimal or non-numeric value | "Out of stock" badge; bad values are refused before sending, with a message | Pass |

**Proof that the key test can fail:** with the first design (the form takes the newest version), the background-refresh test turns red.

**Also in this ticket:**
- Search, status filter and paging, kept in the address.
- "No products match." when a search finds nothing.
- Category suggestions taken from `/categories`.
- Success notifications in green.
- Shared `ConfirmDialog` and `TextAreaField` components.
- A fake product API for the tests (`testing/frontend/support/fakeCatalog.ts`).
- The package versions from ECOM-006 were corrected to ones at least two weeks old (D-079).

**Totals:** 28 new frontend tests (including the regression test for DEF-01 and the gift option), plus backend tests for the gift rule (domain, API, constraint and migration 0004). Every frontend test also checks the whole page for errors (D-085). The `ci` container passes:
- ruff, mypy, 5 contracts, tsc, Prettier, the raw-HTML check and the no-comments check;
- 33 tooling tests;
- 505 backend tests;
- 75 frontend tests and the smoke checks, including "the page is never served stale".

The frontend container was rebuilt.

**Coverage (D-086):** statements 95.72%, branches 89.23%, functions 96.31%, lines 95.81%. The 80% gate is enforced by `run.py frontend`.

## Owner's test (2026-11-21, prompt #017)

The owner tested the screens in the browser. The full record, with screenshots, is in [ECOM-007-evidence](ECOM-007-evidence/README.md).

- **Passed:** the duplicate SKU on its field, and the gift dialog.
- **DEF-01 (fixed, waiting for re-test):** a red "Something unexpected went wrong" after creating or editing a product, one more for each product created in the session. Cause: refreshing cached product entries that had no loader. Fix and guards: D-081.
- **Observations deferred to [ECOM-018](ECOM-018.md):** the drop-downs look off; the table is cramped on a narrow window; a duplicate SKU should show the product that already uses it.

## Owner's re-test 1 (2026-11-21, prompt #018)

- **DEF-02:** the red messages seemed to come back. The owner's browser tab was still running the old code; the server log proves the new code was never downloaded. Fixed with cache headers and a smoke check (D-084).
- **CR-01, gifts are always free (owner's decision):** done in the domain, the API, the database (migration 0004 fixed SP-003 with a history entry) and the form, where the gift option now comes first and locks the price at 0 (D-083).
- **Test hardening:** every frontend test checks the whole page for errors (D-085).
- **Re-test 2 passed** (prompt #019): after one reload, GF-04 was created as a free gift with only the green message, and SP-003 shows no Gift badge. Evidence: screenshot 05.

## Test plan

- Component specs with MSW for each criterion and each row of "Failure cases and retries". A small in-memory fake of the product API in the tests behaves like the real one: versions, duplicate SKUs, the gift rule and history entries.

## Business view

- **What was built:** the admin product screens. A product list with search, filters and pages, a form to create and edit products, the gift confirmation, archive and restore, and each product's full history.
- **Why:** challenge rules CC-02 (manage products) and CC-07 (a usable interface). Until now this was only possible in Swagger.
- **Main goal:** manage the catalogue safely from the browser. No accidental free products, no lost edits, clear messages, and the full story of every product.
- **Human testable or background:** **testable**, in the browser at http://localhost:3000/admin.
- **What to test:** see the steps in prompt #016 of the prompt history.

## Definition of done

- Acceptance criteria pass, written test-first; frontend coverage ≥ 80% (met: 95.7% of statements, D-086).
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
