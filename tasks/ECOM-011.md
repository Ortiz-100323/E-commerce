# ECOM-011: CSV import: review workflow, commit and audit

| Field | Value |
|---|---|
| Type | Story (backend) |
| Phase | 3 |
| Status | **Done**: accepted by the owner after the portal test of the whole import (prompts #028 and #029) |
| Depends on | ECOM-010 |
| Architecture | §4.2 (`ImportBatch`), §4.5, §6.1, §6.4, §6.5 (commit time) |
| Journal | D-037, D-072, D-091, D-093 |

## Context

A person reviews flagged rows and confirms updates before anything reaches the catalog, and every decision is audited.

## Scope

- The `ImportBatch` aggregate, with raw lines kept verbatim and each row's resolution history.
- Use cases and endpoints: `StartImport` (`POST /imports`), `GET /imports/{id}`, `ResolveImportRow` (`PATCH /imports/{id}/rows/{line}`), `CommitImport` (`POST /imports/{id}/commit`), `DiscardImport` (`DELETE /imports/{id}`).
- Commit in one transaction, locking products in SKU order; stale rows go back to review with 409.
- Batch expiry after 24 hours.
- Import events written to the audit log.

## Acceptance criteria

1. Only `needs_review` rows can be corrected; rejected rows cannot be edited.
2. Commit is refused with 409 `import-not-committable` while rows are unresolved or updates unconfirmed.
3. A product changed after the preview sends its row back to review with 409 `import-stale-rows`.
4. After resolving the sample's 6 review rows and committing, there are up to 90 products and exactly 6 resolution audit entries.
5. Re-importing the same file reports 84 `unchanged`.

## Plan (D-091)

1. **Domain** (`catalog/domain/importing/`):
   - `batch.py`: `ImportBatch` and `ImportRow`. Every row says which `actions` it allows. `confirm`, `correct` and `skip` record a `Resolution` (actor, time, values before and after, original issues) and a domain event.
   - Confirming and correcting re-run the ECOM-010 rules for that row (`evaluate_row`).
   - `errors.py`: `ImportNotFound`, `ImportRowNotFound`, `ImportNotPending`, `ImportRowNotResolvable`, `ImportNotCommittable`, `ImportStaleRows`, `InvalidCorrection`.
2. **Application:** `StartImport`, `GetImport`, `ResolveImportRow`, `CommitImport`, `DiscardImport`. Import events are mapped to audit entries, and an imported product's audit context names its batch, line and raw CSV line.
3. **Infrastructure:** migration 0006 (`import_batches`, `import_batch_rows`), `SqlAlchemyImportBatchRepository`, and `ProductRepository.lock_by_skus` (`SELECT … FOR UPDATE` in SKU order).
4. **API:** the five endpoints. The upload keeps the raw `text/csv` body of ECOM-010 (`file_name` as a query parameter), so no new package is needed. Two new problem types: `import-not-pending` and `import-row-not-resolvable`.

## Failure cases and retries (D-072)

| Situation | What the caller gets | Result |
|---|---|---|
| Upload without `X-Actor-Name` | 422 on the header; nothing stored | Pass |
| Upload over 5 MB, not CSV, or unreadable | 413, 415 or 422 on `file`, exactly like the preview; no batch is created | Pass |
| The same file uploaded while another copy is pending | 201 with the file warning `same_file_already_pending` (and that batch's id) | Pass |
| Unknown import or line | 404 `not-found` | Pass |
| Correcting a rejected or superseded row | 409 `import-row-not-resolvable`, with the line, outcome and action | Pass |
| Confirming an empty value (it must be corrected) | 409 `import-row-not-resolvable` | Pass |
| A correction that is still invalid (`heavy`, `-1`) | 422 with one error per column; the row is unchanged | Pass |
| A correction that reuses another row's SKU | 422 `duplicate_sku_in_file` | Pass |
| Commit with rows still pending | 409 `import-not-committable` with `pending_lines`; nothing written | Pass |
| A product changed after the upload | 409 `import-stale-rows` with `lines`; the rows get a fresh diff and must be confirmed again; no product is changed | Pass |
| Any change to an expired (24 h), committed or discarded import | 409 `import-not-pending` with `import_status` | Pass |
| **Retry:** confirm, skip or the same correction twice | 200, nothing new recorded | Pass |
| **Retry:** commit twice | 200 with the same import; products and audit entries are not duplicated | Pass |
| **Retry:** discard twice | 200 | Pass |
| **Stock:** the import sets stock levels, it never sells | Stock values go through the same rules as the admin form; negative or decimal stock is rejected (ECOM-010). Products are locked during the commit, so a checkout can't interleave with it | Pass |

## Verification (2026-11-21)

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | Only `needs_review` rows can be corrected; rejected rows cannot be edited | **Pass** | Unit tests for every outcome's allowed actions; API test: correcting line 16 (rejected) or skipping line 2 (superseded) gives 409 `import-row-not-resolvable`. |
| 2 | Commit is refused with 409 `import-not-committable` while rows are unresolved | **Pass** | API test on the sample: 409 with `pending_lines` [7, 25, 41, 47, 50, 52]; the products table stays empty. An unconfirmed update is also pending (unit and use-case tests). |
| 3 | A product changed after the preview sends its row back with 409 `import-stale-rows` | **Pass** | API test: upload, confirm, change the product's price in the admin API, commit → 409 with `lines` [2]; the row shows the new diff (91.00 → 94.99) and `changed_since_preview`; after confirming again, the commit succeeds. Also covered for a new SKU taken after the upload. |
| 4 | After resolving the 6 review rows and committing: up to 90 products, exactly 6 resolution entries | **Pass** | API test on the real database: 2 confirms (lines 7, 47 as gifts) and 4 corrections; commit → `created: 90`; 90 products, 2 of them free gifts; exactly 6 `import_row` audit entries. |
| 5 | Re-importing the same file reports 84 `unchanged` | **Pass** | API test: after the commit, the same file gives 84 unchanged, 6 review, 2 rejected, 3 superseded, 2 blank, and no "already pending" warning. |

**Also proven:** the batch, rows, history and decisions survive a round trip through PostgreSQL; migration 0006 downgrades and upgrades cleanly; the database refuses an unknown row outcome; an imported product's history starts with its row correction, then `product.created` with the raw CSV line.

**Totals after code review:** 97 new backend tests. The `ci` container passes all static checks (4 import contracts, no comments) and 725 backend tests, with 99.61% coverage of the domain and application code.

## Business view

- **What was built:** the second half of the import. An uploaded file is now kept as an import waiting for review:
  - a person confirms a free gift or a weight of 0, fixes an empty value, or skips the row;
  - updates to existing products show exactly what will change, and need a confirmation;
  - **Import** then applies everything at once, or nothing at all;
  - every decision is recorded with who made it and when.
- **Why:** challenge rules CC-03 and CC-04. A messy file must never reach the catalog without a person deciding on the doubtful rows.
- **Main goal:** a safe, all-or-nothing import with a full audit trail, which can't overwrite a product someone changed in the meantime.
- **Human testable or background:** testable in Swagger, and in the portal with ECOM-012.
- **What to test:** see prompt #026 of the prompt history.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.

## Code review round 2 (2026-11-21)

Two retry/concurrency defects were found and fixed:

- A retry of a `needs_review` confirmation could confirm a newly revealed `update` without the reviewer seeing that update. Confirm requests now include the outcome the reviewer saw; if the row has moved, the retry is a no-op and the new update remains pending.
- `SELECT ... FOR UPDATE` cannot lock a SKU that does not exist. Concurrent writers could therefore race to create the same new SKU and surface a generic duplicate error. Product writes and import commits now take the same transaction-scoped PostgreSQL advisory lock for each SKU, in sorted order, before checking or inserting it.

Regression tests cover the outcome-changing confirmation retry and blocking on an absent SKU. The complete backend suite passes with 725 tests and 99.61% scoped coverage.
