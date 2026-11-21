# ECOM-005: Product CRUD and search API

| Field | Value |
|---|---|
| Type | Story (backend) |
| Phase | 1 |
| Status | **Done** |
| Depends on | ECOM-004 |
| Architecture | §4.3, §4.5, §4.6, CC-02, CC-05 |
| Journal | D-072, D-075 |

## Context

The admin needs to create, read, update, archive and restore products, and shoppers need to search them.

## Scope

- Use cases: `CreateProduct`, `UpdateProduct`, `ArchiveProduct`, `RestoreProduct`, `GetProduct`, `SearchProducts`, `ListCategories`.
- Endpoints: `GET/POST /products`, `GET/PUT/DELETE /products/{id}`, `POST /products/{id}/restore`, `GET /categories`.
- Search: `q` over name, SKU and description (LIKE wildcards escaped), filters `category`, `min_price`, `max_price`, `in_stock`, `tag`, `status`, sorting and offset pagination (`page_size` ≤ 100).
- Money serialised as a string with a currency code.

## Acceptance criteria

1. Full CRUD works over HTTP; DELETE archives, and archived products are hidden from the default search.
2. A price of 0 without `gift: true` returns 422 `zero_price_requires_gift`. The original text said `zero_price_requires_gift_confirmation`; see D-075.
3. PUT with a stale `version` returns 409 `version-conflict` with `current_version`.
4. Creating a duplicate SKU returns 409 `duplicate-sku`.
5. Search handles every filter, pagination and a `%` typed by the user.
6. A contract test sends bad input to every endpoint and gets Problem Details back.

## Plan (D-075)

1. **Request and response shapes**
   - **`POST /products` body:** `sku`, `name`, `description` (optional, default empty), `category`, `price`, `stock`, `weight_kg` and `gift` (default `false`).
     - Unknown fields are refused.
     - `stock`, `version` and `gift` must be real JSON integers and booleans: `"10"`, `1.5`, `true` as a stock, or `"yes"` as a gift, are refused.
     - Text fields are capped at 10,000 characters as an abuse limit; the real limits are the domain's.
   - **`PUT /products/{id}` body:** the same fields **without `sku`** (it never changes), plus the `version` the client read. Everything is replaced.
   - **Product response:** `id`, `sku`, `name`, `description`, `category`, `price` (a string such as `"89.99"`), `currency` (`"USD"`), `stock`, `weight_kg` (a string such as `"0.800"`), `gift`, `tags`, `status`, `is_sellable`, `version`, `created_at` and `updated_at`.
   - **Status codes:** `POST` returns **201** with a `Location` header. `GET`, `PUT`, `DELETE` and restore return **200** with the product, so the screen always gets the new `version`.
