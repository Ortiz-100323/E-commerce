# ECOM-006: Frontend foundation: API client, routing, server state, actor prompt

| Field | Value |
|---|---|
| Type | Technical task (frontend) |
| Phase | 2 |
| Status | **Done** |
| Depends on | ECOM-005 |
| Architecture | §4.6 (frontend), §5 |
| Journal | D-072, D-076, D-077 |

## Context

The skeleton's single page uses plain `fetch`. The real UI needs a typed client, routing and server-state caching.

## Scope

- A typed API client and the `ApiError` class that parses every Problem Details response.
- TanStack Query, React Router, react-hook-form and zod.
- The app shell with Storefront and Admin areas.
- The "Who is reviewing?" prompt: the name is kept in `localStorage` and sent as `X-Actor-Name` on every change.
- A shared component that renders `errors[]` on form fields, and a notification for other problems (with `request_id` on 5xx).
- MSW for frontend tests; ESLint (with `react/no-danger`) and Prettier. ESLint was replaced by a raw-HTML check (D-077).

## Acceptance criteria

1. Routes for both areas render inside the shell.
2. A validation problem from the API marks the matching form fields.
3. A 5xx problem shows a notification that includes the `request_id`.
4. The admin area asks for the reviewer's name once, and every change request carries it.

## Packages added (approved by the owner in prompt #015)

| Package | Version | Kind | Why |
|---|---|---|---|
| `@tanstack/react-query` | 5.108.2 | runtime | Server state: caching, loading and error states, retries |
| `react-router` | 8.5.2 | runtime | Pages and URLs for the storefront and admin areas |
| `react-hook-form` | 7.92.0 | runtime | Forms, and placing server errors on fields with `setError` |
| `zod` | 4.6.7 | runtime | Form rules that mirror the server's (the reviewer name today) |
| `@hookform/resolvers` | 7.0.8 | runtime | Connects zod to react-hook-form |
| `msw` | 3.0.7 | dev | Fake API responses in tests: 422, 409, 404, 5xx, network down, an HTML 502 |
| `prettier` | 3.10.1 | dev | One code format, checked in CI |

Each is pinned exactly and was the newest release on 2026-11-07, two weeks before the install (`npm view <package> version --before 2026-11-07`).

**Not added: ESLint and its plugins** (D-077). The newest `typescript-eslint` (8.73.0) supports TypeScript below 6.1 only. Our TypeScript 7 no longer ships the JavaScript compiler API it needs, so ESLint can't read `.tsx` files at all. On top of that, `eslint-plugin-react` stops at ESLint 9. ESLint's main job here was `react/no-danger`, so `testing/scripts/check_no_raw_html.py` now enforces that rule and four related ones, and runs in `run.py lint`. `tsc --noEmit` (strict) keeps doing the type checking.

## Plan (D-076)

1. **API client** (`src/api/`)
   - `request()` prefixes `/api/v1` and sends and parses JSON. Any failure becomes an **`ApiError`** with `status`, `problem` (the type without the `urn:ecommerce:problem:` prefix), `title`, `detail`, `requestId`, `errors[]` and the raw `body`.
   - An error response that isn't Problem Details (an HTML 502, or JSON of another shape), and a success whose body isn't JSON, become `invalid-response`. A failed fetch becomes `network-error`.
   - The typed `productsApi` covers every ECOM-005 endpoint. **Change functions require the actor**, and the client percent-encodes it.
2. **Server state:** queries retry at most twice, only on network errors and 5xx. **Mutations never retry.** Every query error, and every mutation error except validation (which the form shows), goes to the notifications.
3. **Routing and shell:**
   - `/` is the shop. `/admin` redirects to `/admin/products`. `/weather` keeps the temporary page until ECOM-009, and anything else shows "Page not found".
   - nginx already sends every address to the app, so these routes work on a reload too.
4. **"Who is reviewing?"**
   - The admin area shows the dialog until a valid name is given, applying the server's rules: trimmed, 1–100 characters, no control characters.
   - The name is stored in `localStorage` under `ecommerce.actor`, with an in-memory fallback when storage is blocked.
   - The admin header shows "Reviewing as <name>", with **Change** and **Cancel**.
5. **Errors on screen:**
   - `applyProblemToForm()` marks each matching field (`aria-invalid`, with the message linked by `aria-describedby`) and focuses the first one.
   - `<FormProblems>` lists the rest at the top of the form. `<TextField>` is the shared input.
   - Notifications show the title and detail. For 5xx and network errors they add "Reference: <request_id>".

