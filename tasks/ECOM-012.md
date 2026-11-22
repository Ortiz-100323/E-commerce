# ECOM-012: CSV import UI: upload and review screen

| Field | Value |
|---|---|
| Type | Story (frontend) |
| Phase | 3 |
| Status | **Done**: the owner's portal test passed (prompt #028) and CR-01 passed the re-test (prompt #029) |
| Depends on | ECOM-011, ECOM-006 |
| Architecture | §5 (import screens), CC-03 |
| Journal | D-085, D-091, D-092, D-093, D-094 |
| Evidence | [Owner's portal test](ECOM-012-evidence/README.md) |

## Context

The reviewer needs a screen to see every row's outcome, fix flagged rows and commit.

## Scope

- `/admin/imports/new`: upload a CSV.
- `/admin/imports/:id`: one tab per outcome; an inline editor with confirm and skip for review rows; an old → new diff with a confirm checkbox and "confirm all" for update rows; reasons for rejected rows; the warnings list.
- The commit button stays disabled until the batch can be committed.

## Acceptance criteria

1. Uploading the sample shows the expected counts per tab.
2. Correcting a review row re-validates it and moves it to the right tab.
3. Commit enables only when nothing is left to resolve, and a 409 is explained to the user.

## Plan (D-092)

1. `src/api/imports.ts`: the import types and calls. `request()` can now send a file as the body (`text/csv`).
2. `src/features/admin/imports/`:
   - `ImportUploadPage`: choose a file, upload, open the review; file errors are shown on the page.
   - `ImportReviewPage`: header, status banner, commit and discard bar, tabs with counts, and the 409 explanations.
   - `ImportRows`: the review card (editor, confirm, skip), the update card (diff and checkbox), and the tables for new, unchanged, rejected, superseded, blank and warnings.
   - `queries.ts`: the import query and the mutations; a row decision replaces the row and the summary from the server's answer.
3. Routes, the **Import CSV** menu link, and history labels for import events.
4. Tests with MSW (`testing/frontend/support/fakeImports.ts` is a small stateful fake of the import API), and the page-wide error check of D-085 on every test.

## Failure cases and retries (D-072)

| Situation | What the user sees | Result |
|---|---|---|
| A file with missing columns, the wrong encoding, or broken quotes | The server's message under the file field ("File: These columns are missing: …"); no import is created | Pass |
| A file over 5 MB, or not a CSV | The server's explanation on the page, without a pop-up | Pass |
| An invalid correction (`abc` as a price) | The field error inside that row's card; the row stays in review | Pass |
| A correction that still needs review (price 0) | The row stays in **Needs review**, now offering **Confirm as free gift** | Pass |
| Commit refused: rows still pending | An alert with the server's explanation and the lines | Pass |
| Commit refused: products changed after the upload | "Nothing was imported. The rows on lines … now show the latest changes; confirm them again"; the import reloads and shows the new diff, unconfirmed | Pass |
| An unknown import address | "This import was not found." with a link to upload a file | Pass |
| An expired, committed or discarded import | A banner; no commit button; editors disabled | Pass |
| **Retry:** clicking a decision again | The server treats a repeated decision as a no-op (D-091); the screen shows the server's state | Pass |
| **Stock:** the screen never computes stock; it shows the values the server validated | — | Pass |

## Verification (2026-11-21)

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | Uploading the sample shows the expected counts per tab | **Pass** | Component test: the file is sent as the body (`text/csv`, reviewer name, file name), the page opens the review and shows Needs review (6), Updates (0), New (84), Unchanged (0), Rejected (2), Superseded (3), Blank (2), Warnings (3), opened on **Needs review** with 6 cards. |
| 2 | Correcting a review row re-validates it and moves it to the right tab | **Pass** | Component tests: filling line 50's weight moves it to **New** (counts 5 and 85) marked "Reviewed"; a correction to price 0 stays in review with **Confirm as free gift**; an invalid price shows its field error and keeps the row. |
| 3 | Commit enables only when nothing is left to resolve, and a 409 is explained | **Pass** | Component tests: commit is disabled with "Waiting for a decision on lines 3, 4", enabled only after both are resolved, then shows "Imported. 3 created, 0 updated, 0 skipped." Stale rows and "rows still pending" 409s are explained on the page; after the stale 409 the new diff (91.00) is shown, unconfirmed. |

**Live check on your stack:** both containers were rebuilt; your database is on migration 0006 with no imports yet. The portal serves `/admin/imports/new`, and an unknown import returns 404 through the website's proxy. A read-only preview of the sample against your catalog gives 83 new, 1 update (RS-001, line 36), 6 to review, 2 rejected, 3 superseded and 2 blank: those are the counts you should see in the portal. The smoke checks pass.

**Totals after code review:** 23 new frontend tests. The `ci` container passes all static checks, 44 tooling tests, 725 backend tests and 112 frontend tests (95.91% line coverage), plus the smoke checks.

## Business view

- **What was built:** the import screens in the admin portal.
  - **Import CSV** in the admin menu: choose a file, and it's checked at once.
  - The review screen shows every row in its tab: what needs a person, what will be updated, what's new, and what was refused and why.
  - Fix a row right there, confirm a free gift or a weight of 0, skip a row, or confirm updates one by one or all at once.
  - **Commit import** stays locked until every doubtful row has a decision; any refusal is explained in plain words.
- **Why:** challenge rule CC-03, and so the owner can test the whole import (ECOM-010 to ECOM-012) in the portal instead of Swagger.
- **Main goal:** a reviewer can take a messy file to a clean catalog without leaving the browser, and nothing is imported by mistake.
- **Human testable or background:** **testable** in the portal at http://localhost:3000/admin/imports/new.
- **What to test:** see prompt #026 of the prompt history.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.

## Code review round 2 (2026-11-21)

- Fixed file uploads always claiming to be `text/csv`. The browser client's actual media type is now preserved, so a selected non-CSV file reaches the server as non-CSV and the existing 415 explanation is shown on the page. Files whose browser media type is empty still use the safe `text/csv` fallback.
- Confirm actions now send the row outcome displayed to the reviewer. This prevents a repeated click or network retry from silently approving a different outcome after server-side reclassification.
- Added API-client and component regressions for the upload media type and visible error. The focused import UI suite passes with 35 tests.

## Owner's portal test (2026-11-22)

The owner imported the sample in the portal: "Imported. 88 created, 1 updated, 1 skipped." Verdict: "It worked in general. Very good. We need to improve user experience but the functionality is great." Full record in [ECOM-012-evidence](ECOM-012-evidence/README.md).

**Change request CR-01 (D-094): skipped rows get their own tab.**

- A skipped row now leaves Needs review, Updates or New and is listed under a new **Skipped** tab (between Unchanged and Rejected). The other tabs no longer count it.
- On the Skipped tab the reviewer can still correct or confirm a review row, or tick an update again, and the row returns to its tab. After a commit the tab is read-only.
- Tab counts now come from the rows the server returns, because the server's per-outcome summary still counts skipped rows under their outcome. No backend change.
- Written test-first: 5 component tests failed on the old screen and pass now. The `ci` container passes the static checks, no comments, and 114 frontend tests (95.97% line coverage); the smoke checks pass. The portal container is rebuilt.

The owner's general UX remarks, with six observations from the screenshots, are in [ECOM-018](ECOM-018.md).

**Re-test (2026-11-22, prompt #029):** passed. Skipping line 7 moved it to **Skipped (1)**, with its correction and confirm actions still available. The owner accepted ECOM-010, ECOM-011 and ECOM-012.
