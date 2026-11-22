# ECOM-016: Hardening, Playwright E2E and GitHub Actions

| Field | Value |
|---|---|
| Type | Technical task |
| Phase | 5 |
| Status | **In Review**: built (prompt #035); GitHub Actions green on pull request #1 (prompt #036); waiting for the owner to accept and merge |
| Depends on | ECOM-012, ECOM-015 |
| Architecture | §8.1 (E2E), §10, CC-08 |
| Journal | D-100, D-101, D-102, D-103, D-104 |

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

## Plan (D-101, accepted with changes; see "As built")

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

## As built (D-102, D-103, D-104)

The owner accepted the plan with changes (prompt #035). Where this section and the plan above differ, this section is what was built.

- **Browser tests:**
  - `testing/e2e`, with `@playwright/test` 1.65.0 pinned, run in their own `e2e` compose service under the `e2e` profile: `docker compose --profile e2e run --rm --build e2e`. They are not part of `run.py all`, and `docker compose up` never starts them.
  - Only the Chromium headless shell is installed, into the git-ignored `.cache/ms-playwright`, which CI caches.
  - The service runs as a normal user (`E2E_UID`/`E2E_GID`, default 1000).
  - Specs: the full journey (CSV import with a gift row to confirm → commit → shop search → cart → pay → stock down), a declined card, and a double click on Pay. Each run uses its own `E2E-<run>-` products and archives them afterwards.
- **nginx:**
  - the headers and CSP of the plan, from one included file, also on nginx's own error answers;
  - `server_tokens off`; `client_max_body_size 6m` on `/api/`;
  - nginx's own 413 answered as `application/problem+json`.

  It still uses the official `nginx:1.28-alpine`, configured to run as `nginx` on port 8080: the newest `nginx-unprivileged` tag was a version behind (1.28.2), so no new image was added.
- **Containers:**
  - backend health check is now `python -m ecommerce.healthcheck` (standard library), so `curl` left the image (505 → 487 MB);
  - the `ci` image runs as `runner`, with files copied in already owned by it;
  - `run.py containers` and `run.py images` run on the host (and in GitHub Actions) and ask Docker directly.
- **Checkout:** the idempotency key now also works over plain HTTP (DEF-02, D-102).
- **GitHub Actions:** `.github/workflows/ci.yml`.
  - Steps: compose up → `ci` container → container users → image budgets → browser cache → browser tests → results uploaded on failure.
  - Actions are pinned to commit SHAs, and the workflow has read-only permissions.
- **Screenshots:** the owner's name and email were pixelated in every commit before the first push (D-103), with `testing/scripts/redact_images.py`.

## Found while building: DEF-02, the checkout needs a secure context (D-102)

`crypto.randomUUID()` exists only on HTTPS or `localhost`. Over `http://frontend:8080`, as in the browser tests, or any plain-HTTP server name, Pay would have failed. The key now falls back to `crypto.getRandomValues`.

## Failure cases and retries (results)

| Situation | Result |
|---|---|
| A CSV between 1 and 5 MB through the portal | Pass: live smoke check (a 2 MB CSV gets 200; before the fix it failed) |
| A body over 6 MB through the portal | Pass: 413 `payload-too-large` as problem+json (live smoke check) |
| An E2E run stopped halfway | Pass: its products carry a unique prefix; every run uses new SKUs and archives its own |
| **Retry:** the E2E suite run twice | Pass: run twice in a row, both green |
| **Stock:** the journey checks exact stock before and after; a declined card and a double click are checked too | Pass |

## Verification (2026-11-22)

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | Playwright passes: import → review → commit → search → buy → stock decreases | **Pass** | Real browser against the running stack: the CSV is uploaded, the gift row is confirmed, the import commits "2 created", the lamp is found by search, 2 are bought for $25.00, and its stock goes 5 → 3 |
| 2 | Playwright passes: a declined card leaves stock unchanged | **Pass** | The declined message shows, the card field is cleared, and the stock stays at 5. A third test proves a double click buys once (5 → 4) |
| 3 | Responses carry the security headers and CSP | **Pass** | Live smoke check on `/`, `/cart`, an API answer and an API error: all six headers with exact values |
| 4 | Every container runs as a non-root user | **Pass** | `run.py containers`: backend uid 999, database uid 70, web server uid 101. The browser tests run as uid 1000 and the `ci` container as `runner` |
| 5 | The GitHub Actions run gives the same result as the local `ci` container | **Pass** | [Run 45022442937](https://github.com/Ortiz-100323/E-commerce/actions/runs/45022442937) on pull request #1, 2 min 20 s: 8 contracts kept, 60 tooling, 869 backend (99.62%), 136 frontend tests, every smoke check, no root process (999, 70, 101), images within budget, 3 browser tests passed; the same numbers as the local run. The browser cache was empty on that first run and was saved for the next ones. |

**Totals:** 3 browser tests, 3 new live smoke checks, 10 new tooling tests, 3 backend and 2 frontend tests. Locally, the `ci` container passes all static checks, 60 tooling tests, 869 backend tests (99.62% coverage), 136 frontend tests (95.85% lines) and 11 smoke checks. `run.py containers` and `run.py images` pass.

## Business view

- **What was built:** the safety checks before delivery.
  - A real browser now walks the whole journey, from importing a file to buying a product, and checks the stock.
  - The web server sends security headers and accepts uploads up to the promised 5 MB.
  - No container runs as the administrator.
  - The same checks are ready to run on GitHub for every change.
- **Why:** CC-08 (runs in Docker) and CC-13 (enterprise-grade). The reviewers will see the checks pass on GitHub.
- **Main goal:** proof, on every change, that a shopper and an admin can do everything end to end.
- **Human testable or background:** mostly background. You can run the browser tests yourself, and see the headers in the browser's developer tools (F12 → Network).
- **What to test:** see prompt #035 of the prompt history.

## Test plan

- The Playwright specs, plus a header check in the smoke test.

## Definition of done

- Acceptance criteria pass.
- `run.py all` is green locally and in GitHub Actions.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
