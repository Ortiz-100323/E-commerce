# ADR-0003: A React single-page app with TanStack Query, react-hook-form and zod

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-003, D-076, D-079, D-087 |

## Context

The challenge asks for a UI for product CRUD, search and purchase. There's no need for server-side rendering, and the only client-side state is the cart.

## Decision

- **React 19 and strict TypeScript, built with Vite,** served as static files by nginx.
- **TanStack Query** for server state:
  - queries retry up to twice, and only on network errors and 5xx;
  - changes (mutations) never retry by themselves, because repeating a change must be a person's decision.
- **React Router.** Search filters, sorting and pages live in the URL, so a refresh or a shared link shows the same list.
- **react-hook-form with zod** for forms. The browser checks only the obvious things; the server stays the authority, and its 422 errors land on the matching fields.
- **CSS Modules with shared design tokens.** No UI kit.
- **One `ApiError`** for every failed call: a Problem Details answer, any other error answer, or a network failure.
- **Every package is pinned exactly,** at a version at least two weeks old, checked against its publish date.

## Alternatives discarded

- **Next.js.** Server rendering isn't needed, and it adds a Node runtime to the deployment.
- **Redux.** There is no complex client state beyond the cart.
- **A component kit (MUI, Chakra).** A heavier bundle for simple screens, and a generic look.
- **A hand-written fetch cache.** Loading, error, retry and invalidation are exactly what TanStack Query provides.

## Consequences

- The frontend tests (Vitest, Testing Library, MSW) run against a fake API, with an 80% coverage gate (96% measured).
- Every test also fails if the page shows an unexpected error ([ADR-0023](0023-test-first-and-one-runner.md)).