2. **Every change endpoint requires `X-Actor-Name`** (ECOM-004's `require_actor`), and its unit of work is opened with that actor, so every change lands in the history.
3. **Use cases** live in `catalog/application/products.py` and take the time from the `Clock` port. Reads (`SearchProducts`, `ListCategories`) go through a `ProductQueries` port, implemented with SQL in `catalog/infrastructure/product_queries.py`.
4. **Search**
   - **Text:** `q` (at most 200 characters) is trimmed. `\`, `%` and `_` are escaped, and the search is `ILIKE '%q%'` on name, SKU and description, served by the trigram indexes.
   - **Filters:**
     - `category` matches case-insensitively.
     - `min_price` and `max_price` are inclusive and at least 0; a minimum above the maximum is a 422 `invalid_range`.
     - `in_stock=true` means stock > 0, and `false` means stock = 0.
     - `tag=GIFT` keeps gifts only.
   - **Status:** `status` defaults to `ACTIVE`, which is what the storefront shows. The admin sends `ALL` or `ARCHIVED`.
   - **Sorting:** `sort` is one of `name`, `-name`, `price`, `-price`, `created_at` or `-created_at` (default `name`). Ties are always broken by id, so pages never overlap.
   - **Paging:** `page` ≥ 1 and `page_size` 1–100 (default 20). The response is `{items, total, page, page_size}`.
5. **Categories:** the distinct categories of active products, merged case-insensitively and sorted alphabetically: `{items: [...]}`.
6. **Errors:**
   - `VersionConflict` → 409 `version-conflict` with `current_version`.
   - `DuplicateSku` → 409 `duplicate-sku` with `sku`.
   - `ProductAlreadyExists` → 409 `product-already-exists`.
   - `ProductNotFound` → 404.

   Problem mappings can now add a `detail` and extra fields. Query and header errors share one `InvalidParameters` error that carries its location.
7. **Retries:** a `PUT` with a stale version whose changes are already in place returns 200 with the current product instead of 409. That is the usual case of a retry after a timeout, and nothing would be lost.

## Verification (2026-11-21)

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | Full CRUD over HTTP; DELETE archives; archived products are hidden from the default search | **Pass** | Real database, one flow:<br>• create (201, `Location`) → read → update (version 2) → delete (200, `ARCHIVED`, not sellable) → read it still → restore (version 4).<br>• The history shows all four changes with the right names.<br>• After DELETE the product disappears from `GET /products` and appears with `status=ARCHIVED`. |
| 2 | A price of 0 without `gift: true` returns 422 `zero_price_requires_gift` | **Pass** | Real database:<br>• `price: "0"` without the gift flag gives 422, field `price`, and nothing is stored.<br>• With `gift: true` it gives 201 with tag `GIFT`.<br>• A PUT that removes the gift flag from a free product also gives 422. |
| 3 | PUT with a stale `version` returns 409 `version-conflict` with `current_version` | **Pass** | Real database:<br>• Two saves with version 1: the second gets 409 with `current_version: 2` and the detail "You edited version 1, but the product is now at version 2."<br>• Its change is not stored, and the history has no entry for it. |
| 4 | Creating a duplicate SKU returns 409 `duplicate-sku` | **Pass** | Real database:<br>• `rs-001` against an existing `RS-001` gives 409, with `sku: "RS-001"` and "SKU RS-001 is already taken."<br>• There is still only one product. |
| 5 | Search handles every filter, pagination and a `%` typed by the user | **Pass** | Real database, 5 products, one of them archived:<br>• Text search covers name, SKU and description, in any letter case and with spaces around it.<br>• `100%` and `%` match only the product whose description holds a `%`, and `_` matches only a real underscore. A `\` gives no error.<br>• Every filter is tested, alone and combined.<br>• All 6 sort orders are tested.<br>• Three pages of 3 have no overlap, with the right `total`.<br>• Categories are listed once each, archived ones excluded. |
| 6 | A contract test sends bad input to every endpoint and gets Problem Details back | **Pass** | The test reads the API's own OpenAPI document. For each of the 10 endpoints that take input, it generates:<br>• a bad id;<br>• a bad value for every query parameter;<br>• a missing actor header;<br>• a malformed body, a body of the wrong type and an empty body.<br>That makes 29 cases. Every response is checked for the Problem Details shape and status. A second test fails if a new endpoint isn't covered, and a third checks that all 4 product changes require `X-Actor-Name`. |

## Failure cases and retries (D-072)

| Situation | What the caller gets | Result |
|---|---|---|
| Body is not valid JSON | 400 `malformed-request` | Pass |
| Unknown field, missing field or wrong type (including `sku` in a PUT, `"10"`, `1.5` or `true` as a stock, `"yes"` as a gift) | 422 `validation-error`, location `body`, with codes `unknown_field`, `required`, `not_an_integer` or `not_a_boolean` | Pass |
| Domain rules broken (bad SKU, markup in the name, negative price, weight with 4 decimals) | 422 listing **all four** issues at once | Pass |
| Price with 3 decimals, `NaN` price, `Infinity` weight, negative stock, a 10,001-character name | 422 `too_many_decimal_places`, `not_a_number`, `too_small` or `too_long` | Pass |
| Price 0 without `gift: true` | 422, field `price`, code `zero_price_requires_gift` | Pass |
| `X-Actor-Name` missing on a change | 422, location `header`; nothing stored | Pass |
| Unknown product id on GET, PUT, DELETE, restore and history | 404 `not-found`, "Product not found." | Pass |
| Id that isn't a UUID, on the same 5 endpoints | 422, location `path`, code `not_a_uuid` | Pass |
| Duplicate SKU (any letter case) | 409 `duplicate-sku` with `sku` | Pass |
| PUT with a stale version | 409 `version-conflict` with `current_version`; nothing stored, no history entry | Pass |
| Search: `page_size` 0 or 101, `page` 0 or `abc`, negative price, `abc` price, unknown `sort`/`status`/`tag`, `in_stock=maybe`, `q` over 200 characters | 422, location `query`, one precise code each | Pass |
| Search: `min_price` above `max_price` | 422, location `query`, code `invalid_range` | Pass |
| Database down | 503 `service-unavailable` with `Retry-After: 1` | Pass |
| **Retry:** the same create sent twice | First 201, second 409 `duplicate-sku`; one product, one history entry | Pass |
| **Retry:** a PUT repeated after it succeeded | 200 with the current product; no new version, no new entry | Pass |
| **Retry:** a PUT that changes nothing | 200, same version, no history entry | Pass |
| **Retry:** DELETE twice, and restoring an active product | 200 each time; one history entry, one version | Pass |
| **Concurrency:** two admins save the same version | One 200, one 409; only the first change is stored | Pass |
| **Stock:** a negative stock | 422 `too_small`. `in_stock` and `is_sellable` never count an empty or archived product as sellable | Pass |

**Also in this ticket:**
- `ProblemMapping` gained `detail` and `extra`.
- `InvalidHeader` became `InvalidParameters`, which carries its location (header or query).
- The in-memory test doubles now behave like the real repository: a save with no changes is skipped, the version moves only on a real change, and commit writes history entries.
- `testing/backend/live.py` starts the app against the test database.
- `X-Actor-Name` is declared required, so Swagger marks it and a missing name is reported with any body errors in one 422.
- The tag filter uses SQLAlchemy's `any_()`, not the deprecated `ARRAY.any()`.

**Totals:** 132 new tests: 17 use-case tests, 41 API tests, 43 search tests and 31 contract tests. The `ci` container passes:
- lint, mypy over 72 files, 5 contracts and the no-comments check;
- 20 tooling tests;
- 500 backend tests, with 100% coverage of the domain and catalog application code;
- 6 frontend tests and the smoke checks.

The live stack was rebuilt and checked without writing anything, so the database stays empty for the owner's own tests.

## Owner's test in Swagger (2026-11-21, prompt #014)

The owner created `RS-001` (Running Shoes) and the free gift `GC-001`, then edited, archived and restored the gift and checked the categories (`Gifts`, `Sports`). The history of `GC-001` reads: created → archived → restored, at version 3. The edit sent the values the product already had, so it correctly returned version 1 and wrote no "changed" entry. Accepted.

## Test plan

- Application tests with in-memory fakes; API tests on real PostgreSQL; the contract test.
- Every row of "Failure cases and retries" has a test.

## Business view

- **What was built:** the product API. Products can be created, read, edited, archived and restored, and the catalogue can be searched with filters, sorting and pages.
- **Why:** challenge rules CC-02 (CRUD) and CC-05 (search). It is also the base for the admin screen (ECOM-007) and the shop (ECOM-008).
- **Main goal:** manage products safely. No duplicate SKUs, no lost edits, no free products by accident, and every change in the history.
- **Human testable or background:** **testable**, in Swagger.
- **What to test:** see the step-by-step list in prompt #013 of the prompt history.

## Definition of done

- Acceptance criteria pass, written test-first; application coverage ≥ 95%.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
