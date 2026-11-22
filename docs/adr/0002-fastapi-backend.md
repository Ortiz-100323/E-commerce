# ADR-0002: FastAPI for the backend

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-001, D-060 |

## Context

The backend needs a typed HTTP layer with request validation and generated API documentation, and it must stay thin, because the business rules live in the domain ([ADR-0001](0001-modular-monolith-with-ddd.md)).

## Decision

- **Python 3.13 with FastAPI,** run by uvicorn and managed with uv. Every version is pinned in `backend/uv.lock`.
- **Pydantic v2 is used for the API schemas only.** The domain has its own value objects and never imports Pydantic or FastAPI.
- **The app is built by a factory.** `create_app(dependencies_factory)` receives the adapters, so tests pass fakes and production wires PostgreSQL.
- **Swagger** is served at `/docs` on the backend's port (8001).

## Alternatives discarded

- **Django with Django REST Framework.** Its ORM and app structure pull the domain towards the framework, which works against strict layering.
- **Flask.** No built-in validation or OpenAPI, so more glue to write and maintain.

## Consequences

- The OpenAPI document is generated from the code. Two contract tests read it: one checks that every endpoint has bad-input tests, and one checks that every validation error type has an error code.
- Pydantic shape checks and domain meaning checks are kept apart ([ADR-0020](0020-problem-details-errors.md)).
