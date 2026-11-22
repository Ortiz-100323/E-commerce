# ECOM-016: Hardening, Playwright E2E and GitHub Actions

| Field | Value |
|---|---|
| Type | Technical task |
| Phase | 5 |
| Status | **In Progress**: plan waiting for the owner's review (prompt #034) |
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

## Found while planning: DEF-01, uploads over 1 MB are refused by the portal (D-100)

nginx's default `client_max_body_size` is 1 MB, but the import accepts files up to 5 MB.
- A 1.5 MB CSV sent through http://localhost:3000 got nginx's HTML "413 Request Entity Too Large".
- The same file sent straight to the backend got 200.
- The sample (9 KB) never reaches the limit, so no test noticed.

The fix belongs to this ticket's "upload limits" scope:
- `client_max_body_size 6m` on `/api/`;
- nginx's own 413, for anything bigger, answered as `application/problem+json` (`payload-too-large`), like the backend's;
- a smoke check that uploads a 2 MB preview through the website.

## Plan (D-101, proposed)

### 1. Browser end-to-end tests (Playwright)

- **New package, needs your approval:** `@playwright/test` **1.65.0** (published 2026-11-05, the newest version at least two weeks old), with Chromium only. It lives in `testing/e2e/` with its own `package.json` and lockfile, so the frontend's dependencies don't change. The `ci` image installs it with Chromium, which adds about 400 MB to the test image only; the app images don't change.
- **`run.py e2e`** runs the specs against `http://frontend`. `run.py all` runs them after the smoke test.
- **Your data stays untouched.** Each run creates its own products with a unique SKU prefix (`E2E-<run>-…`) from a small generated CSV. It buys only those products and archives them at the end, like the smoke test's `SMOKE-TEST`. Orders made by the tests use the customer name "E2E test".
- **Specs:**
  1. **The full journey (AC1):** upload the CSV, resolve its review row, commit; search for the new product in the shop; add to cart, pay with 4242; the confirmation shows; the product's stock dropped by the quantity bought; its history shows "Stock decreased" by "Shop checkout".
  2. **Declined card (AC2):** pay with 4000 0000 0000 0002; the declined message shows; the stock is unchanged.
  3. **Double click on Pay:** exactly one order (the stock drops once).
- On failure, the trace and screenshots are saved to `testing/e2e/results/` (git-ignored) and uploaded by GitHub Actions.

### 2. Web server hardening (nginx)

- **Security headers on every response, including the API proxy and errors:**
  - `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`;
  - `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`;
  - `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()`;
  - `Cross-Origin-Opener-Policy: same-origin`;
  - `server_tokens off`.

  They go in one included file, because nginx drops server-level `add_header` in any location that sets its own (our cache headers).
- **No HSTS:** the stack runs on plain HTTP locally. The README will say a real deployment needs HTTPS (this is also OBS-08, card autofill).
- **Upload limits:** see DEF-01.

### 3. Containers

- **Non-root everywhere (AC4):**
  - **frontend:** switch to `nginxinc/nginx-unprivileged:1.28-alpine`, which listens on 8080 inside the container. The host port stays 3000.
  - **backend:** already runs as `app`.
  - **db:** the PostgreSQL server process runs as `postgres`.
  - **ci:** a new `runner` user.
  - **A check:** a host-side script (`run.py containers`) asks Docker which user each running container's main process uses, and fails on root.
- **Healthchecks:** db, backend and frontend already have one. The backend's switches from `curl` to Python's standard library, so `curl` can leave the image.
- **Image size check:** `run.py images` fails if an image grows past its budget. Today the frontend is 93 MB and the backend 505 MB. Proposed budgets: frontend 120 MB, backend 500 MB, after dropping `curl` and the apt lists.
- **Logs:** request IDs and JSON logs already exist (ECOM-001). A test proves a checkout's log lines carry the request ID and no card data.

### 4. GitHub Actions (AC5)

- **`.github/workflows/ci.yml`** runs on push and pull request:
  1. check out the code;
  2. `docker compose up -d --build --wait db backend frontend`;
  3. `docker compose run --rm ci`;
  4. `run.py images` and `run.py containers`;
  5. upload the Playwright results if anything fails.

  Every action is pinned to a full commit SHA, and the workflow has read-only permissions.
- **This needs the code on GitHub.** `github.com/Ortiz-100323/E-commerce` is **public** and still empty. Pushing publishes every commit, including the test screenshots. Three of them (ECOM-015 evidence 03, 04 and 05) show your full name and email, and the ECOM-012 ones show your name.

## Failure cases and retries (D-072)

| Situation | Expected | Planned result |
|---|---|---|
| A CSV between 1 and 5 MB through the portal | Accepted, like the backend | — |
| A body over 6 MB through the portal | 413 `payload-too-large` as problem+json, not nginx's HTML | — |
| An E2E run stopped halfway | Its products have a unique prefix; the next run doesn't depend on them, and they can be archived by prefix | — |
| **Retry:** the E2E suite run twice | Passes both times; each run uses new SKUs | — |
| **Stock:** the journey checks the exact stock before and after; the declined spec checks it doesn't change | — | — |

## Business view (planned)

- **What will be built:** the safety checks before delivery.
  - Real-browser tests that walk the whole journey, from import to purchase.
  - A safer web server: security headers, and the upload limit the app promises.
  - Containers that never run as the administrator user.
  - Automatic checks on GitHub for every change.
- **Why:** CC-08 (runs in Docker) and CC-13 (enterprise-grade). Reviewers see the same green run on GitHub that we see locally.
- **Main goal:** proof, on every change, that a shopper and an admin can do everything end to end.
- **Human testable or background:** mostly background. You can watch the browser tests and the GitHub run; the headers can be seen in the browser's developer tools.

## Test plan

- The Playwright specs, plus a header check in the smoke test.

## Definition of done

- Acceptance criteria pass.
- `run.py all` is green locally and in GitHub Actions.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
