# ECOM-024: Requirements checklist against the code challenge

| Field | Value |
|---|---|
| Type | Verification |
| Phase | Hand-in |
| Status | **Planned**: waiting for the owner's approval (prompt #055) |
| Depends on | ECOM-022, ECOM-023 |
| Journal | D-122 |

## Context

The owner wants proof that nothing in the challenge document was missed.

## Scope

- **docs/REQUIREMENTS_CHECK.md:** one row per requirement in the challenge document, in the document's order. Each row has the requirement in the document's words, where it is met (a file, a test or a screen) and a status: Done, Partial or Missing.
- The rows include:
  - the local database;
  - product CRUD;
  - the CSV import;
  - search;
  - the purchase with fake payment;
  - the UI for all three;
  - running in Docker;
  - the README content;
  - the CSV download date;
  - local run instructions;
  - no AI comments in the code;
  - the GitHub repository.
- **The no-comments check is extended:** CSS, Dockerfiles, compose and CI YAML, nginx config, TOML and INI are covered, not only Python and TypeScript.
- **Anything Partial or Missing is reported to the owner before it is fixed.**

## Acceptance criteria

1. Every requirement sentence in the challenge document has a row.
2. Every "where it's met" reference exists. A tooling test checks that the file paths and test names resolve.
3. Every row is Done, or the owner has accepted the gap in writing.

## Definition of done

- The checklist is published and linked from the README.
- The owner has accepted it.
