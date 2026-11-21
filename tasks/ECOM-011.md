# ECOM-011: CSV import: review workflow, commit and audit

| Field | Value |
|---|---|
| Type | Story (backend) |
| Phase | 3 |
| Status | **Backlog** |
| Depends on | ECOM-010 |
| Architecture | §4.2 (`ImportBatch`), §6.1, §6.4, §6.5 (commit time) |

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

## Test plan

- Aggregate unit tests; API tests for the whole golden workflow on real PostgreSQL; a stale-row test.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
