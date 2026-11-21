# ECOM-001: Backend foundation: shared kernel, Problem Details errors, quality gates

| Field | Value |
|---|---|
| Type | Technical task |
| Phase | 1 |
| Status | **Done** |
| Depends on | ECOM-000 |
| Architecture | §3.2, §4.1, §4.6, §8.1, §8.3 |
| Journal | D-061 to D-066 |

## Context

The skeleton proves the stack runs. Before the first business feature, the backend needs the shared pieces every context will use, and the quality gates the skeleton deferred.

## Scope

- `shared_kernel/domain`: `Money` (Decimal, 2 places, USD), base `DomainError`, `DomainValidationError` carrying a list of `ValidationIssue {field, code, severity, message, params}`.
- `shared_kernel/application`: `UnitOfWork` and `Clock` ports.
- `shared_kernel/infrastructure`: SQLAlchemy `UnitOfWork` implementation, structured JSON logging and a request-ID middleware.
- `shared_kernel/api`: RFC 9457 Problem Details handlers for every error source in §4.6, and the mapping table from Pydantic error types to our codes.
- Quality gates: `mypy --strict` added to `run.py lint`.
- Integration tests: decide between the compose `ecommerce_test` database and **Testcontainers**, and record the decision in the journal (decided: compose database, D-061).

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

## Verification (2026-11-21)

| # | Criterion | Result |
|---|---|---|
| 1 | Every error is Problem Details | Pass. API tests cover an unknown route (404), a wrong method (405, with `Allow`), broken JSON (400), Pydantic errors (422), domain validation (422), not found (404), Open-Meteo down (502), database down (503 with `Retry-After`) and an unexpected exception (500). Each response is `application/problem+json` with `type`, `title`, `status`, `instance` and a `request_id` that matches the header. Also checked by hand through nginx on the live stack. |
| 2 | 400 for broken JSON, 422 with `errors[]` | Pass. Errors use dotted paths with indexes (`lines[1].quantity`), the query location, stable codes and plain `params`. Every issue is reported at once. |
| 3 | Values never echoed | Pass. Five bad requests carrying a card number (wrong type, pattern mismatch, unknown field, inside a number, broken JSON): it appears in neither the response nor the logs. |
| 4 | `X-Request-ID` and the log line | Pass. The header is on every response, 500s included. A safe incoming ID is kept and an unsafe one replaced. One JSON log line per request with the same ID, without the query string; checked in the container logs too. |
| 5 | `Money` rules | Pass: floats and booleans raise `TypeError`; more than 2 places, other currencies, NaN, infinity and text that isn't a number raise `InvalidMoney`. |
| 6 | mypy strict | Pass: 44 source files, migrations included |

**Also in this ticket**
- The SQLAlchemy Unit of Work, with 5 integration tests (commit, implicit rollback, rollback on error, explicit rollback, no session outside it).
- Testcontainers was not adopted; see D-061.
- A coverage test reads the OpenAPI document and fails if a request schema can raise a Pydantic error type without a code.
- The `ci` container passes: lint, mypy, 3 layer contracts, no comments, 19 tooling tests, 120 backend tests, 6 frontend tests and 4 smoke checks.

## Business view

- **What was built:** the backend's house rules: how the system says "no" clearly, how every request gets a reference number, how money is handled, how saving is all-or-nothing, and automatic quality checks.
- **Why:** every later feature (products, CSV import, orders) needs these. Building them once means every screen behaves the same way.
- **Main goal:** when something goes wrong, people get a clear and safe message, and support can trace exactly what happened.
- **Human testable or background:** mostly background. The visible part is the error messages and the reference number. Money and the all-or-nothing saving become visible with prices (ECOM-002/005) and orders (ECOM-013 onwards).
- **What to test:**
  1. In the portal, a normal search still works.
  2. A city that doesn't exist shows "City not found".
  3. With the database stopped, the portal says the service is unavailable; once the database is started again, searches work with nothing restarted.
  4. In Swagger, a wrong form lists every problem at once and never repeats what was typed.
  5. Every Swagger response shows an `x-request-id`, and the same number appears in the backend log.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
