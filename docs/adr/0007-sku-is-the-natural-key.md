# ADR-0007: The SKU is the natural key, and product names aren't unique

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-010, D-068 |

## Context

The sample CSV has "Running Shoes" three times and "Bluetooth Speaker" four times, under different SKUs. The import needs a stable way to tell whether a row is a new product or an existing one.

## Decision

- **The SKU is unique.** It is normalised by trimming and upper-casing.
- **A UUID `ProductId` is the internal identity.** Orders and audit entries reference it.
- **The SKU never changes.** It is the identity the importer matches on, so a different SKU means a different product. `PUT` refuses a `sku` field rather than ignoring it.
- **Names are not unique.** Variants with the same name are normal.

## Alternatives discarded

- **Unique names:** they would reject the sample's legitimate variants.
- **An editable SKU:** a later import would no longer find the product, and would create a duplicate.

## Consequences

- Re-importing a file updates the right products.
- A reused or mistyped SKU could overwrite a different product. [ADR-0013](0013-sku-identity-check.md) guards against that.
