# Requirements check

Every requirement in the code challenge document, in the document's order and in its words, with where it is met and whether it is done. Checked on 2026-11-22.

The links are checked by `python testing/run.py docs`, which also runs in GitHub Actions. Every file must exist, and every test named as `file::test` must exist in that file.

**Status:** **Done** means met and proven. **Partial** means met in part; what is missing is in the notes.

| # | Requirement | Where it is met | Status |
|---|---|---|---|
| R-01 | "Build an enterprise-grade e-commerce application" | See R-01 below. | Done |
| R-02 | "Must use a local DB (SQL/No SQL)" | See R-02 below. | Done |
| R-03 | "CRUD for Products." | See R-03 below. | Done |
| R-04 | "Products can also be imported from a csv." | See R-04 below. | Done |
| R-05 | "Proposed csv structure": name, sku, description, category (string/enum), price (decimal), stock (string/int), weight_kg (decimal) | See R-05 below. | Done |
| R-06 | "Please download and use the following CSV file as an example" | See R-06 below. | Done |
| R-07 | "Please add in your readme file the date you downloaded the example CSV file provided." | See R-07 below. | Done |
| R-08 | "Search for Products." | See R-08 below. | Done |
| R-09 | "Purchase products (payment provider not necessary, fake the payment)." | See R-09 below. | Done |
| R-10 | "UI is required for: CRUD for Products." | See R-10 below. | Done |
| R-11 | "UI is required for: Search for Products." | See R-11 below. | Done |
| R-12 | "UI is required for: Purchase for Products." | See R-12 below. | Done |
| R-13 | "The application must be runnable as a docker container." | See R-13 below. | Done |
| R-14 | "On a readme.md document your decisions, approach, alternatives considered." | See R-14 below. | Done |
| R-15 | "AI is allowed, if you use it, please remove comments from the code." | See R-15 below. | Done |
| R-16 | "Please provide your solution in a Github repository." | See R-16 below. | **Partial** |
| R-17 | "Please add instructions on how to run the project locally." | See R-17 below. | Done |
| R-18 | Note: "ask the right questions and guide AI to make use of your experience and foreseeing skills" | See R-18 below. | Done |

## Where each requirement is met

### R-01: Enterprise grade

- [ADR-0001](adr/0001-modular-monolith-with-ddd.md): DDD bounded contexts with layers enforced by import-linter (11 contracts).
- [ADR-0023](adr/0023-test-first-and-one-runner.md): test-first development and the CI gates.
- [ADR-0016](adr/0016-append-only-audit-trail.md): an append-only audit trail.
- [ADR-0019](adr/0019-no-overselling-row-locks.md): concurrency safety.
- [.github/workflows/ci.yml](../.github/workflows/ci.yml): CI on GitHub Actions.

### R-02: A local database

- PostgreSQL 17 as the `db` service in [docker-compose.yml](../docker-compose.yml) ([ADR-0004](adr/0004-postgresql-only.md)).
- Migrations in [backend/migrations](../backend/migrations).
- [test_migrations.py::test_the_migrations_match_the_table_definitions](../testing/backend/integration/test_migrations.py)

### R-03: Product CRUD

- API: [catalog/api/router.py](../backend/src/ecommerce/catalog/api/router.py), with create, read, update, and delete as archive ([ADR-0008](adr/0008-archive-instead-of-delete.md)) plus restore.
- Tests:
  - [test_products_api.py::test_full_crud_over_http](../testing/backend/api/test_products_api.py)
  - [test_products_api.py::test_a_put_with_a_stale_version_is_a_conflict](../testing/backend/api/test_products_api.py)
  - [test_products_api.py::test_the_same_create_sent_twice_stores_one_product](../testing/backend/api/test_products_api.py)

### R-04: CSV import

- API: [imports_router.py](../backend/src/ecommerce/catalog/api/imports_router.py), a review workflow committed all or nothing ([ADR-0011](adr/0011-csv-import-review-workflow.md), [ADR-0012](adr/0012-csv-issue-taxonomy.md)).
- Tests:
  - [test_imports_api.py::test_the_golden_workflow_imports_90_products_with_6_resolution_entries](../testing/backend/api/test_imports_api.py)
  - [test_imports_api.py::test_committing_twice_is_a_safe_retry](../testing/backend/api/test_imports_api.py)

