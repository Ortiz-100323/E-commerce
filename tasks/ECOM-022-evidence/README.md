# ECOM-022: Test evidence

| Field | Value |
|---|---|
| Ticket | [ECOM-022](../ECOM-022.md): One-command start, proven from a fresh clone |
| Test type | Fresh-clone run (automated checks), plus a manual acceptance test by the owner in the browser |
| Tester | Project owner (import), Claude (fresh clone and checks) |
| Date | 2026-11-22 |
| Environment | A fresh clone of `github.com/Ortiz-100323/E-commerce` at `4852c07`, in an empty folder, run as its own compose project with an empty database; shop at http://localhost:3000 |
| Result | **Passed**: no defects |

## Test runs

| # | Step | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| 1 | Log in as the seeded admin, **Import CSV**, upload `Code Challenge E-Commerce.csv` (the downloaded sample), review and commit | On an empty shop: 84 rows to create, 6 to review, 2 rejected. After the review: every review row is either created or skipped | "Imported. 85 created, 0 updated, 5 skipped". Needs review 0, New 85, Skipped 5, Rejected 2, Superseded 3, Blank 2, Warnings 3, 97 rows. The owner accepted one review row and skipped five (84 + 1 = 85) | **Passed** (criterion 4) | [01](01-sample-csv-imported.png) |
| 2 | Admin **Products** after the import | The imported products are listed as Active, with their category, price and stock | Air Purifier, Baby Monitor, Backpack, Bamboo Toothbrush, Bike Light Set, Bluetooth Speaker (BS-021 and BS-099), Board Game… all Active | **Passed** (criterion 4) | [02](02-admin-products-after-import.png) |

**Owner's verdict:** "I tested for us, its working."

## Notes

- The superseded rows are duplicate SKUs within the file, where the later row wins (D-049). The blank rows are empty lines. The warnings are soft notices on rows that were still imported.
