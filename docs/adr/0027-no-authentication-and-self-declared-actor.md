# ADR-0027: No authentication, with a self-declared name as the audit actor

| Field | Value |
|---|---|
| Status | Superseded by [ADR-0028](0028-one-login-with-roles.md) |
| Date | 2026-11-21 |
| Journal | D-021, D-038, D-040 |

## Context

The challenge doesn't ask for authentication. The audit trail still needs a "who" for every change.

## Decision

- **The admin area was open,** documented as a known gap.
- **The admin screens asked "Who is reviewing?" once,** stored the answer in the browser, and sent it as the `X-Actor-Name` header on every change. A change without it got 422.
- **The name was stored as the audit actor,** labelled as self-declared.
- **The audit format was designed so that a real login could replace the name** without changing it.

## Alternatives discarded

- **HTTP Basic auth for `/admin`:** cheap, but it adds credential handling to the run instructions.
- **A reviewer field on every form:** repetitive and inconsistent.
- **Recording the IP address:** not a meaningful "who", and it is personal data.
- **Leaving the actor empty:** the audit couldn't answer "who".

## Consequences

- This was in force from ECOM-004 to ECOM-018.
- It was replaced by real logins with roles in ECOM-019. The audit format didn't change; only the actor's source did.
