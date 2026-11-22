# ECOM-018: UI polish and user experience, starting with the shop's product card

| Field | Value |
|---|---|
| Type | Story (frontend, with a small backend change for product images) |
| Phase | 5 |
| Status | **Done**: part A accepted (prompt #042) and part B accepted (prompt #045); committed on `feature/ECOM-018-ui-polish`. The pull request into `main` is opened when the owner asks |
| Priority | First after ECOM-016 (owner's order, prompt #037: ECOM-018 → ECOM-019 → ECOM-020 → ECOM-017) |
| Depends on | ECOM-007, ECOM-008, ECOM-012, ECOM-015 |
| Architecture | §4.2 (`Product`), §4.5, §5, §10 (CSP), CC-07 |
| Journal | D-106, D-109, D-110 (code review round 4), D-111, D-112 |
| Evidence | [Playwright on desktop and mobile](ECOM-018-evidence/README.md) |
| Source | Owner's tests of ECOM-007 (prompt #017), ECOM-012 (prompt #028) and ECOM-015 (prompt #034); the product card request (prompt #037) |

## Context

The screens work, but some parts feel rough. The owner collected UX remarks here while testing (D-082). In prompt #037 they asked for a real store card in the shop, as the first piece of this ticket:

> Today it only shows name, category and price, and to buy anything I have to open the product. I want it to feel like a real store card.

## Scope

### Part A: the shop's product card (owner's request, prompt #037), delivered and reviewed first

1. **Image area on top, 4:3.**
   - When the product has an image URL, the card shows the image (`object-fit: cover`, lazy loading).
   - Otherwise it shows a clean placeholder: a soft tint of the category's colour and a simple icon for the category.
   - A broken image falls back to the placeholder. The 4:3 box is reserved before the image loads, so nothing jumps.
2. **Text:** the name (at most two lines; the full name appears on hover and on the product page), the category in smaller, softer text, and the price highlighted ("Free" for gifts).
3. **Stock badges:** "Only N left" when 1 to 5 are left; "Out of stock" at 0, with the button disabled.
4. **"Add to cart" on the card.** It uses the same cart rules as the product page: never more than the stock shown.
   - The button confirms "Added" for a moment, and screen readers hear "Running Shoes added to cart (2 in your cart)".
   - At the stock limit, the button is disabled and says why.
5. **The rest of the card opens the product page.** The name is a real link stretched over the card, so there are no nested buttons and links.
6. **Hover:** the card lifts a little, with a soft shadow. Nothing moves for visitors who ask their system to reduce motion.
7. **Equal heights:** every card in the grid is the same height, with the button aligned at the bottom.
8. **Keyboard:** Tab reaches the card link (with a visible focus ring around the whole card), then its button. Enter opens the product, and Enter or Space adds it to the cart.
9. **Mobile:** two columns on a phone, full-width buttons, touch targets at least 44 px, and no hover effects on touch screens.
10. **Telling look-alikes apart:** every card shows its SKU in small text, so the two "Bluetooth Speaker" cards read "SKU BS-021" and "SKU BS-099". The card's accessible name includes the SKU too.

**Product images (the backend part of A):**
- `Product` gains an optional `image_url`: HTTPS only, at most 2,048 characters, checked by a value object.
- It is stored by migration 0009, returned by the API, settable in the admin form ("Image URL (optional)", with a preview), and recorded in the product's history like any other field.
- The CSV import doesn't change (its seven columns stay the same).
- The Content-Security-Policy gains `img-src https:`, so images can come from any HTTPS host.

### Part B: the polish collected so far, built after part A is accepted

- **Admin products:**
  - styled filters, and no light-blue autofill on Category (OBS-01, ECOM-007);
  - SKUs never wrap, the actions stay visible (a compact menu on narrow screens), and the table scrolls inside its own box (OBS-02, ECOM-007);
  - success messages close by themselves, and notifications never cover the main actions (OBS-02, ECOM-007);
  - "SKU RS-001 is already taken by **Running Shoes**", with links to view or edit it: the `duplicate-sku` problem gains the existing product's id and name (OBS-03, ECOM-007).
- **"A new version is available — reload":** the page compares its build id with the server's every few minutes and offers a reload (D-084).
- **Import screens** (ECOM-012 OBS-01 to OBS-06):
  - disabled buttons that look disabled;
  - a text area for long values;
  - visible spaces in the raw CSV line (`·`);
  - a read-only summary of a finished import's rows;
  - "line 2" instead of "line(s) 2";
  - a sticky commit bar, and focus moved to the next row after a decision.
- **Purchase screens** (ECOM-015 OBS-07, OBS-09, OBS-10):
  - flagged cart lines greyed out, and "Subtotal of available items";
  - "MM/YY" as the expiry placeholder;
  - − and + buttons for quantities.
  - OBS-08 (card autofill needs HTTPS) goes to the README in ECOM-017.

## Acceptance criteria

### Part A: product card

1. Each card shows a 4:3 image area: the product's image when it has an `image_url`, otherwise the category's colour and icon. A broken image shows the placeholder.
2. The name takes at most two lines, the category is smaller and softer, and the price stands out ("Free" for gifts).
3. "Only N left" appears for 1 to 5 in stock, and "Out of stock" at 0 with a disabled button.
4. **Add to cart** on the card adds one unit, updates the header's cart count, and never exceeds the stock.
5. Clicking anywhere on the card except the button opens the product page.
6. All cards in the grid have the same height on desktop and on mobile.
7. The card works with the keyboard alone: visible focus, Enter opens, Enter or Space adds to the cart.
8. Two products with the same name can be told apart on their cards (the SKU).
9. **Playwright checks 1 to 8 on desktop (1280 × 800) and on a phone (Pixel 7),** and the screenshots are attached to the evidence before the owner's review.
10. An admin can set and clear a product's image URL. Only HTTPS URLs are accepted, and the change appears in the product's history.

### Part B: polish

11. Each listed observation is fixed as described, with a test where behaviour changes. The owner re-checks the screens in the portal.

## Plan (D-106, accepted by the owner in prompt #038)
**The owner's decisions (prompt #038):** product images through an optional HTTPS-only image URL, with the CSP allowing HTTPS images; "Only N left" from 5 units down; no accessibility package (the keyboard and label checks are written in our own tests).

**Part A, test-first:**
1. **Backend:**
   - an `ImageUrl` value object (HTTPS, a host, at most 2,048 characters, no spaces or control characters);
   - `Product.image_url`, part of `revise`, so the change is audited;
   - migration 0009;
   - the API schemas gain `image_url`;
   - unit, repository, API and contract tests.
2. **CSP:** `img-src 'self' data: https:` in `frontend/security-headers.conf`, and in the smoke check.
3. **Frontend:**
   - a new `ProductCard`;
   - `ProductImage` (image or placeholder, with a fallback on error);
   - `categoryLook(category)`: a stable colour and icon per category. The colour comes from a palette of 8 accessible tints, chosen by a hash of the normalised category name. The icons are a small set of inline SVGs for the shop's categories (Electronics, Sports, Home & Office, Kitchen, Gifts, Books, Outdoors, Beauty, Games, Food & Beverage, Tools, Health, Clothing and Footwear, Pets, Stationery, Accessories), with a neutral box for anything else. No icon package is needed.
   - The admin form gains **Image URL (optional)** with a preview.
4. **Component tests (Vitest):** every rule of criteria 1 to 8.
5. **Playwright (`testing/e2e/specs/product-card.spec.ts`)** runs in two projects, **desktop** (1280 × 800) and **mobile** (Pixel 7), on the existing headless shell. It checks:
   - the 4:3 ratio, from the measured box;
   - at most two lines of name;
   - equal card heights;
   - the badges and the disabled button, using its own `E2E-` products, archived afterwards;
   - adding from the card;
   - clicking the card body;
   - Tab, Enter and Space;
   - and it saves the screenshots into `tasks/ECOM-018-evidence/`.

   Nothing is bought, so your stock doesn't change.

**Part B:** planned in detail once part A is accepted, one observation at a time, each with its test.

## Failure cases and retries (D-072)

| Situation | Expected | Planned result |
|---|---|---|
| An image URL that is not HTTPS, too long, or not a URL | 422 under **Image URL**; nothing saved | — |
| An image that fails to load | The placeholder, with no broken-image icon | — |
| A slow image | The 4:3 box keeps its place; nothing below it moves | — |
| A very long name | Two lines and an ellipsis; the full name on hover and on the product page | — |
| **Retry:** clicking **Add to cart** many times | Stops at the stock; the button says why | — |
| **Stock:** the card shows the stock from the list and never decides a sale | Checkout re-checks everything with the stock locked (ECOM-014) | — |

## Part A as built (2026-11-22)

- **Backend:**
  - `ImageUrl` value object: HTTPS only, a host, at most 2,048 characters, no spaces or control characters; the scheme is stored in lower case.
  - `Product.image_url`: in `create`, and in `revise`, where an empty value clears it and no value keeps it. It is part of the audit snapshot.
  - Migration 0009 adds the `image_url` column with the CHECK `ck_products_image_url_https`.
  - The API returns `image_url` and accepts it on create and update. An update without it clears it, because a PUT replaces every field.
- **CSP:** `img-src 'self' data: https:`, also checked by the smoke test.
- **Frontend:**
  - `ProductCard`;
  - `ProductImage` (photo, or a placeholder that also replaces a photo that fails to load);
  - `categoryLook` (a tint and an icon per kind of category);
  - `CategoryIcon` (inline SVG);
  - the card's colours come from 8 CSS classes, never from inline style attributes, so the CSP needs no exception;
  - the admin form gains **Image URL (optional)** with a preview.
- **Card behaviour:**
  - the name link is stretched over the whole card, and the button sits above it;
  - the grid uses `grid-auto-rows: 1fr`, with the button at the bottom of every card;
  - the hover lift only happens on devices that can hover and don't ask for reduced motion;
  - the card shows a focus frame when its link has keyboard focus;
  - a phone gets two columns.
- **Browser tests:** `testing/e2e/specs/product-card.spec.ts` runs in a **desktop** project (1280 × 800) and a **mobile** project (Pixel 7). The purchase tests run on desktop only.

### Verification (part A)

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | The 4:3 image area shows the photo or the category placeholder; a broken photo shows the placeholder | **Pass** | Component tests; Playwright measures 4:3 on every card on both devices, and checks a loaded photo and a broken one |
| 2 | Two lines of name, softer category, highlighted price ("Free" for gifts) | **Pass** | Component test; Playwright measures the long name at most two lines |
| 3 | "Only N left" (1 to 5) and "Out of stock" with a disabled button | **Pass** | Component and Playwright tests |
| 4 | **Add to cart** on the card, never past the stock | **Pass** | Component test ("All 1 in your cart"); Playwright ("All 2 in your cart") |
| 5 | Clicking anywhere except the button opens the product | **Pass** | Playwright clicks the image area and lands on the product page |
| 6 | Same height on desktop and mobile | **Pass** | Playwright: all six cards within 1 px, on both devices |
| 7 | Keyboard only | **Pass** | Component test and Playwright: Tab, Enter, Space, Shift+Tab, and the focus frame |
| 8 | Look-alikes told apart | **Pass** | SKU on every card, and in its accessible name ("Bluetooth Speaker SKU BS-099") |
| 9 | Playwright checks 1 to 8 on desktop and mobile, with screenshots | **Pass** | 19 tests; screenshots in [ECOM-018-evidence](ECOM-018-evidence/README.md) |
| 10 | An admin can set and clear an HTTPS image URL, and it appears in the history | **Pass** | Admin form tests; API tests on PostgreSQL (saved, shown in search, cleared, the history entry before and after); the domain refuses `http:`, `javascript:` and `data:` |

**Defect found by Playwright and fixed before review:** a photo that isn't 4:3 stretched its card (DEF-01 in the evidence).

### Failure cases and retries (results)

| Situation | Result |
|---|---|
| An image URL that is not HTTPS, too long, or not a URL | Pass: 422 under **Image URL** from the API; the form refuses it before sending |
| An image that fails to load | Pass: the placeholder, with no broken-image icon |
| A slow image | Pass: the 4:3 box keeps its place (the photo is positioned inside it) |
| A very long name | Pass: two lines and an ellipsis; the full name in `title` and on the product page |
| **Retry:** clicking **Add to cart** many times | Pass: stops at the stock, and the button says why |
| **Stock:** the card never decides a sale | Pass: checkout re-checks with the stock locked (ECOM-014) |

**Totals for part A:** 24 new backend tests, 13 new frontend tests (10 for the card and 3 for the admin image field), and 9 browser tests run on 2 devices. The `ci` container passes `run.py all`: all static checks, 60 tooling, 893 backend (99.62% coverage), 149 frontend tests, and the smoke checks. `run.py containers` and `run.py images` pass.

## Part A, round 2: one look for every screen (owner's review, prompt #041, D-109)

The owner found the interface "half styled": the card was designed, but the rest of the controls used the browser's defaults. The owner's five fixes, in order:

| # | Owner's request | As built |
|---|---|---|
| 1 | Style every button, input, dropdown and link the same way | Shared tokens and `:where()` base styles in `index.css`; one shared module `styles/controls.module.css` (`primary`, `secondary`, `quiet`, alerts), reused with `composes` by the shop, product page, cart, checkout, admin, imports, dialogs and the name prompt |
| 2 | Reorganise the filter bar; Sort next to the product count | One search panel: the search box and button, then Category, toggle chips and a Min–Max price range. The product count and Sort share a results bar above the grid. On phones the filters fold behind **Filters (N)** |
| 3 | Product page with a picture and two columns | The picture (photo or category placeholder) on the left; the name, price, stock label, Add to cart, description and details on the right. They stack on phones |
| 4 | Lighter cards: smaller buttons, stock labels, no SKU | A compact pill button beside the price; "In stock", "Only N left" or "Out of stock" as a dot label. The SKU is shown only when two products on the page share a name, so AC 8 still holds |
| 5 | Header, colour and empty states | A white sticky header with a wordmark, the active link underlined, and the cart as a pill with a count badge; a spruce brand colour; empty states for no results, an empty cart and a missing product |

### Acceptance criteria (round 2)

| # | Criterion | Result | How it was proven |
|---|---|---|---|
| R1 | Every button, field, dropdown and link uses the shared styles on every screen | **Pass** | Playwright screenshots of the shop, product page, cart, checkout, admin products, new product and import (evidence 05 to 18) |
| R2 | Sort sits next to the product count, outside the search panel; Category and Price are inside it | **Pass** | Component test "puts the sort next to the product count" |
| R3 | On a phone the filters fold behind a button that counts them, and open by themselves on a price error | **Pass** | Component tests; Playwright on the phone (hidden, then shown after a tap) and on the desktop (always shown) |
| R4 | The product page shows the picture beside the details on a desktop and above them on a phone | **Pass** | Playwright measures both layouts; component test for the placeholder, stock label and SKU |
| R5 | Cards show a stock label, a compact button on the price row, and no SKU unless names repeat | **Pass** | Component tests; Playwright (the tent has no SKU, the two speakers do) |
| R6 | Empty states explain what to do next | **Pass** | Component and Playwright tests for "No products match your search" with **Clear filters** |
| R7 | Everything from round 1 still holds (4:3, equal heights, keyboard, stock limit, 44 px touch targets) | **Pass** | All round 1 browser tests, on both devices |

**Totals for round 2:** 7 new component tests (156 frontend tests in all) and 4 new browser tests (26 passed, 3 skipped by design). `run.py all` passes in the `ci` container: the static checks, 60 tooling, 893 backend (99%), 156 frontend tests and the smoke checks. `run.py containers` and `run.py images` pass.

## Part B as built (2026-11-22, D-111)

| Source | Observation | As built |
|---|---|---|
| ECOM-007 OBS-01 | Drop-downs look off; Category turns light blue | All filters use the shared styles (D-109); autofilled fields stay white |
| ECOM-007 OBS-02 | SKUs wrap, actions cut off, notifications cover the table | SKUs never wrap; below 56 rem the actions open from an **Actions** button as a bottom panel; notifications sit bottom-left, and success messages close after 5 seconds |
| ECOM-007 OBS-03 | A duplicate SKU should show the existing product | "SKU RS-001 is already taken by Running Shoes.", with **View** and **Edit** links; the API's `duplicate-sku` problem gains `existing_product` |
| D-084 | A long-open tab runs old code | `version.json` with the build id, checked every 5 minutes and when the tab becomes visible; a **Reload** banner |
| ECOM-012 OBS-01 | Disabled buttons look active | Disabled buttons are grey, with a dashed border and a `not-allowed` cursor |
| ECOM-012 OBS-02 | Long values are cut off | Description is a text area across the full width |
| ECOM-012 OBS-03 | Invisible spaces in the raw line | Spaces show as `·`, with "· marks a space." |
| ECOM-012 OBS-04 | A finished import still shows editors | A read-only table for every tab once the import is committed, discarded or expired |
| ECOM-012 OBS-05 | "line(s) 2" | "line 2", or "lines 2 and 5" |
| ECOM-012 OBS-06 | Long lists: the commit bar scrolls away; no focus after a decision | The commit bar stays under the header; focus moves to the next row to review |
| ECOM-015 OBS-07 | $0.00 subtotal next to a flagged line | Flagged lines are greyed out with the total struck through; "Subtotal of available items" |
| ECOM-015 OBS-09 | "12/30" placeholder looks filled in | `MM/YY` |
| ECOM-015 OBS-10 | No visible quantity buttons | − and + around the quantity; + stops at the available stock |

OBS-08 (card autofill needs HTTPS) is a README item for ECOM-017; nothing changes in the app.

### Verification (part B)

| # | Criterion | Result | How it was proven |
|---|---|---|---|
| B1 | A duplicate SKU names the holder and links to it | **Pass** | Unit, repository and API tests on PostgreSQL; component tests; Playwright on both devices |
| B2 | SKUs on one line; actions always reachable | **Pass** | Component tests (open, Escape, tap outside, Archive closes it); Playwright: inline on desktop, bottom panel on the phone |
| B3 | Success messages close by themselves; notices stay clear of the actions | **Pass** | Component test with a fake clock; Playwright measures the notice on the left and sees it close |
| B4 | A new build offers a reload | **Pass** | Component tests (newer build, same build, failed answer, tab visible again, never in development); smoke check that `version.json` is published and never cached; Playwright on both devices |
| B5 | The six import observations | **Pass** | Server test for "line 2" and "lines 2 and 5"; component tests; Playwright: text area, `·`, a disabled Commit with `not-allowed`, the sticky bar, focus on the next row, the read-only summary after Discard |
| B6 | The three purchase observations | **Pass** | Component tests; Playwright: − and +, + stops at the stock, the greyed line, "Subtotal of available items", `MM/YY` |
| B7 | No screen is wider than a phone | **Pass** | New Playwright guard on six screens (DEF-02, D-112) |

**Defect found by Playwright and fixed before review:** the admin products page was 566 px wide on a 412 px phone (DEF-02 in the evidence, D-112).

### Failure cases and retries (part B)

| Situation | Result |
|---|---|
| The SKU's holder can't be found when the database refuses it (a delete in between) | Pass: the plain "SKU … is already taken." message, without links |
| `version.json` is missing, returns HTML or fails | Pass: no banner, and no error shown; the next check tries again |
| A success message while an error is shown | Pass: the success closes after 5 seconds; the error stays until dismissed |
| **Retry:** pressing + repeatedly | Pass: stops at the available stock; checkout still re-checks it with the stock locked |
| Typing a quantity above the stock | Pass: the line is flagged and greyed, **Use N** fixes it, and checkout stays disabled until then |

**Totals for part B:**
- 7 new backend tests, 19 new component tests and 7 new browser tests (run on 2 devices).
- `run.py all` passes in the `ci` container: the static checks, 60 tooling tests, 900 backend tests (99% coverage), 175 frontend tests and 12 smoke checks.
- 39 browser tests passed (4 skipped by design).
- `run.py containers` and `run.py images` pass.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container; the browser tests pass on desktop and mobile.
- Journal, prompt history and this ticket are updated; the owner has accepted it.

## Code review round 4 (2026-11-22, D-110)

### Discoveries fixed

1. **Malformed image addresses could become a server error.** `urlsplit()` raises `ValueError` for malformed IPv6, and reading an invalid port also raises. The value object now converts both cases to `invalid_image_url`; API regressions prove a 422 instead of a 500.
2. **Impossible ports were accepted.** Addresses such as `https://images.example.com:bad/photo.jpg` and port 99999 used to pass because only the hostname was inspected. The domain now validates the parsed port too.
3. **The admin form did not enforce the documented 2,048-character limit.** It now uses the same limit as the value object in both the input and its client-side validation, so it does not send a value the domain must reject.
4. **A storefront test was flaky under the complete-suite load.** Its async catalog wait used Testing Library's one-second default and timed out once while all frontend files were running, although the isolated test and browser suite passed. The shared storefront wait now has a three-second ceiling; failures still fail quickly, but normal worker contention no longer creates a false negative.

### Output review

- Inspected all 18 stored screenshots and re-ran the complete Playwright output against freshly rebuilt images.
- The bright green card and product-page image is the test's deliberately stretched one-pixel fixture, not a rendering defect; the broken-image fallback and real category placeholders render correctly.
- The cart button looked muted in the screenshot, so its state was checked after capture as well as before it. It is enabled; the normal spruce button colour is lighter than its hover colour. The extra post-capture assertion remains as a guard.
- Result: 26 browser tests passed and 3 device-specific tests skipped by design. No additional layout or interaction defect was reproduced.
- Complete verification: all static and architecture checks, 60 tooling tests, 898 backend tests (99.62% scoped coverage), 157 frontend tests (96.18% line coverage), and all 11 smoke checks pass.
