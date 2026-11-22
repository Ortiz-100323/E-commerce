# ADR-0005: Repositories on SQLAlchemy Core with explicit mapping

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-071, D-060 |

## Context

The architecture first planned SQLAlchemy's imperative ORM mapping. But `Product` keeps its state in private attributes and frozen value objects. The ORM would have to instrument the domain class itself and map every value object as a composite.

## Decision

- **Tables are defined with SQLAlchemy Core.** Repositories write rows with `insert`/`update` and rebuild aggregates through their normal constructors. For a product, the translation is about 40 lines, type-checked by mypy.
- **Repositories run on the Unit of Work's session,** so one use case commits or rolls back everything together.
- **Every constraint is named,** and a domain error is raised from the name. For example, `uq_products_sku` becomes `DuplicateSku`, caught inside a SAVEPOINT so the transaction stays usable.
- **`ecommerce/schema.py` gathers every table for Alembic.**
  - A test compares the migrated database with the table definitions.
  - Separate tests write invalid rows with direct SQL to prove each CHECK constraint, because Alembic doesn't compare CHECK constraints.

## Alternatives discarded

- **ORM imperative mapping:** it adds SQLAlchemy state to the domain objects and needs composites for every value object.
- **Hand-written SQL strings:** Core gives typed statements, parameter binding and one engine for the whole app.

## Consequences

- The domain classes stay plain Python.
- Read-only queries, such as search and order lists, go straight to SQL through query ports, without loading aggregates.
