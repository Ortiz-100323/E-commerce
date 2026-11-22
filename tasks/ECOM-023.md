# ECOM-023: README about the system, and decision records

| Field | Value |
|---|---|
| Type | Documentation |
| Phase | Hand-in |
| Status | **In review**: built and verified (prompt #059), committed on the owner's word (prompt #060); the owner reviews the README at the end |
| Depends on | ECOM-022 |
| Journal | D-122, D-123, D-125 |

## Context

The README is about the system, written in plain, direct English. It is not a narrative (that's what the journal and prompt history are for). The decisions get their own records in `docs/adr`, so the README stays short and links to them.

## Scope

- **README.md, focused on the system.** It covers these sections, in this order:
  1. what was built;
  2. quick start with Docker;
  3. running without Docker;
  4. running the tests;
  5. the sample CSV and the date it was downloaded (2026-11-20);
  6. architecture;
  7. decisions and the alternatives discarded (a short table linking each ADR);
  8. out of scope;
  9. next steps;
  10. how AI was used.
- **docs/adr/:** one record per real decision, built from `docs/JOURNAL.md`.
  - Each record has: Status, Date, Context, Decision, Alternatives discarded, Consequences, and the journal entries it comes from.
  - A superseded decision that was once in force gets its own record, marked "Superseded by ADR-NNNN".
  - There is an index at `docs/adr/README.md`.
  - Housekeeping entries (merges, renumbering, test fixes) don't become ADRs.
- The detail lives in the ADRs and `docs/TECHNICAL_ARCHITECTURE.md`, so the README can be read in a few minutes.

## Acceptance criteria

1. Every section listed in the scope is in the README.
2. Every command in the quick start, running without Docker and the tests sections has been run as written.
3. Every ADR is linked from the README's decisions table and from the index. Every ADR cites at least one journal entry, and every relative link in the README and the ADRs resolves.
4. The README describes the system in plain English, with no narrative and no marketing tone.

## Test plan

- **A tooling test** (in `testing/tooling`) checks:
  - every relative link in `README.md` and `docs/adr/*.md` resolves;
  - every ADR is in the index and linked from the README;
  - every ADR has the required sections and cites a `D-` entry that exists.
- The commands are proven by the ECOM-022 fresh-clone run and by running them natively on Windows.

## As built and verified (2026-11-22, prompts #058 and #059, D-125)

- **README.md:** rewritten about the system, in the ten sections.
- **docs/adr/:** 30 records and an index.
  - One record is superseded: ADR-0027, replaced by ADR-0028.
  - Each record cites the journal entries it comes from.
- **The docs check is a script, not a tooling test.** The `ci` image doesn't contain `docs/` or the README, so the check can't run there.
  - `testing/scripts/check_docs.py` runs on the host as `python testing/run.py docs`, and in GitHub Actions.
  - Its 19 tests run in `testing/tooling` on temporary files.
- **D-125:** proving the commands found that running without Docker failed on Windows. It was fixed with `python -m ecommerce.serve`, and the seed now runs on a compatible event loop, with 11 new tests.

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | Every section in the scope is in the README | **Pass** | `run.py docs` checks all ten headings |
| 2 | Every command in the quick start, running without Docker and the tests sections was run as written | **Pass** | Docker: the ECOM-022 fresh clone, plus the rebuilt stack after the D-125 fix (`ci` exit 0, browser tests 44 passed and 5 skipped). Without Docker, on Windows: migrations, seed, `ecommerce.serve`, Vite and `run.py all` |
| 3 | Every ADR is linked from the README and the index, cites real journal entries, and every link resolves | **Pass** | `run.py docs`, including links to headings |
| 4 | The README describes the system in plain English | **For the owner's review** | — |

## Definition of done

- Acceptance criteria pass, and the owner has accepted the README.
