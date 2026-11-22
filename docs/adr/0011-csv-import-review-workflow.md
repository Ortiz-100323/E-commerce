# ADR-0011: The CSV import is a review workflow, committed all or nothing

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-011 (superseded), D-030, D-033, D-037, D-090, D-091, D-092, D-094 |

## Context

The sample CSV contains currency symbols, words as prices, zero prices, negative stock, empty fields, blank lines, markup and SQL-looking text, and duplicate SKUs. The first plan was a partial import with a per-row report (D-011). The owner wanted zero and empty values, and updates to existing products, decided by a person, not by a silent rule.

## Decision

- **An import is an `ImportBatch` aggregate,** stored in `import_batches` and `import_batch_rows`.
  - States: `PENDING_REVIEW`, then `COMMITTED`, `DISCARDED` or `EXPIRED` (after 24 hours, computed when read, so no background job is needed).
  - Each row keeps its raw line and raw values unchanged, beside its current values, outcome, issues, diff and decision history.
- **Each row gets an outcome:** `create`, `update` (with an old → new diff), `unchanged`, `needs_review`, `rejected`, `superseded` or `blank`.
- **Each row lists what it allows** (the API returns `actions`):
  - review rows (a zero or empty value) can be corrected, confirmed (a zero price as a gift, a zero weight) or skipped;
  - an update to an existing SKU must be confirmed or skipped;
  - rejected rows can't be edited; the fix belongs in the source file.
- **The commit:**
  - is allowed only when nothing is left to decide;
  - runs in one transaction, locking the batch and then the products in SKU order;
  - checks every row again under the lock. If a product changed since the preview, nothing is imported, the stale rows get a fresh diff, and the answer is 409.
- **Retries are safe everywhere:** the same decision twice records nothing new, and committing a committed import returns it unchanged.
- **Upload:** the file is the raw `text/csv` request body, up to 5 MB and 10,000 rows.
- **There is a read-only preview endpoint,** `POST /imports/preview`, which writes nothing.

## Alternatives discarded

- **Partial import with a per-row report (D-011):** bad rows are dropped silently, and zero prices go live unseen.
- **A stateless dry run, with the client re-sending the file and its decisions:** no audit trail, fragile payloads, and the file is parsed twice.
- **Import first, fix later:** contradicts the owner's requirement.
- **Making rejected rows editable:** the owner limited editing to zero and empty values.
- **Multipart upload:** it would need the `python-multipart` package. The raw body needs nothing extra and keeps the bytes untouched for the encoding check.

## Consequences

- The review screen is the largest piece of the UI.
- On an empty shop, the sample gives 84 to create, 6 to review and 2 rejected ([ADR-0012](0012-csv-issue-taxonomy.md)).
- Every decision is audited ([ADR-0016](0016-append-only-audit-trail.md)).
