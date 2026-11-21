# ECOM-006: Frontend foundation: API client, routing, server state, actor prompt

| Field | Value |
|---|---|
| Type | Technical task (frontend) |
| Phase | 2 |
| Status | **Backlog** |
| Depends on | ECOM-005 |
| Architecture | §4.6 (frontend), §5 |

## Context

The skeleton's single page uses plain `fetch`. The real UI needs a typed client, routing and server-state caching.

## Scope

- A typed API client and the `ApiError` class that parses every Problem Details response.
- TanStack Query, React Router, react-hook-form and zod.
- The app shell with Storefront and Admin areas.
- The "Who is reviewing?" prompt: the name is kept in `localStorage` and sent as `X-Actor-Name` on every change.
- A shared component that renders `errors[]` on form fields, and a notification for other problems (with `request_id` on 5xx).
- MSW for frontend tests; ESLint (with `react/no-danger`) and Prettier.

## Acceptance criteria

1. Routes for both areas render inside the shell.
2. A validation problem from the API marks the matching form fields.
3. A 5xx problem shows a notification that includes the `request_id`.
4. The admin area asks for the reviewer's name once, and every change request carries it.

## Test plan

- Vitest, React Testing Library and MSW specs in `testing/frontend` for each criterion.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
