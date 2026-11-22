# ADR-0023: Test-first, with every test under `testing/` and one runner for local runs and CI

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-004, D-006, D-024, D-055, D-066, D-070, D-072, D-085, D-086 |

## Context

Test-driven development was a hard rule from the start. Tests and helper scripts shouldn't be scattered around the project, and a check run on a laptop must behave exactly like the same check in CI.

## Decision

- **Every behaviour starts with a failing test.** Every ticket also tests:
  - each failure and the answer it produces;
  - what a retry does (no duplicate, no double sale, no double audit entry);
  - that stock never goes below zero, including under concurrent requests.
- **All tests and scripts live in `testing/`:** `backend/`, `frontend/`, `e2e/`, `tooling/`, `fixtures/` and `scripts/`. Application code is the only code outside it.
- **`testing/run.py` is the single entry point,** built on the standard library only. Its subcommands are `lint`, `nocomments`, `tooling`, `backend`, `frontend`, `smoke`, `all`, `containers`, `images`, `docs` and `script <name>`.
- **The `ci` container runs `run.py all`** against the running stack. GitHub Actions starts the same stack and runs the same container, so local runs and CI behave the same.
- **Quality gates:**
  - ruff, `mypy --strict`, import-linter, the TypeScript check and Prettier;
  - 95% coverage of the domain and application code (hypothesis property tests included);
  - 80% coverage of the frontend;
  - every frontend test also fails if the page shows an unexpected error or a red notification it didn't expect.

## Alternatives discarded

- **Tests next to the code (`backend/tests`, `*.test.tsx`):** the conventional layout, but the owner wanted one place.
- **A Makefile:** no `make` on Windows by default.
- **npm scripts:** they would make the Python tooling depend on Node.
- **nox or tox:** an extra dependency for what a small script does.
- **Tests on the host only:** they don't prove the containers work together.

## Consequences

- Vitest resolves packages from `frontend/node_modules` for specs that sit outside `frontend/`. A small Vite plugin handles that.
- At delivery: 79 tooling, 1,099 backend (99%) and 204 frontend tests (96%), plus 14 smoke checks.