## Verification (2026-11-21)

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | Routes for both areas render inside the shell | **Pass** | `/` shows the shop, with "Shop" marked as the current page. `/admin/products` shows the admin area, and `/admin` redirects there. The header links move between the two. `/weather` still works, and an unknown address shows "Page not found" with a link back. All of them render inside the same header and navigation (7 tests). |
| 2 | A validation problem from the API marks the matching form fields | **Pass** | A form posts to the fake API, which answers 422:<br>• The SKU and price fields get `aria-invalid` and the server's exact messages, and the first one gets focus.<br>• Problems with no matching field ("Reviewer name: Field required", `weight_kg`) are listed at the top of the form.<br>• No notification pops up for a validation problem. |
| 3 | A 5xx problem shows a notification that includes the `request_id` | **Pass** | A read that keeps failing with 500 is tried 3 times in total, then shows "An unexpected error occurred." and "Reference: req-7f3a". A failed change shows its reference after **one** request. A read that recovers on the retry shows no notification. |
| 4 | The admin area asks for the reviewer's name once, and every change request carries it | **Pass** | The first visit to the admin area shows the dialog and hides the content. After "  Maria  " is entered, the header says "Reviewing as Maria" and the name is stored trimmed. Opening the app again doesn't ask. Archive and restore both send `X-Actor-Name: %C5%81ukasz` for "Łukasz", and the shop never asks for a name. |

## Failure cases and retries (D-072)

| Situation | What the person sees | Result |
|---|---|---|
| The API answers 422 with `errors[]` | Each message under its field; the others at the top of the form; no notification | Pass |
| The API answers 409 | A notification with the title ("The product was changed by someone else. Reload it and try again.") | Pass |
| The API answers 404 | A notification with the title and detail, without a reference; not retried | Pass |
| The API answers 5xx | A notification with "Reference: <request_id>" | Pass |
| The network is down | "We can't reach the server. Check your connection and try again."; no crash | Pass |
| The proxy answers an HTML 502; JSON that isn't Problem Details; a success that isn't JSON | "Something went wrong (status 502). Please try again." with the proxy's request id; no crash | Pass |
| Storage is blocked | The prompt still works and the name lasts for the session | Pass |
| A name that is blank, spaces only, 101 characters, or contains a tab | The dialog shows the problem, marks the field and saves nothing | Pass |
| A name in another alphabet ("Łukasz", "李") | Sent percent-encoded (`%C5%81ukasz`, `%E6%9D%8E`) | Pass |
| **Retry:** a read fails with 5xx or a network error | Retried up to 2 times (3 requests in all), then the notification | Pass |
| **Retry:** a change fails (5xx or 409) | **Exactly one request**; the person decides what to do next | Pass |
| **Double click** on a submit button | One request; the button is disabled while it runs | Pass |

**Proof that the tests can fail:** making changes retry once, or making 404 reads retry, turns the notification tests red. The code was restored afterwards.

**Also in this ticket:**
- `testing/scripts/check_no_raw_html.py` refuses `dangerouslySetInnerHTML`, `.innerHTML`, `.outerHTML`, `insertAdjacentHTML`, `document.write` and `createContextualFragment` in `frontend/src`. It has 13 tooling tests.
- `run.py lint` now also runs Prettier and that check.
- The Prettier config lives in `frontend/.prettierrc.json`. It is passed explicitly, so the same rules apply to `testing/frontend`, also inside the CI image.
- The frontend test setup starts an MSW server that fails on any request no handler covers, and clears storage between tests.

**Known local issue:** on the Windows host, Vitest sometimes stops with "failed to find the runner" before running any test. The same code passes on the next run, and clearing `node_modules/.vite` helps. It never happened in the `ci` container (Linux), where the suite passed 3 times out of 3. The `ci` container is the reference run.

**Totals:** 54 new tests: 41 frontend tests (7 shell, 12 API client, 4 form problems, 9 notifications, 9 reviewer name) and 13 tooling tests. The `ci` container passes:
- ruff, mypy, 5 contracts, tsc, Prettier, the raw-HTML check and the no-comments check;
- 33 tooling tests;
- 500 backend tests, with 100% coverage of the domain and catalog application code;
- 47 frontend tests and the smoke checks against the rebuilt frontend container.

## Test plan

- Vitest, React Testing Library and MSW specs in `testing/frontend` for each criterion and each row of "Failure cases and retries".

## Business view

- **What was built:** the frame of the website. It has a header with "Shop" and "Admin", a page for each area, a "Page not found" page, and the "Who is reviewing?" prompt that remembers your name. Under the surface, there is one consistent way to talk to the API and to show its errors.
- **Why:** every screen from now on (admin products in ECOM-007, shop search in ECOM-008, import, checkout) is built on this frame. Errors will look the same everywhere, and every change will carry your name.
- **Main goal:** a reliable base. Clear errors, no automatic repeat of a change, and no change without a name.
- **Human testable or background:** **partly testable** in the browser at http://localhost:3000. The pages and the name prompt can be tried by hand. The error messages on forms will be visible from ECOM-007, when the first form talks to the API; for now the tests prove them.
- **What to test:** see the steps in prompt #015 of the prompt history.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
