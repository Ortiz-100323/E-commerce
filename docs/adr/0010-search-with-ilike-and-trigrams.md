# ADR-0010: Search with `ILIKE` and `pg_trgm` indexes

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-017, D-028, D-075, D-087 |

## Context

The challenge asks for product search. Shoppers type parts of names, and admins type SKU prefixes such as `RS-0`. The catalog holds hundreds or thousands of products, not millions.

## Decision

- **`GET /api/v1/products?q=…` matches the name, SKU and description** with case-insensitive `ILIKE`, backed by `pg_trgm` GIN indexes.
- **LIKE wildcards** (`%`, `_`) in the user's text are escaped, so they're searched literally.
- **Filters:** category, price range, in stock, tag and status.
- **Sorting:** by name, price or date added, in either direction. Ties are broken by id, so pages are stable.
- **Offset pages with a total count.**
- **Abuse limits:** `q` at most 200 characters, and `page` at most 100,000.
- **Search reads go straight to SQL** through a `ProductQueries` port. No aggregates are loaded.
- **In the shop,** the whole search lives in the URL. Invalid values from a hand-edited link fall back to the defaults instead of showing an error page.

## Alternatives discarded

- **PostgreSQL full-text search (`tsvector`).** It adds stemming and ranking, but handles partial words and SKU prefixes poorly.
- **An external engine (Meilisearch, Elasticsearch).** Another service to run and keep in sync, out of proportion for this catalog.
- **Search on every keystroke.** An explicit Search button is simpler to test and sends fewer requests.

## Consequences

- No relevance ranking: results are sorted by the chosen field.
- If the catalog grows a lot, full-text search can be added behind the same port.
