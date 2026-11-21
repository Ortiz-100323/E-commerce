# ECOM-016: Hardening, Playwright E2E and GitHub Actions

| Field | Value |
|---|---|
| Type | Technical task |
| Phase | 5 |
| Status | **Backlog** |
| Depends on | ECOM-012, ECOM-015 |
| Architecture | §8.1 (E2E), §10, CC-08 |

## Context

With every feature in place, we prove the real user journeys in the browser and harden the containers.

## Scope

- Playwright specs in `testing/e2e`, run by the `ci` container against the compose stack.
- Security headers and a CSP in nginx; upload limits.
- Non-root users and healthchecks in every image; an image size check.
- A GitHub Actions workflow that runs the same compose stack and `ci` container as local runs.

## Acceptance criteria

1. Playwright passes: import → review → commit → search → buy → stock decreases.
2. Playwright passes: a declined card leaves stock unchanged.
3. Responses carry the security headers and CSP.
4. Every container runs as a non-root user.
5. The GitHub Actions run gives the same result as the local `ci` container.

## Test plan

- The Playwright specs, plus a header check in the smoke test.

## Definition of done

- Acceptance criteria pass.
- `run.py all` is green locally and in GitHub Actions.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
