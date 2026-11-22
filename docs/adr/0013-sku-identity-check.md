# ADR-0013: An existing SKU that names a different product is rejected

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-050, D-090 |

## Context

The SKU is the key ([ADR-0007](0007-sku-is-the-natural-key.md)). A reused or mistyped SKU in a CSV would overwrite a different product, and that product's orders and history would no longer describe it.

## Decision

- **When a row's SKU already exists,** active or archived, the two names are compared after normalisation (NFKC, case-folding, collapsed whitespace):
  - equal names mean the same product;
  - a trigram similarity of 0.5 or more is treated as a rename, and goes through the confirmed update;
  - below 0.5, the row is rejected with `sku_belongs_to_different_product`, and the message names both products.
- **The similarity is computed in the domain,** in pure Python, in the same way as PostgreSQL's `pg_trgm`. It is checked against PostgreSQL's documented values.
- **The same check runs on rows that share an SKU in one file,** and again at commit time, under the locks.
- **It is configurable:** `IMPORT_SKU_IDENTITY_POLICY` (`name_similarity`, `exact_name` or `sku_only`) and `IMPORT_SKU_SIMILARITY_THRESHOLD`.

## Alternatives discarded

- **Trust the SKU blindly (`sku_only`):** a silent overwrite.
- **Exact names only:** harmless renames such as "Running Shoes" → "Running Shoes Pro" would be rejected.
- **Send conflicts to review with a "same product" button:** only zero and empty values are reviewable ([ADR-0011](0011-csv-import-review-workflow.md)), and the fix is a new SKU in the file.
- **Run the similarity in SQL:** the rule couldn't be unit-tested without PostgreSQL, and the preview would need a database round trip per row.

## Consequences

- A drastic rename through CSV (for example "Cotton T-Shirt" → "Organic Tee") is rejected. The workaround is to rename the product in the admin first.
- Whether suppliers reuse SKUs is an open business question (CQ-10).
