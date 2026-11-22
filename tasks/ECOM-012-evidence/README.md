# ECOM-012: Test evidence

| Field | Value |
|---|---|
| Tickets | [ECOM-012](../ECOM-012.md): CSV import UI, tested together with [ECOM-010](../ECOM-010.md) and [ECOM-011](../ECOM-011.md) |
| Test type | Manual acceptance test (owner), in the browser |
| Tester | Project owner |
| Date | 2026-11-22 |
| Environment | Local compose stack, admin at http://localhost:3000/admin, build of `feature/ECOM-012-import-ui` with the code review round 2 fixes (D-093), the owner's own catalog (RS-001 already present) |
| File | `Documents/Code Challenge E-Commerce.csv`, 97 rows |
| Result | **Passed**: 1 change request (CR-01) done and verified by the owner in the re-test; observations deferred to [ECOM-018](../ECOM-018.md) |

## Test runs

| # | Step | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| 1 | Upload the sample and resolve review rows one by one | Each decision moves the row and updates the counts; commit stays locked and lists the waiting lines | Needs review (4), Updates (1), New (85), commit locked with "Waiting for a decision on lines 36, 41, 47, 50, 52." | **Passed** (ECOM-012 criteria 1 to 3) | [01](01-review-in-progress.png) |
| 2 | Skip line 41 (WS-001, name only spaces); correct line 52's category | Line 41 is skipped and no longer waiting; line 52 is checked again | Line 41 marked "Skipped" and gone from the waiting list (lines 36, 52 left), **but still shown in Needs review** with its editor | Passed as designed; **change request CR-01** | [02](02-skipped-row-stays-in-needs-review.png) |
| 3 | Confirm the RS-001 update (line 36) | Now → After table; once ticked, commit unlocks | Description, category, price, stock and weight shown; "Every row has a decision"; **Commit import** enabled | **Passed** (ECOM-011 criterion 2, ECOM-012 criterion 3) | [03](03-update-confirmed-ready-to-commit.png) |
| 4 | **Commit import** | "Imported" with the counts; nothing left to edit | "Imported. 88 created, 1 updated, 1 skipped."; editors disabled | **Passed** (ECOM-011 criterion 4: everything applied at once) | [04](04-imported-result.png) |
| 5 | Open Admin → Products | The imported products are listed; the free gifts carry the Gift badge at $0.00 | The catalog lists the imported products (Air Purifier, Baby Monitor, Backpack…), with gifts at $0.00 and the Gift badge | **Passed** | [05](05-products-after-import.png) |

**Owner's verdict:** "It worked in general. Very good. We need to improve user experience but the functionality is great."

The database confirms it: the import is stored as committed with 88 created, 1 updated and 1 skipped, and 89 products have an audit entry from this import.

## Change requests

### CR-01: skipped rows leave the review screen and get their own tab

- **Request (owner):** "I believe those which we skipp should dissapear from screen [...] I mean dissapeared from the review screen, we can have a tab for them."
- **Before:** a skipped row stayed in its tab (Needs review, or Updates for a cleared update) with a "Skipped" label. That followed D-092, so it is a change, not a defect.
- **Change:**
  - A new **Skipped** tab, between Unchanged and Rejected.
  - A skipped row leaves Needs review, Updates or New and appears only under Skipped. The other tabs no longer count it.
  - On the Skipped tab the reviewer can still change their mind: correct or confirm a review row, or tick an update again, and the row returns to its tab.
  - After the import is committed, the Skipped tab is read-only.
- **Tests:** 5 component tests describe the new behaviour. They failed on the old screen and pass now.
- **Journal:** D-094.
- **Status:** Done. **Verified by the owner in the re-test** (below).

## Observations (deferred to ECOM-018, UI polish)

The owner asked for a better user experience in general. Seen in the screenshots:

- **OBS-01, disabled buttons look like active ones.** A locked **Save correction** or **Commit import** is a solid grey button, close to the enabled style. Screenshots 01, 02 and 04.
- **OBS-02, long values are cut off in the editor.** The Description field shows "This product name is only whites…". Screenshots 01 and 02.
- **OBS-03, invisible spaces in the raw line.** Line 41's name is only spaces, so its raw line looks oddly indented, without saying why. Showing the spaces (for example as `·`) would explain the "name is empty" message. Screenshot 01.
- **OBS-04, a finished import still shows editors.** After the commit, rows are listed with disabled editors instead of a short read-only summary. Screenshot 04.
- **OBS-05, wording.** "SKU RS-001 also appears on line(s) 2" should say "line 2". Screenshot 03.
- **OBS-06, long review lists.** The commit bar scrolls out of view, and after a decision the next row to review isn't brought into focus.

## Re-test checklist (CR-01)

Press **Ctrl+F5** once first, so the browser loads the new screen (D-084).

1. Reopen your committed import (Admin → Import CSV, or the same address as before).
   → The tabs now include **Skipped (1)**; Needs review shows **0**; line 41 is under Skipped, read-only.
2. Upload the sample again and press **Skip this row** on any review row.
   → It leaves Needs review at once; Needs review drops by 1 and Skipped goes up by 1.
3. On the Skipped tab, type a name for line 25 (or 41) and press **Save correction**.
   → It leaves Skipped and appears under New.
4. If RS-001 shows under Updates, untick **Confirm this update**.
   → It moves to Skipped; tick it there and it goes back to Updates.
5. Press **Discard import** to finish the test without importing.

## Re-test 1 (2026-11-22, prompt #029)

| # | Step | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| 6 | Upload the sample again (after the commit) and skip line 7 (Yoga Mat) | Line 7 leaves Needs review and is listed under **Skipped**, where it can still be corrected or confirmed | Needs review (5), **Skipped (1)**, Unchanged (84); on the Skipped tab, line 7 with the explanation, **Save correction** and **Confirm as free gift**; the waiting list no longer includes line 7 | **Passed** (CR-01) | [06](06-retest-skipped-tab.png) |

**Owner's verdict:** "It worked, commit and lets go to next one."

Screenshot 06 also confirms ECOM-011 criterion 5 in the portal: after the commit, the same file shows **Unchanged (84)**.
