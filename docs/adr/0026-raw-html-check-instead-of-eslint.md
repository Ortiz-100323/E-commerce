# ADR-0026: A raw-HTML check instead of ESLint, while TypeScript 7 has no ESLint support

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-076, D-077 |

## Context

The frontend plan included ESLint with `react/no-danger`, as an XSS guard. The project uses TypeScript 7, the native compiler. The newest `typescript-eslint` supported TypeScript below 6.1 only, so without a parser ESLint can't read any `.ts` or `.tsx` file.

## Decision

- **ESLint is not installed for now.** Forcing unsupported peer dependencies would likely break.
- **`testing/scripts/check_no_raw_html.py`** refuses these in `frontend/src`:
  - `dangerouslySetInnerHTML`;
  - `.innerHTML` and `.outerHTML`;
  - `insertAdjacentHTML`;
  - `document.write`;
  - `createContextualFragment`.

  It runs in `run.py lint`, with its own tooling tests.
- **Prettier checks the format, and `tsc --noEmit` in strict mode checks the types.**
- **This is revisited** when `typescript-eslint` supports TypeScript 7.

## Alternatives discarded

- **Downgrading to TypeScript 5.9:** a project-wide change for a linter.
- **Forcing the peer dependencies:** unsupported.
- **The Babel parser or oxlint:** new packages that weren't approved.

## Consequences

- The XSS guard ESLint would have given is kept. React also escapes output, and product names refuse markup.
- The React hooks rules and general lint rules are missing until ESLint returns. Code reviews and tests cover them meanwhile.
