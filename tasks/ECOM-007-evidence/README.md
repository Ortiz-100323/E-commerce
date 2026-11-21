# ECOM-007: Test evidence

| Field | Value |
|---|---|
| Ticket | [ECOM-007](../ECOM-007.md): Admin product UI |
| Test type | Manual acceptance test (owner), in the browser |
| Tester | Project owner |
| Date | 2026-11-21 |
| Environment | Local compose stack, frontend at http://localhost:3000/admin, build of `feature/ECOM-007-admin-product-ui` before the fixes below |
| Result | **Passed** after re-test 2: 2 defects fixed and verified by the owner, 1 change request done, 3 observations deferred to [ECOM-018](../ECOM-018.md) |

## Test runs

| # | Step | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| 1 | Create `TS-002` Trail Shoes (stock 0) from **New product** | Back on the list, the new row with "Out of stock", and a green "Product created" | The row and "Product created" appear, **plus** a red "Something unexpected went wrong. Please try again." | **Failed**: DEF-01 | [01](01-table-after-create-two-messages.png) |
| 2 | Create a product with the taken SKU `rs-001` | "SKU RS-001 is already taken." under the SKU field, form kept | As expected | Passed (OBS-03 noted) | [02](02-duplicate-sku-on-field.png) |
| 3 | Create `GF-002` Collar gift with price 0 and "Free gift" unticked | The dialog "Price is 0. Mark this product as a gift?", with "No, go back" and "Yes, mark as gift" | The dialog appears as expected. After confirming, **two** red "Something unexpected…" messages | Dialog passed; **failed** after saving: DEF-01 | [03](03-gift-confirmation-dialog.png) |
| 4 | Edit a product and save | Back on the list with the new values and "Changes saved" | Saved, **plus** a red "Something unexpected…" message | **Failed**: DEF-01 | (owner's report) |

## Defects

### DEF-01: "Something unexpected went wrong" after creating or editing a product

- **Severity:** Medium. The data was saved correctly, but the admin is told something failed.
- **Symptom:**
  - One red message after the first create.
  - One more for every product created earlier in the same session, so two after the gift.
  - The same on edits.
- **Cause:**
  - After a save, the app stored the server's answer in its cache, under a product-detail key that had never been loaded by a screen.
  - Next, it refreshed *every* cached product query, those stored entries included. The library cannot refresh an entry that was never loaded by a screen, because it has no instruction for loading it.
  - Each one failed with "Missing queryFn". That's an internal error, which the app showed as "Something unexpected went wrong".
- **Why the tests missed it:** they checked that "Product created" appeared, but not that no error appeared next to it.
- **Fix:**
  - After a save, the app now refreshes only the product lists, that product's history and the categories. The saved product is already up to date from the server's answer.
  - Unexpected errors are now also logged to the browser console, to make the next diagnosis faster.
- **Guards added:**
  - A regression test replays this run (create, create a gift, edit) and requires success messages only.
  - Every frontend test now fails if the app reports an unexpected error.
  - With the old code, 7 tests fail on exactly this error; with the fix, all 72 pass.
- **Journal:** D-081.
- **Status:** Fixed. **Verified by the owner in re-test 2.**

## Observations (not defects; deferred to ECOM-018, UI polish)

- **OBS-01, the drop-downs look off** (owner). The Status select and the Category suggestions use the browser's default look, and the Category field turns light blue (browser autofill). Accepted for now; to be improved in the UI-focused work.
- **OBS-02, the table is cramped on a narrow window** (seen in screenshot 01). SKUs wrap ("RS-" / "001"), the Archive button is cut off at the right edge, and the notifications cover the table.
- **OBS-03, a duplicate SKU should show the existing product** (owner). The message should link to the product that already uses the SKU, so the admin can see what is in its place.

## Re-test 1 (2026-11-21, prompt #018)

| # | Step | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| 5 | Create `SP-02` Testing shoes after the fix was deployed | Only "Product created" | Two red "Something unexpected…" messages and "Product created" | **Failed**: not a code defect, see DEF-02 | [04](04-retest-errors-from-stale-tab.png) |
| 6 | Create `SP-003` Normal shoes, $55, with the Gift box ticked | Not specified (paid gifts were allowed) | Saved as a paid gift | **Change request**: CR-01 | owner's report |

### DEF-02: the browser tab was still running the old code

- **Severity:** High for testing. Any fix looks "not fixed" until the page is reloaded.
- **Evidence:** the frontend server's log. The site was rebuilt with the fix at 18:53 UTC.
  - The owner's two creates came at 19:09:53 and 19:11:13 UTC, from the browser (`Mozilla/5.0 …`).
  - The browser **never downloaded the new code**: the first request for `/assets/index-CfDpcUSZ.js` after the rebuild is our own check, at 19:12:04 (`curl`).
  - The other `GET /` lines every 5 seconds are Docker's health check (`Wget`).
- **Cause:**
  - A single-page app loads its code once per tab. The open tab kept running the old code (with DEF-01) after the server was updated.
  - The server also sent no caching instructions (`Cache-Control`). A browser may then reuse an old copy of the page for a while, even after a refresh.
- **Fix:**
  - nginx now sends `Cache-Control: no-cache` for the page and every app address, so a refresh always checks for new code.
  - The code files (whose names change with every build) are sent with `public, max-age=31536000, immutable`.
  - A new smoke check, "the page is never served stale", verifies both on every CI run.
  - A banner saying "a new version is available — reload" is added to ECOM-018.
- **Journal:** D-084.
- **Status:** Fixed. **Verified by the owner in re-test 2.**

### CR-01: gifts must always be free (owner's decision)

- **Before:** a gift was a tag that a paid product could also carry (D-068, accepted in #010).
- **Now:** a gift always has price 0, and price 0 always means a gift (D-083).
  - **Form:** "Free gift" is the first option. Ticking it sets the price to 0 and locks the field ("Gifts are always free."); unticking brings the previous price back.
  - **API and domain:** a paid gift is refused with 422 `gift_must_be_free` on the price field.
  - **Database:** the constraint `ck_products_gift_if_and_only_if_free` replaces `ck_products_zero_price_requires_gift`.
  - **Existing data:** migration 0004 removed the Gift tag from SP-003 "Normal shoes" (kept at $55, now version 2). It also wrote a history entry: "Changed by Data migration, tags GIFT → (none)", with the reason. Verified on the live database.
- **Status:** Done. **Verified by the owner in re-test 2** (SP-003 shows no Gift badge; GF-04 created as a free gift).

## Test hardening after this run (D-085)

At the owner's request, every frontend test now checks the **whole page** when it finishes. It fails if:
- the page shows "Something unexpected went wrong";
- any red notification appeared that the test didn't declare in advance (`expectErrorNotifications()`);
- the app logged an unexpected error.

This also removed a double message: "Product not found" pages no longer pop up a red "not found" notification as well.

## Re-test checklist (after the fixes)

- [x] **First, reload the page once with Ctrl+F5.** That's the last time it's needed: from now on a normal refresh always gets the newest version.
- [x] Create a product: only "Product created" (green), no red message.
- [x] Create a gift: tick **Free gift** first. The price becomes 0 and is locked. Save: only the green message.
- [ ] Try a gift with a price: you can't. The price is locked while the gift box is ticked. *(not reported in re-test 2; covered by automated tests)*
- [ ] Edit and save: only "Changes saved". *(not reported in re-test 2; covered by automated tests)*
- [x] Open SP-003 Normal shoes: no Gift badge any more. *(History entry not reported; verified on the database, D-083)*

## Re-test 2 (2026-11-21, prompt #019)

| # | Step | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| 7 | After one reload, create `GF-04` "shoes for gift" as a free gift | Only "Product created", price $0.00 with the Gift badge | Only the green "Product created"; GF-04 at $0.00 with the Gift badge | **Passed** | [05](05-retest-2-only-success-message.png) |
| 8 | Look at SP-003 "Normal shoes" | No Gift badge, still $55.00 (migration 0004) | $55.00, no Gift badge | **Passed** | [05](05-retest-2-only-success-message.png) |

**Owner's verdict:** "Great, no error this time." The interface will be improved later (ECOM-018); it is good for testing the backend.
