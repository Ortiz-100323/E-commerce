# Task board

This folder simulates a Jira project. Each ticket is one Markdown file, named after its key. A ticket has these sections: context, scope, acceptance criteria, test plan, definition of done and status. Before it is built, it also gets a "Failure cases and retries" section: what can go wrong and what the caller gets back, what happens on a retry, and, if it touches stock, proof that we never sell what we don't have (D-072). When it is delivered, it also gets a business view: what was built, why, the main goal, whether a person can test it or it runs in the background, and what to test (D-067).

**Test evidence.** Screenshots and recordings from the owner's tests are kept in `tasks/<KEY>-evidence/`. Each folder has a `README.md` written like a Jira test record: the environment, each step with its expected and actual result, the defects with their cause, fix and status, the observations, and a re-test checklist (D-082).

- **ECOM-000** sets up the environment: a walking skeleton that proves the whole stack runs end to end in local containers.
- **ECOM-001 onwards** build the e-commerce application, following [TECHNICAL_ARCHITECTURE.md](../docs/TECHNICAL_ARCHITECTURE.md).

## Status values

| Status | Meaning |
|---|---|
| Backlog | Written, not yet planned for work |
| To Do | Planned and ready to start |
| In Progress | Being built |
| In Review | Built and tested, waiting for the owner's review |
| Done | Accepted by the owner |

A ticket moves to **Done** only after the owner accepts it at its review gate.

## Board

| Key | Title | Phase | Depends on | Status |
|---|---|---|---|---|
| [ECOM-000](ECOM-000.md) | Walking skeleton: four containers, weather test feature, local CI | 0 | — | Done |
| [ECOM-001](ECOM-001.md) | Backend foundation: shared kernel, Problem Details errors, quality gates | 1 | ECOM-000 | Done |
| [ECOM-002](ECOM-002.md) | Catalog domain: value objects and the Product aggregate | 1 | ECOM-001 | Done |
| [ECOM-003](ECOM-003.md) | Catalog persistence: schema, repository and Unit of Work | 1 | ECOM-002 | Done |
| [ECOM-004](ECOM-004.md) | Audit trail: append-only log and product history | 1 | ECOM-003 | Done |
| [ECOM-005](ECOM-005.md) | Product CRUD and search API | 1 | ECOM-004 | Done |
| [ECOM-006](ECOM-006.md) | Frontend foundation: API client, routing, server state, actor prompt | 2 | ECOM-005 | Done |
| [ECOM-007](ECOM-007.md) | Admin product UI: table, form, gift dialog, history | 2 | ECOM-006 | Done |
| [ECOM-008](ECOM-008.md) | Storefront search UI | 2 | ECOM-006 | Done |
| [ECOM-009](ECOM-009.md) | Remove the temporary weather feature | 2 | ECOM-007, ECOM-008 | Backlog |
| [ECOM-010](ECOM-010.md) | CSV import: parsing, classification and policies | 3 | ECOM-005 | Backlog |
| [ECOM-011](ECOM-011.md) | CSV import: review workflow, commit and audit | 3 | ECOM-010 | Backlog |
| [ECOM-012](ECOM-012.md) | CSV import UI: upload and review screen | 3 | ECOM-011, ECOM-006 | Backlog |
| [ECOM-013](ECOM-013.md) | Ordering: Order aggregate, fake payment and checkout | 4 | ECOM-005 | Backlog |
| [ECOM-014](ECOM-014.md) | Checkout safety: idempotency key and stock locking | 4 | ECOM-013 | Backlog |
| [ECOM-015](ECOM-015.md) | Purchase UI: cart, checkout and confirmation | 4 | ECOM-014, ECOM-006 | Backlog |
| [ECOM-016](ECOM-016.md) | Hardening, Playwright E2E and GitHub Actions | 5 | ECOM-012, ECOM-015 | Backlog |
| [ECOM-017](ECOM-017.md) | README and delivery | 6 | ECOM-016 | Backlog |
| [ECOM-018](ECOM-018.md) | UI polish and user experience (from the owner's ECOM-007 test) | 5 | ECOM-007, ECOM-008 | Backlog |
