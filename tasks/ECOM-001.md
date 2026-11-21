# ECOM-001: Backend foundation: shared kernel, Problem Details errors, quality gates

| Field | Value |
|---|---|
| Type | Technical task |
| Phase | 1 |
| Status | **Backlog** |
| Depends on | ECOM-000 |
| Architecture | §3.2, §4.1, §4.6, §8.1, §8.3 |

## Context

The skeleton proves the stack runs. Before the first business feature, the backend needs the shared pieces every context will use, and the quality gates the skeleton deferred.

## Scope

- `shared_kernel/domain`: `Money` (Decimal, 2 places, USD), base `DomainError`, `DomainValidationError` carrying a list of `ValidationIssue {field, code, severity, message, params}`.
- `shared_kernel/application`: `UnitOfWork` and `Clock` ports.
- `shared_kernel/infrastructure`: SQLAlchemy `UnitOfWork` implementation, structured JSON logging and a request-ID middleware.
- `shared_kernel/api`: RFC 9457 Problem Details handlers for every error source in §4.6, and the mapping table from Pydantic error types to our codes.
- Quality gates: `mypy --strict` added to `run.py lint`.
- Integration tests move from the compose `ecommerce_test` database to **Testcontainers**, if the `ci` container can reach Docker; otherwise the compose database stays and the journal records why.

## Acceptance criteria

1. Every error response, including an unknown route, a wrong method, broken JSON, a Pydantic error and an unexpected exception, is `application/problem+json` with `type`, `title`, `status` and `request_id`.
2. Broken JSON returns 400 `malformed-request`; a schema error returns 422 `validation-error` with `errors[]`.
3. Submitted values are never echoed in an error response.
4. Every response carries an `X-Request-ID` header, and the same ID appears in the log line.
5. `Money` rejects floats, more than 2 decimal places and other currencies.
6. `mypy --strict` passes on the whole backend.

## Test plan

- Unit: `Money`, `ValidationIssue`, the conversion from `loc` to `field`, and a test that fails if a schema can raise an unmapped Pydantic type.
- API: a temporary test router that raises each error kind, asserting the Problem Details shape.
- A test sends a card number in a bad request and proves it is in neither the response nor the logs.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
