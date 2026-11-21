# ECOM-010: CSV import: parsing, classification and policies

| Field | Value |
|---|---|
| Type | Story (backend) |
| Phase | 3 |
| Status | **In Review**: committed; the owner tests it through the ECOM-012 import screen (prompt #026) |
| Depends on | ECOM-005 |
| Architecture | §2, §6.1–§6.3, §6.5, CC-03, CC-04 |
| Journal | D-072, D-090 |

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

## Plan (D-090)

1. **Scripts first.** `testing/scripts/profile_csv.py` reports the file's facts: encoding, BOM, line endings, final newline, row count, blank rows and duplicate SKUs. `testing/scripts/simulate_import.py` runs the real classifier on a file and prints the report. Both are run on the sample before anything else, and §2 is corrected where it is wrong. **Profile result:** every format fact in §2 holds (UTF-8 without BOM, CRLF, no final newline, 97 data rows, blank lines 62–63, RS-001 on lines 2 and 36, BS-021 on lines 11, 56 and 89). A first look with Git Bash's `sed` had wrongly suggested LF, because it strips carriage returns before displaying; the script reads the raw bytes.
2. **Domain** (`catalog/domain/importing/`, pure Python, no I/O):
   - `policies.py`: one enum per §6.3 setting, plus `ImportPolicies` with the defaults.
   - `fields.py`: parses each raw value into the product's value objects and collects every issue with its severity and code (§6.2). It never throws.
   - `similarity.py`: trigram similarity computed the same way as PostgreSQL's `pg_trgm`, plus NFKC, case-fold and whitespace normalisation.
   - `classification.py`: the order of §6.2. Blank rows, then field count, then fields; the worst severity decides; then duplicates in the file (§6.5), then the comparison with the catalog (identity check → `update` with a field diff, `unchanged` or `create`).
3. **Infrastructure:**
   - `csv_reader.py` handles the file-level checks: size, media type, UTF-8 with an optional BOM, header normalisation, missing, duplicate and unknown columns, row limit, malformed CSV. It keeps each row's line number and raw text verbatim.
   - `ProductQueries.existing_by_skus()` loads the catalog's matching products in one query.
4. **Application:** `PreviewImport` reads the file, loads the existing products and classifies. It **never writes**; the stored batch and the review come in ECOM-011.
5. **API:** `POST /api/v1/imports/preview` takes the file as the request body (`Content-Type: text/csv`); Swagger shows a file picker. It returns the counts, the file warnings and every row (line, outcome, SKU, issues, changes). File-level errors return Problem Details with the §6.2 status (413, 415 or 422) and the code. Being read-only, it needs no `X-Actor-Name`. A multipart upload for `POST /imports` (ECOM-011) needs the `python-multipart` package, which waits for the owner's approval.
6. **Policies from settings:** `IMPORT_*` environment variables (§6.3) are read by `Settings` and turned into `ImportPolicies` by the composition root. A bad value stops the app at start-up with a clear message.
7. **Policy codes not named in §6.2:**
   - `create_only` rejects an existing SKU with `sku_already_exists`.
   - `accept_as_gift` imports a zero price as a gift, with the warning `zero_price_accepted_as_gift`.
   - `reject` variants reuse the review code as an error (`zero_price`, `zero_weight`, `empty_required_field`).
   - `reject_all` rejects every row of a duplicated SKU with `duplicate_sku_in_file` as an error.
   - The currency policy `reject` uses `unsupported_currency`.
8. **Fixtures:**
   - The sample is copied to `testing/fixtures/sample-products.csv` as the golden fixture.
   - Small edge-case fixtures: a BOM, a missing column, a duplicated column, an extra column, non-UTF-8 text, an unclosed quote, and every row-level code.
   - The oversized and too-many-rows files are generated inside the tests, so no large files sit in the repository.

## Failure cases and retries (D-072)

| Situation | What the caller gets | Result |
|---|---|---|
| Body over 5 MB | 413 `payload-too-large`, with `max_bytes`; the body stops being read at the limit, and nothing is classified | Pass |
| `Content-Type` not a CSV type (`text/csv`, `application/csv`, `application/vnd.ms-excel`) | 415 `unsupported-media-type` | Pass |
| Not UTF-8 | 422 `validation-error`, field `file`, code `invalid_encoding`, with the byte offset | Pass |
| Empty body, or a header of empty names | 422, field `file`, code `empty_file` | Pass |
| A required column missing | 422, field `file`, code `missing_columns`, naming them | Pass |
| The same column twice | 422, field `file`, code `duplicate_columns` | Pass |
| More rows than `IMPORT_MAX_ROWS` | 422, field `file`, code `too_many_rows`, with the limit | Pass |
| An unclosed quote | 422, field `file`, code `malformed_csv`, with the line | Pass |
| A bad row | Never an error response: the row is classified and listed with every issue | Pass |
| **Retry:** the same file previewed twice | Exactly the same report; nothing is stored, so a retry is always safe | Pass |
| **Stock:** negative, decimal or out-of-range stock | Rejected with `negative_value`, `not_an_integer` or `value_out_of_range`; `12.0` is accepted with `integer_normalized` | Pass |
| A bad policy setting at start-up | The backend refuses to start; the error names the setting (`zero_price_policy`, `max_rows`, `sku_similarity_threshold`…) | Pass |

## Verification (2026-11-21)

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | On an empty database the sample gives 2 `blank`, 2 `rejected`, 6 `needs_review`, 84 `create` and 3 `superseded` rows | **Pass** | Checked three ways:<br>• `simulate_import.py` printed exactly these numbers before any test was written.<br>• A golden test also checks the exact lines: blank 62–63; rejected 16 (`negative_value`) and 20 (`markup_in_name`); review 7, 25, 41, 47, 50, 52; superseded 2, 11, 56.<br>• The API on an empty real database returns the same summary, and stores nothing. |
| 2 | Exactly 3 warnings: 1 `currency_symbol_stripped` and 2 `duplicate_sku_in_file`, with 0 identity conflicts | **Pass** | The golden test finds exactly `(4, currency_symbol_stripped)`, `(36, duplicate_sku_in_file)` and `(89, duplicate_sku_in_file)`, and no `sku_conflict_in_file` or `sku_belongs_to_different_product`. |
| 3 | Every warning, review and error code in §6.2 has its own test | **Pass** | Each code has its own test:<br>• Row warnings: `currency_symbol_stripped`, `sku_normalized`, `integer_normalized`, `duplicate_sku_in_file`, `restores_archived_product`.<br>• Review: `empty_required_field` (each of the 6 columns, empty and spaces-only), `zero_price` (`0`, `0.00`, `free`, `FREE`, `$0`), `zero_weight`.<br>• Errors: `wrong_field_count`, `invalid_number` (6 forms), `unsupported_currency` (4 forms), `negative_value` (3 columns), `too_many_decimal_places`, `not_an_integer`, `value_out_of_range`, `value_too_long` (4 columns), `invalid_sku_format`, `markup_in_name`, `control_characters` (4 columns), `sku_conflict_in_file`, `sku_belongs_to_different_product`.<br>• File level: `file_too_large`, `unsupported_media_type`, `invalid_encoding`, `empty_file`, `missing_columns`, `duplicate_columns`, `too_many_rows`, `malformed_csv`, `unknown_column_ignored`.<br>• `same_file_already_pending` needs stored batches, so it comes with ECOM-011. |
| 4 | Each file-level error returns the right status, and no batch is created | **Pass** | API tests on the real database: 413 for an oversized body, 415 for JSON or plain text, and 422 with field `file` for each of the 6 unreadable-file cases. After each one, the products and audit tables are still empty. The contract test also sends JSON (415), an empty CSV (422) and non-UTF-8 bytes (422) to the endpoint. |
| 5 | Changing a policy setting changes the classification, with no code change | **Pass** | `IMPORT_*` environment variables only, on the sample:<br>• `ZERO_PRICE_POLICY=reject` gives 4 rejected and 4 review.<br>• `ZERO_PRICE_POLICY=accept_as_gift` gives 86 created.<br>• `EMPTY_FIELD_POLICY=reject` gives 6 rejected.<br>• `CURRENCY_SYMBOL_POLICY=reject` gives 83 created and 3 rejected.<br>• `DUPLICATE_SKU_IN_FILE_POLICY=reject_all` gives 82 created and 7 rejected.<br>• `MAX_ROWS=96` refuses the file.<br>Every variant of every policy also has its own unit test, and a bad value stops the app with the setting's name. |

**Live check on your database:** the sample previews with 83 `create` and 1 `update`, because your catalog already holds RS-001. The update lists its exact changes (description, and category Sports → Footwear). Sending JSON through the website's proxy gives 415. Nothing was stored.

**Also in this ticket:**
- `.gitattributes` keeps `testing/fixtures/**` byte-exact, so the CRLF, BOM and Latin-1 fixtures stay as they are.
- New shared problem types: `payload-too-large` (413) and `unsupported-media-type` (415).
- The contract test now understands CSV request bodies.

**Totals:** 161 new backend tests and 10 new tooling tests. The `ci` container passes:
- all static checks, with 4 import contracts;
- 44 tooling tests;
- 628 backend tests, with 100% coverage of the domain and application code, the import rules included;
- 89 frontend tests;
- the smoke checks.

## Test plan

- Unit tests per code and per policy variant; the golden classification test; edge-case fixture tests.

## Business view

- **What was built:** the first half of the CSV import. You send a product file and get back, row by row, what would happen:
  - which products would be created or updated, with the exact changes;
  - which rows need a person to check them (a price of 0, an empty name, a weight of 0…);
  - which rows are refused, and why;
  - which rows are duplicates.

  **Nothing is saved yet**; that is ECOM-011.
- **Why:** challenge rules CC-03 and CC-04. The sample file is deliberately messy, and every row must be accounted for, never silently dropped or guessed.
- **Main goal:** a trustworthy, explainable verdict for every row, with rules the business can change through settings, without a programmer.
- **Human testable or background:** **testable** in Swagger (`POST /api/v1/imports/preview`).
- **What to test:** see prompt #025 of the prompt history.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
