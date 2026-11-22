# ADR-0012: CSV issues are warnings, review items or errors, and values are never silently changed

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-012, D-032, D-048, D-049, D-051, D-090 |

## Context

Each row in the CSV needs a clear answer: imported, held for a person, or refused. The guiding question is whether the system would have to guess what a value means.

## Decision

- **Three severities.** All issues on a row are collected, and the row's outcome follows the most severe one.
  - **Warning, imported.** Only lossless fixes: a stripped `$`, a normalised SKU, `12.0` read as `12`, a duplicate SKU in the file, or an archived product being restored.
  - **Review, held for a person.** Values that are zero or empty: a zero price or `free`, a zero weight, an empty required field.
  - **Error, rejected.** Anything invalid or dangerous: wrong field count, malformed or negative numbers, too many decimals, an unsupported currency, markup in a name, control characters, a bad SKU, an SKU conflict.
- **File-level errors refuse the whole upload:** too large (413), wrong media type (415), bad encoding, empty file, missing or duplicate columns, too many rows, malformed CSV.
- **Never silently change what a value means.** Rounding `9.999`, accepting `1,299.99` or `1.299,99`, exponent notation, `NaN` and `Infinity` are all errors. Trimming whitespace, a BOM and line endings are handled silently.
- **Duplicate SKUs in one file:** the last row wins, and earlier rows become `superseded`. If the last row is rejected or held, the earlier rows are not used instead. Rows sharing an SKU but describing different products are all rejected.
- **The import reuses the product's own value objects,** so a rule such as "no markup in names" exists in one place.
- **SQL-looking text is plain data.** `Robert'); DROP TABLE products;--` is accepted, and a test proves the table survives (queries are parameterised).

## Alternatives discarded

- **Rounding with a warning:** money would change without anyone noticing.
- **Reporting trimming as a warning:** every report would fill with noise.
- **Falling back to the last valid duplicate:** it would import data the file meant to replace.
- **Rejecting SQL-looking text:** security theatre that protects nothing and refuses legitimate names.
- **An allow-list of name characters:** it would refuse names like O'Brien.

## Consequences

- **The golden test on the sample, with an empty catalog:** 2 blank, 2 rejected, 6 needing review, 84 to create, 3 superseded and 3 warnings.
- Re-importing the same file reports the products as unchanged.
