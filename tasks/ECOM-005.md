# ECOM-005: Product CRUD and search API

| Field | Value |
|---|---|
| Type | Story (backend) |
| Phase | 1 |
| Status | **Backlog** |
| Depends on | ECOM-004 |
| Architecture | §4.3, §4.5, CC-02, CC-05 |

## Context

The admin needs to create, read, update, archive and restore products, and shoppers need to search them.

## Scope

- Use cases: `CreateProduct`, `UpdateProduct`, `ArchiveProduct`, `RestoreProduct`, `GetProduct`, `SearchProducts`, `ListCategories`.
- Endpoints: `GET/POST /products`, `GET/PUT/DELETE /products/{id}`, `POST /products/{id}/restore`, `GET /categories`.
- Search: `q` over name, SKU and description (LIKE wildcards escaped), filters `category`, `min_price`, `max_price`, `in_stock`, `tag`, `status`, sorting and offset pagination (`page_size` ≤ 100).
- Money serialised as a string with a currency code.

## Acceptance criteria

1. Full CRUD works over HTTP; DELETE archives, and archived products are hidden from the default search.
2. A price of 0 without `gift: true` returns 422 `zero_price_requires_gift_confirmation`.
3. PUT with a stale `version` returns 409 `version-conflict` with `current_version`.
4. Creating a duplicate SKU returns 409 `duplicate-sku`.
5. Search handles every filter, pagination and a `%` typed by the user.
6. A contract test sends bad input to every endpoint and gets Problem Details back.

## Test plan

- Application tests with in-memory fakes; API tests on real PostgreSQL; the contract test.

## Definition of done

- Acceptance criteria pass, written test-first; application coverage ≥ 95%.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
