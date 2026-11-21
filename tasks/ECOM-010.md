# ECOM-010: CSV import: parsing, classification and policies

| Field | Value |
|---|---|
| Type | Story (backend) |
| Phase | 3 |
| Status | **Backlog** |
| Depends on | ECOM-005 |
| Architecture | §2, §6.1–§6.3, §6.5, CC-03, CC-04 |

## Context

The sample CSV is deliberately dirty. Every row must be classified, never thrown away silently, using rules the customer can change by configuration.

## Scope

- `testing/scripts/profile_csv.py` and `simulate_import.py`, run first to re-verify the expected numbers in §2.
- The CSV reader adapter: size, media type, UTF-8 (BOM tolerated), header check, CRLF, quotes.
- Row classification into `create`, `update`, `unchanged`, `needs_review`, `rejected`, `superseded` and `blank`, using the full issue taxonomy (§6.2).
- The configurable policies (§6.3), each variant with its own tests.
- The SKU identity check against the database and within the file (§6.5).
- The sample CSV copied to `testing/fixtures/` as the golden fixture, plus edge-case fixtures (BOM, missing column, oversized, non-UTF-8).

## Acceptance criteria

1. On an empty database the sample gives 2 `blank`, 2 `rejected`, 6 `needs_review`, 84 `create` and 3 `superseded` rows.
2. It gives exactly 3 warnings: 1 `currency_symbol_stripped` and 2 `duplicate_sku_in_file`, with 0 identity conflicts.
3. Every warning, review and error code in §6.2 has its own test.
4. Each file-level error returns the right status, and no batch is created.
5. Changing a policy setting changes the classification, with no code change.

## Test plan

- Unit tests per code and per policy variant; the golden classification test; edge-case fixture tests.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