### R-05: The proposed CSV structure

- The importer requires exactly these seven columns:
  - [test_import_fields.py::test_the_columns_are_the_seven_required_by_the_challenge](../testing/backend/unit/catalog/test_import_fields.py)
- How each column is typed:
  - `category` is a string, normalised, not a fixed enum (business question CQ-07);
  - `stock` is an integer;
  - `price` and `weight_kg` are exact decimals ([ADR-0006](adr/0006-money-and-weight-as-decimal.md)).
- [test_import_fields.py::test_a_clean_row_parses_into_typed_values_without_issues](../testing/backend/unit/catalog/test_import_fields.py)

### R-06: The sample CSV is used

- The downloaded file is kept unchanged as the golden fixture [sample-products.csv](../testing/fixtures/csv/sample-products.csv). It is byte-identical to the download (SHA-256 `6fc46b84badb1ac3…`).
- [test_import_golden.py::test_the_sample_gives_the_expected_outcomes_on_an_empty_catalog](../testing/backend/unit/catalog/test_import_golden.py)
- The owner imported it through the admin screen on a fresh clone ([ECOM-022 evidence](../tasks/ECOM-022-evidence/README.md)).

### R-07: The download date is in the README

- [README, "The sample CSV"](../README.md#the-sample-csv): **2026-11-20**.

### R-08: Product search

- `GET /api/v1/products` searches name, SKU and description, with filters, sorting and pages ([ADR-0010](adr/0010-search-with-ilike-and-trigrams.md)).
- Tests:
  - [test_product_search_api.py::test_q_searches_name_sku_and_description_literally](../testing/backend/api/test_product_search_api.py)
  - [test_product_search_api.py::test_every_filter_narrows_the_results](../testing/backend/api/test_product_search_api.py)

### R-09: Purchase with a fake payment

- The checkout API is in [ordering/api/router.py](../backend/src/ecommerce/ordering/api/router.py), and the fake card gateway in [payment_gateway.py](../backend/src/ecommerce/ordering/infrastructure/payment_gateway.py) ([ADR-0017](adr/0017-checkout-and-fake-payment.md)).
- Tests:
  - [test_orders_api.py::test_an_approved_card_pays_the_order_and_takes_the_stock_with_an_audit_entry](../testing/backend/api/test_orders_api.py)
  - [test_orders_api.py::test_a_declined_card_returns_402_stores_a_failed_order_and_keeps_the_stock](../testing/backend/api/test_orders_api.py)
  - [test_checkout_safety_api.py::test_twenty_parallel_checkouts_for_the_last_unit_sell_it_once](../testing/backend/api/test_checkout_safety_api.py)

### R-10: A UI for product CRUD

- **Screens:** Admin → Products, at `/admin/products` ([ProductsTablePage.tsx](../frontend/src/features/admin/products/ProductsTablePage.tsx)), plus the new, edit and history pages ([ProductFormPages.tsx](../frontend/src/features/admin/products/ProductFormPages.tsx), [ProductHistoryPage.tsx](../frontend/src/features/admin/products/ProductHistoryPage.tsx)).
- **CSV import screens:** Admin → Import CSV ([ImportUploadPage.tsx](../frontend/src/features/admin/imports/ImportUploadPage.tsx), [ImportReviewPage.tsx](../frontend/src/features/admin/imports/ImportReviewPage.tsx)).
- **Tests:**
  - [adminProducts.test.tsx::creates a product and shows it in the table, recorded under the logged-in admin](../testing/frontend/adminProducts.test.tsx)
  - [adminProducts.test.tsx::edits a product and the table shows the new values](../testing/frontend/adminProducts.test.tsx)
  - [adminProducts.test.tsx::archives after confirmation and restores, and the table follows](../testing/frontend/adminProducts.test.tsx)

### R-11: A UI for search

- **Screen:** the shop at `/` ([StorefrontPage.tsx](../frontend/src/features/storefront/StorefrontPage.tsx)), with search, filters, sorting and pages.
- **Tests:**
  - [storefront.test.tsx::lists active products by name, with prices and badges](../testing/frontend/storefront.test.tsx)
  - [storefront.test.tsx::shows an empty state that explains what to do](../testing/frontend/storefront.test.tsx)
  - [product-card.spec.ts::an empty search explains what to do next](../testing/e2e/specs/product-card.spec.ts)

### R-12: A UI for purchase

- **Screens:** cart, checkout and confirmation ([CartPage.tsx](../frontend/src/features/storefront/checkout/CartPage.tsx), [CheckoutPage.tsx](../frontend/src/features/storefront/checkout/CheckoutPage.tsx), [OrderConfirmationPage.tsx](../frontend/src/features/storefront/checkout/OrderConfirmationPage.tsx)), plus My orders ([MyOrdersPage.tsx](../frontend/src/features/account/MyOrdersPage.tsx)).
- **Tests:**
  - [checkout.test.tsx::pays with 4242, shows the confirmation and empties the cart](../testing/frontend/checkout.test.tsx)
  - [purchase.spec.ts::an imported product is found in the shop, bought, and its stock goes down](../testing/e2e/specs/purchase.spec.ts)
  - [purchase.spec.ts::a double click on Pay buys only once](../testing/e2e/specs/purchase.spec.ts)

### R-13: Runs in Docker

- `docker compose up --build` starts the database, backend and frontend, applies the migrations and seeds the first admin ([docker-compose.yml](../docker-compose.yml), [ADR-0022](adr/0022-four-containers-and-same-origin-proxy.md), [ADR-0030](adr/0030-first-run-migrations-and-admin-only.md)).
- This was proven from a fresh clone in an empty folder ([ECOM-022](../tasks/ECOM-022.md)).

### R-14: The README documents decisions, approach and alternatives

- **Decisions and alternatives:** [README, "Decisions and alternatives"](../README.md#decisions-and-alternatives) has 30 decisions, each with the main alternatives discarded and a link to its record in [docs/adr](adr/README.md).
- **Approach:** [README, "Approach"](../README.md#approach) covers:
  - the data first;
  - nothing ambiguous guessed;
  - the domain first;
  - tests first;
  - small tickets with a review gate;
  - every decision recorded;
  - business questions with safe defaults;
  - verification the way a reviewer runs it.

  It was added after this check first found it missing (D-127).
- **Also in the README:** the architecture, out of scope, next steps and how AI was used.
- `run.py docs` fails if any of these README sections is missing.

### R-15: No comments in the code

- [check_no_comments.py](../testing/scripts/check_no_comments.py) fails on any comment in Python (docstrings included), TypeScript, JSON, CSS, HTML, SQL, Dockerfiles, YAML, nginx config, TOML, INI and shell files.
- It scans `backend`, `frontend`, `testing`, `docker`, `docker-compose.yml` and `.github`, and skips only lock files and generated folders.
- It runs as `python testing/run.py nocomments` in the `ci` container and on the GitHub Actions host.
- [test_check_no_comments_files.py::test_scan_covers_every_kind_of_code_and_config_file](../testing/tooling/test_check_no_comments_files.py)
- [ADR-0025](adr/0025-no-comments-in-code.md)

### R-16: A GitHub repository

- The public repository is `github.com/Ortiz-100323/E-commerce`. Its `main` holds ECOM-000 to ECOM-021 and ECOM-017, and CI there is green.
- **Gap:** the hand-in work (ECOM-022 to ECOM-024) is committed locally but **not pushed yet**. GitHub's `main` is at `4852c07`.

### R-17: Instructions to run locally

- The README's [Quick start](../README.md#quick-start), [Running without Docker](../README.md#running-without-docker) and [Running the tests](../README.md#running-the-tests).
- Every command was run as written:
  - with Docker, from a fresh clone;
  - without Docker, on Windows, after the D-125 fix ([ECOM-023](../tasks/ECOM-023.md)).
- [test_local_run.py::test_serve_starts_the_production_app_on_the_compatible_loop](../testing/backend/unit/test_local_run.py)

### R-18: Asking the right questions and guiding the AI

- The business questions CQ-01 to CQ-10, each with a working default, are in [§11.3 of the architecture document](TECHNICAL_ARCHITECTURE.md#113-questions-for-the-customer-business-stakeholder) and in the README.
- Every prompt and reply is in [PROMPT_HISTORY.md](PROMPT_HISTORY.md), and every decision in [JOURNAL.md](JOURNAL.md).
- Every ticket, with its plan, acceptance criteria and evidence, is on the [ticket board](../tasks/README.md).
