# ADR-0001: A modular monolith with DDD bounded contexts and enforced layers

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-002, D-016, D-065, D-066, D-095, D-115 |

## Context

The challenge asks for an enterprise-grade solution. The real logic sits in the CSV import rules and the checkout, not in the CRUD. That logic has to be testable without a web framework or a database.

## Decision

- **One deployable backend, split into bounded contexts:**
  - `catalog`: products, search, import, audit history;
  - `ordering`: cart quote, checkout, orders;
  - `identity`: accounts, sessions;
  - `shared_kernel`: Money, Actor, Principal, Problem Details, Unit of Work, audit writer.
- **Layers inside each context:** `domain → application → infrastructure / api`.
  - The domain imports no framework.
  - Use cases depend on ports, never on adapters.
- **Contexts never import each other:**
  - Ordering reads the catalog through its own `CatalogGateway` port. The adapter that implements it lives in `ecommerce/integration`, outside both contexts, and is wired in `main.py`.
  - Logins reach the other contexts only through an `Authenticator` port in the shared kernel.
- **A shared Unit of Work.** One transaction covers a whole use case, across contexts when needed (checkout changes stock and writes the order together).
- **import-linter enforces all of this** with 11 contracts in CI, including indirect imports. `mypy --strict` runs over the backend.

## Alternatives discarded

- **A flat CRUD app with one products module.** Fastest to write, but the import and checkout rules would end up in route handlers, untestable without HTTP and SQL.
- **Microservices per context.** Network calls, distributed transactions and more containers for a small shop. The contexts can still be split later, because they already talk through ports.
- **Domain events with eventual consistency between ordering and catalog.** Overkill in one process with one database. A shared transaction is simpler and strictly consistent.

## Consequences

- More files and indirection up front.
- Domain and application code run in plain unit tests (95% coverage gate, 99% measured).
- A wrong import fails CI, so the boundaries hold over time.
