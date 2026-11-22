# ECOM-018: UI polish and user experience, starting with the shop's product card

| Field | Value |
|---|---|
| Type | Story (frontend, with a small backend change for product images) |
| Phase | 5 |
| Status | **To Do**: plan accepted by the owner (prompt #038); not started yet |
| Priority | First after ECOM-016 (owner's order, prompt #037: ECOM-018 → ECOM-019 → ECOM-020 → ECOM-017) |
| Depends on | ECOM-007, ECOM-008, ECOM-012, ECOM-015 |
| Architecture | §4.2 (`Product`), §4.5, §5, §10 (CSP), CC-07 |
| Journal | D-106 |
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

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` is green in the `ci` container; the browser tests pass on desktop and mobile.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
