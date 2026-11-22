# ECOM-018: Test evidence

| Field | Value |
|---|---|
| Ticket | [ECOM-018](../ECOM-018.md): UI polish, part A (the shop's product card) |
| Test type | Automated browser test (Playwright 1.65.0, Chromium headless shell), before the owner's review |
| Date | 2026-11-22 |
| Environment | Local compose stack at `http://frontend:8080`, the owner's own catalog (101 active products), and 6 test products per device with the prefix `E2E-<run>-`, archived afterwards |
| Devices | **Desktop**: 1280 × 800. **Mobile**: Pixel 7 emulation (412 × 915, touch, no hover) |
| Result | **Passed**: 19 tests (2 skipped by design: hover on the phone, two columns on the desktop) |

## Screenshots

| # | What it shows | File |
|---|---|---|
| 01 | Desktop, the owner's catalog: category placeholders with their colour and icon, two-line names, softer category, SKU, highlighted price, **Add to cart** | [01](01-desktop-shop.png) |
| 02 | Desktop, every card state side by side: a photo (the test's one-pixel image, stretched over the 4:3 area), a broken photo shown as the Kitchen placeholder, "Only 2 left", "Out of stock" with a disabled button, a gift ("Free"), a long name cut at two lines, and two "E2E Speaker" cards told apart by their SKU | [02](02-desktop-card-states.png) |
| 03 | Phone, the owner's catalog: two columns, large buttons | [03](03-mobile-shop.png) |
| 04 | Phone, every card state, two columns, equal heights | [04](04-mobile-card-states.png) |

In these screenshots, names and prices look regular weight rather than bold. The test container only has basic fonts. On Windows (Segoe UI) and other systems they show bold.

## What was checked, on both devices

| Check | Result |
|---|---|
| The image area is 4:3 on every card, measured from its box | Pass |
| A long name takes at most two lines; the full name is in its `title` | Pass |
| Every card in the grid has the same height (within 1 px) | Pass |
| A photo loads; a broken photo falls back to the category placeholder | Pass |
| Two products with the same name show different SKUs | Pass |
| "Only 2 left", "Out of stock" with a disabled button, "Free" for a gift | Pass |
| **Add to cart** on the card updates the header and stops at the stock ("All 2 in your cart") | Pass |
| Clicking the image area opens the product page | Pass |
| Keyboard: Tab from the link reaches the button, Enter and Space add to the cart, Shift+Tab returns to the link with a visible frame around the card, Enter opens the product | Pass |
| Desktop only: hovering lifts the card | Pass |
| Phone only: two columns; buttons at least 44 px tall | Pass |

## Defect found by these tests and fixed before review

### DEF-01: a photo that isn't 4:3 stretched its card

- **Found by:** the 4:3 check, which measured 1:1 on the card with the (square) test photo.
- **Cause:** the image area used `aspect-ratio: 4 / 3`, but an image inside it with `height: 100%` falls back to its own size, and the box grew to fit the square photo.
- **Fix:** the photo is placed absolutely inside the 4:3 box (`position: absolute; inset: 0; object-fit: cover`), so its shape can no longer change the box.
- **Guard:** the same Playwright check, on both devices.

## Design note: category colours

The first screenshots showed Home & Office, Electronics and Outdoors all in the same grey: the colour was picked by a hash of the category name. Each known kind of category now has its own tint (sports green, electronics blue, kitchen apricot, gifts plum, outdoors teal, home sand, beauty rose…). The hash is used only for categories the shop doesn't know yet, and grey is kept for tools and unknown ones.

## Round 2: one look for every screen (owner's review, prompt #041, D-109)

| Field | Value |
|---|---|
| Test type | Automated browser test (Playwright 1.65.0), before the owner's review |
| Date | 2026-11-22 |
| Result | **Passed**: 26 tests (3 skipped by design: hover on the phone, two columns on the desktop, the screen tour on the phone) |

| # | What it shows | File |
|---|---|---|
| 05 | Desktop shop: the white header with the cart badge, the search panel (search row, then Category, toggle chips and price range), the product count beside **Sort by**, and lighter cards | [05](05-desktop-shop.png) |
| 06 | Desktop card states: stock labels, the price and a compact button on one row, a Gift tag, and the SKU only on the two speakers that share a name | [06](06-desktop-card-states.png) |
| 07 | Desktop product page: the picture on the left, with the name, price, stock, **Add to cart** and details on the right (the green square is the test's one-pixel photo) | [07](07-desktop-product-page.png) |
| 08 | Desktop empty search: what to do next, and **Clear filters** | [08](08-desktop-empty-search.png) |
| 09 | Admin products: the same buttons, fields, dropdown and a table on a white surface | [09](09-desktop-admin-products.png) |
| 10 | Admin new product: the same fields in a white form panel | [10](10-desktop-admin-new-product.png) |
| 11 | Admin CSV import: the same file button and primary button | [11](11-desktop-admin-import.png) |
| 12 | Cart: the same quantity field, link-style **Remove** and primary **Go to checkout** | [12](12-desktop-cart.png) |
| 13 | Checkout: white form sections, the same fields, and the primary **Pay** button | [13](13-desktop-checkout.png) |
| 14 | Phone shop: the filters folded behind **Filters**, so the first products show on the first screen | [14](14-mobile-shop.png) |
| 15 | Phone, filters opened: **Filters (1)** with **In stock only** active | [15](15-mobile-filters-open.png) |
| 16 | Phone card states: two columns, equal heights, 44 px buttons | [16](16-mobile-card-states.png) |
| 17 | Phone product page: the picture above the details, with a full-width **Add to cart** | [17](17-mobile-product-page.png) |
| 18 | Phone empty search | [18](18-mobile-empty-search.png) |

Screenshots 01 to 04 show round 1, kept for comparison.

### Found while checking the screenshots, and fixed before review

- The **Price** label sat a few pixels above **Category**: a `fieldset` legend lines up differently from a label. It is now a labelled group, like the other filters.
- On the phone, the open filters filled the whole first screen, with no products visible. They now fold behind **Filters (N)**.
- The checkout and cart titles were smaller than the other page titles, and the checkout sections sat on grey. Both now match.
- The cart's accessible name came out with extra spaces once it gained an icon and a badge. An explicit label keeps it exactly "Cart: N items" (caught by the component tests).
