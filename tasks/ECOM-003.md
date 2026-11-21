# ECOM-003: Catalog persistence: schema, repository and Unit of Work

| Field | Value |
|---|---|
| Type | Story (backend) |
| Phase | 1 |
| Status | **Backlog** |
| Depends on | ECOM-002 |
| Architecture | §4.4 |

## Context

Products must be stored in PostgreSQL without leaking the ORM into the domain.

## Scope

- Alembic migration: `products` table with `NUMERIC(12,2)` price and `NUMERIC(10,3)` weight, CHECK constraints mirroring the invariants, a unique index on `sku`, the `pg_trgm` extension and GIN trigram indexes on name, SKU and description.
- SQLAlchemy imperative mapping of `Product`.
- `ProductRepository` interface in the domain and its SQLAlchemy implementation.
- Optimistic locking on the `version` column.

## Acceptance criteria

1. A product round-trips through the repository with every field intact, including Decimal precision.
2. The database itself rejects a negative price, negative stock, negative weight, and a zero price without the gift tag.
3. A second product with the same SKU is rejected by the unique index.
4. Saving with a stale `version` raises a version-conflict error.
5. The migration upgrades and downgrades cleanly.

## Test plan

- Integration tests against real PostgreSQL for each criterion, including direct SQL writes that the CHECK constraints must block.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
