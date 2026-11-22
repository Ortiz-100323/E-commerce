# ADR-0020: One error format: RFC 9457 Problem Details, with one validation vocabulary

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-017, D-046, D-047, D-062, D-075 |

## Context

Errors come from Pydantic, the domain, the application layer, Starlette, nginx and unexpected failures. Clients should handle all of them one way, and a form should show every problem at once, under the right field.

## Decision

- **Every error is `application/problem+json`,** with these fields:
  - `type` (`urn:ecommerce:problem:<name>`), `title`, `status`, `detail`, `instance` and `request_id`;
  - validation errors add `errors[]` with `location`, `field`, `code`, `message` and `params`.
- **Status codes:**
  - unparseable JSON is 400 `malformed-request`;
  - invalid input is 422 `validation-error`;
  - conflicts are 409 with a specific type;
  - nginx's own 413 is also returned as Problem Details.
- **Who checks what:** Pydantic checks shape (types, required fields, unknown fields refused). The domain checks meaning, and collects every issue before raising.
- **One `ValidationIssue` structure** is used by the API errors and the import row issues, with the same codes, so one frontend component renders both.
- **Each context hands the composition root a table** from its exceptions to problem types, so the shared kernel never imports a context.
- **Values are never echoed back.** Pydantic's `input` is dropped, so card numbers and personal data can't come back in a response or a log.
- **A 500 never shows the exception.** It carries the `request_id` used in the logs.
- **Contract tests read the OpenAPI document** and fail if any Pydantic error type has no code, or any endpoint lacks a bad-input test.

## Alternatives discarded

- **FastAPI's default `{"detail": [...]}` beside custom shapes elsewhere:** two formats for clients.
- **A custom error envelope:** it reinvents a standard.
- **`about:blank` for everything:** clients can't branch on the type.
- **Echoing rejected values:** handy for debugging, but it leaks sensitive data.

## Consequences

- The frontend has one `ApiError` parser. Field errors land on form fields; everything else is a notification.
- New endpoints are covered by the contract tests automatically.
