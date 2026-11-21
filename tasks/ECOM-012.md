# ECOM-012: CSV import UI: upload and review screen

| Field | Value |
|---|---|
| Type | Story (frontend) |
| Phase | 3 |
| Status | **Backlog** |
| Depends on | ECOM-011, ECOM-006 |
| Architecture | §5 (import screens), CC-03 |

## Context

The reviewer needs a screen to see every row's outcome, fix flagged rows and commit.

## Scope

- `/admin/imports/new`: upload a CSV.
- `/admin/imports/:id`: one tab per outcome; an inline editor with confirm and skip for review rows; an old → new diff with a confirm checkbox and "confirm all" for update rows; reasons for rejected rows; the warnings list.
- The commit button stays disabled until the batch can be committed.

## Acceptance criteria

1. Uploading the sample shows the expected counts per tab.
2. Correcting a review row re-validates it and moves it to the right tab.
3. Commit enables only when nothing is left to resolve, and a 409 is explained to the user.

## Test plan

- Component specs with MSW for each criterion.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
