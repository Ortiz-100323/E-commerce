# ADR-0021: Request IDs and one JSON log line per request

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-063, D-056 |

## Context

When something fails, the error a user sees must lead straight to the matching log lines, and the logs must be readable by a machine.

## Decision

- **A pure ASGI middleware gives every request an ID** and returns it in `X-Request-ID`.
  - An incoming ID is kept only if it is 8 to 64 letters, digits or hyphens. Anything else is replaced, so a client can't inject text into the logs.
- **Logs are JSON, one object per line,** with `time`, `level`, `logger`, `message` and `request_id`.
- **Each request writes exactly one line,** with the method, path, status and duration. The query string is never logged, and uvicorn's access log is turned off.
- **Every Problem Details answer carries the same `request_id`.**
- **One health endpoint,** `GET /api/v1/health`, reports the database too. The container health checks use it.

## Alternatives discarded

- **Starlette's `BaseHTTPMiddleware`:** simpler to write, but it has known problems with exceptions and streaming responses.
- **Separate liveness and readiness endpoints:** only useful with an orchestrator that restarts containers. They can be split later without breaking anything.

## Consequences

- Support can search the logs by the ID on an error screen.
- Metrics and tracing aren't included. They are listed in the README's next steps.
