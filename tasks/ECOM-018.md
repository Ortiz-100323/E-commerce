# ECOM-018: UI polish and user experience

| Field | Value |
|---|---|
| Type | Story (frontend) |
| Phase | 5 (with hardening), or earlier if the owner prefers |
| Status | **Backlog** |
| Depends on | ECOM-007, ECOM-008, ECOM-012 |
| Architecture | §5, CC-07 |
| Source | Owner's test of ECOM-007 ([evidence](ECOM-007-evidence/README.md)), prompt #017 |

## Context

The owner's browser test of ECOM-007 showed that the screens work, but some parts feel rough. The owner asked to focus on a better user experience when the UI gets its own attention.

## Scope (collected so far)

- **Drop-downs:** a styled status filter and category picker, replacing the browser defaults, with no light-blue autofill on the Category field (OBS-01).
- **Responsive table:** SKUs never wrap, the actions are always visible (a compact actions menu on narrow screens), and the table scrolls inside its own box instead of cutting off buttons (OBS-02).
- **Notifications:** success messages close by themselves after a few seconds, and notifications never cover the main actions (OBS-02).
- **"A new version is available — reload":** a long-open tab notices when the site was updated (for example by checking the page's version every few minutes) and asks the admin to reload. That prevents testing old code by accident, as in DEF-02 (D-084).
- **Duplicate SKU, show the existing product:** "SKU RS-001 is already taken by **Running Shoes**", with links to view or edit it (OBS-03). The frontend can find it with `GET /products?q=RS-001&status=ALL`; alternatively the API's `duplicate-sku` problem could carry the existing product's id and name.
- **Import screens** (owner's portal test of ECOM-010 to ECOM-012, prompt #028, [evidence](ECOM-012-evidence/README.md)): "We need to improve user experience but the functionality is great."
  - Disabled buttons that look clearly disabled (OBS-01).
  - Long values readable in the row editor, for example a wider Description field or a text area (OBS-02).
  - Spaces made visible in the raw CSV line, so "the name is empty" is obvious for a name made only of spaces (OBS-03).
  - A short read-only summary for rows of a finished import, instead of disabled editors (OBS-04).
  - "line 2" rather than "line(s) 2" (OBS-05).
  - A commit bar that stays in view on long lists, and focus moved to the next row after a decision (OBS-06).

## Acceptance criteria

To be written when the ticket is planned. The scope above lists the starting points.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
