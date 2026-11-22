# ADR-0025: No comments in the code, enforced by a check

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-019 |

## Context

The challenge allows AI but asks for comments to be removed from the code. A manual review can miss one, and new comments can creep in later.

## Decision

- **`testing/scripts/check_no_comments.py` tokenizes Python, TypeScript and TSX.**
  - It fails on any comment.
  - Docstrings count as comments.
- **It runs as `python testing/run.py nocomments`,** in the `ci` container and in GitHub Actions, over:
  - `backend/src` and `backend/migrations`;
  - `frontend/src` and `frontend/vite.config.ts`;
  - `testing/`.
- **Explanations live in `docs/` and the README,** not in the code.

## Alternatives discarded

- **Manual review only:** error-prone.
- **A linter rule:** ruff has no rule that bans every comment, and the frontend has no ESLint ([ADR-0026](0026-raw-html-check-instead-of-eslint.md)).

## Consequences

- Names and small functions carry the meaning that comments would otherwise carry.
- The check has its own tooling tests, so it can't silently stop working.
