# ADR-0024: Browser tests with Playwright, in their own compose service

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-22 |
| Journal | D-101, D-102, D-104 |

## Context

Component tests use a fake API. Only a real browser against the real stack proves that buying, importing and logging in work end to end, on a desktop and a phone. But `docker compose up` shouldn't download a browser.

## Decision

- **Playwright 1.65.0, Chromium only,** in `testing/e2e`, with its own lockfile.
- **A separate `e2e` service under the `e2e` profile.**
  - `docker compose up` never builds or starts it.
  - It runs with `docker compose --profile e2e run --rm --build e2e`.
- **Only Chromium's headless shell is installed,** into a cached folder, so it is downloaded once. GitHub Actions caches it by lockfile.
- **Two projects:** desktop, and a phone (Pixel 7).
- **Test data is isolated:**
  - each run creates its own products with an `E2E-<run>-` SKU prefix, buys only those, and archives them at the end;
  - the owner's catalog is never touched.
- **The container doesn't run as root.**

## Alternatives discarded

- **Playwright inside the `ci` image:** a much bigger image that every `docker compose up` would build.
- **The official Playwright image with every browser:** larger, and only Chromium is needed.
- **A separate database for browser tests:** the point is to prove the real stack, and unique SKUs already keep data apart.

## Consequences

- At delivery: 44 tests pass, and 5 are skipped by design (they run on one device only).
- Writing them found a real bug: the checkout key needed a secure context, so it failed on plain HTTP addresses other than localhost (D-102).
- Each full run leaves one test admin and two test customers behind, because accounts can't be removed.
