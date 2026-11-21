# ECOM-017: README and delivery

| Field | Value |
|---|---|
| Type | Technical task |
| Phase | 6 |
| Status | **Backlog** |
| Depends on | ECOM-016 |
| Architecture | §12 (Phase 6), CC-04, CC-09 to CC-12 |

## Context

The reviewers judge the delivery by the README, the decisions and how AI was used.

## Scope

- README: overview, CSV download date (2026-11-20), how to run with compose or natively, architecture summary, decisions and alternatives, questions for the business (§11.3), known gaps, how AI was used (linking `docs/PROMPT_HISTORY.md`).
- A final no-comments sweep and a journal completeness check.
- Push to `github.com/Ortiz-100323/E-commerce` once the owner approves.

## Acceptance criteria

1. A reviewer can run the project from the README alone on a clean machine.
2. Every challenge rule CC-01 to CC-13 is traceable to where it is met.
3. The repository is pushed under the `Ortiz-100323` account.

## Test plan

- A fresh clone, followed by the README steps, ends with `ci` exiting 0.

## Definition of done

- Acceptance criteria pass.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
