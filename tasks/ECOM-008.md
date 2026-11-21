# ECOM-008: Storefront search UI

| Field | Value |
|---|---|
| Type | Story (frontend) |
| Phase | 2 |
| Status | **Done** |
| Depends on | ECOM-006 |
| Architecture | §5, CC-05, CC-07 |
| Journal | D-072, D-087, D-089 |
| Evidence | [ECOM-008-evidence](ECOM-008-evidence/README.md) |

## Context

Shoppers find products by searching and filtering.

## Scope

- `/`: search box, filters (category, price range, in stock, gift), sorting and pagination, kept in the URL.
- A "Gift" badge on gift products.
- `/products/:id`: product detail; "Add to cart" is disabled when the product is out of stock.

## Acceptance criteria

1. Typing a query and applying filters updates the results and the URL.
2. Reloading the page keeps the same search.
3. Gift products show the badge.
4. Out-of-stock products cannot be added to the cart.

## Plan (D-087)

1. **The shop page (`/`)**
   - A search box (name, SKU, description) with a **Search** button.
   - Filters: category (taken from `/categories`), minimum and maximum price, **In stock only** and **Gifts only**.
   - Sort: Name A–Z, Name Z–A, Price low to high, Price high to low, and Newest.
   - Pages of 12 products, with Previous and Next.
   - **Everything lives in the URL** (`?q=shoes&category=Sports&min_price=10&in_stock=true&tag=GIFT&sort=price&page=2`). A reload or a shared link shows the same results.
   - The shop only ever asks for active products; archived ones never appear.
2. **Product cards:** name, price ("Free" for gifts), category, a **Gift** badge and an **Out of stock** label. Each card links to the detail page.
3. **Detail page (`/products/:id`):** name, price, description, category, weight and stock status.
   - **Add to cart** is disabled when the product is out of stock or archived ("No longer available").
4. **A minimal cart**, so criterion 4 means something. The full cart page and checkout come in ECOM-015.
   - The cart is kept in the browser (`localStorage`, as §5 plans), with a session fallback when storage is blocked.
   - The header shows "Cart: N items".
   - **You can never add more than the stock shown:** at the limit, the button says "Only N in stock" and is disabled.
   - The server checks stock again at checkout (ECOM-014).
5. **Shared read hooks:** `useProductList`, `useProduct` and `useCategories` move from the admin feature to `src/api/productQueries.ts`, and both areas use them.

## Verification (2026-11-21)

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | Typing a query and applying filters updates the results and the URL | **Pass** | A fake product API that applies every filter:<br>• Searching "shoes" shows Running Shoes and Trail Shoes. Ticking **In stock only** leaves Running Shoes. Sorting by "Price: high to low" gives `?q=shoes&in_stock=true&sort=-price`, and the request carries exactly those values plus `status=ACTIVE`.<br>• Category, minimum price and **Gifts only** each narrow the list and appear in the URL.<br>• All 5 sort orders and paging (12 per page) are tested. |
| 2 | Reloading the page keeps the same search | **Pass** | The page is opened at `/?q=shoes&in_stock=true&sort=-price`, closed and opened again. The results, the search box, the check box and the sort list all come back the same. |
| 3 | Gift products show the badge | **Pass** | Gift Card shows the **Gift** badge and the price "Free", on the card and on the product page. Other products don't. |
| 4 | Out-of-stock products cannot be added to the cart | **Pass** | Trail Shoes (stock 0) shows "Out of stock", the button is disabled, and clicking it leaves "Cart: 0 items". A product with stock 2, clicked three times fast, stops at 2: "Only 2 in stock", disabled. With the limit loosened by one on purpose, that test fails. |

### Code review round 1 (2026-11-21)

**Fixed:** a valid but out-of-range page in a shared or hand-edited URL, such as `?page=999`, showed neither products nor the normal empty-search message. After the real response arrives, the shop now replaces the URL with the last available page and loads it. A regression test proves a 14-product catalog moves from page 999 to page 2 and shows products 13 and 14.

## Failure cases and retries (D-072)

| Situation | What the shopper sees | Result |
|---|---|---|
| The search fails (5xx) | A notification with the reference, and "We couldn't load the products." with **Try again**, which works | Pass |
| Nothing matches | "No products match your search." with **Clear filters**, which brings everything back | Pass |
| A price filter that isn't a number, or is negative | "Use a price like 19.99." on that field; no request sent | Pass |
| A minimum above the maximum | "The minimum price must not be above the maximum."; no request sent | Pass |
| A hand-edited URL with bad values (`page=abc&sort=colour&tag=SALE&min_price=-1&max_price=x&in_stock=maybe`) | The defaults are used; the request carries only `status=ACTIVE&sort=name&page=1&page_size=12` | Pass |
| A `%` in the search | Sent as-is (`q=100%`) and matched literally | Pass |
| Product page for an unknown id | "Product not found", with "Back to the shop"; no pop-up | Pass |
| Product page for an archived product | "This product is no longer available."; the button says "No longer available" and is disabled | Pass |
| **Stock:** out of stock | "Out of stock" on the card and the product page; button disabled | Pass |
| **Stock:** the cart already holds the whole stock | "Only N in stock"; button disabled | Pass |
| **Fast clicks** on Add to cart | Stops at the stock, never beyond | Pass |
| Reload | The cart is still there | Pass |
| Storage blocked | The cart works for the session | Pass |

**Found while building:** the price errors were first placed inside the field labels, which changed the fields' accessible names (for example, "Min price Use a price like 19.99."). The tests caught it; each message is now outside its label and linked to the field.

**Also in this ticket:**
- The read hooks (`useProductList`, `useProduct`, `useCategories`) moved to `src/api/productQueries.ts` and are shared with the admin area.
- The cart lives in `src/cart/` (`cart.ts` and `CartContext.tsx`). The header shows "Cart: N items".
- The fake product API in the tests now applies category, price range, stock, tag and sort.

**Live check:** the shop's own query against your data returns your 7 active products, and "Gifts only" returns 3. `/products/<id>` loads through nginx.

**Totals:** 19 new frontend tests. The `ci` container passes:
- all static checks, the raw-HTML check and the no-comments check;
- 34 tooling tests;
- 505 backend tests;
- 94 frontend tests, with coverage of 96.13% of statements and 90.3% of branches;
- the smoke checks.

## Owner's test (2026-11-21, prompt #021)

Passed. Category **Gifts** showed the 2 gifts in that category as "Free" with the badge. Sorting by price high to low listed all 7 products with Trail Shoes "Out of stock" first. Evidence and notes: [ECOM-008-evidence](ECOM-008-evidence/README.md).

## Test plan

- Component specs with MSW for each criterion and each row of "Failure cases and retries". The fake product API from ECOM-007 gains the search filters.

## Business view

- **What was built:** the shop. Shoppers can search, filter by category, price, stock and gifts, sort, and page through the products. Each product has its own page with **Add to cart**, and a simple cart counts the items in the header.
- **Why:** challenge rules CC-05 (search) and CC-07 (a usable interface). It is the shopper's half of the store.
- **Main goal:** find products easily and never put in the cart more than is in stock.
- **Human testable or background:** **testable** at http://localhost:3000.
- **What to test:** see prompt #020 of the prompt history.

## Definition of done

- Acceptance criteria pass, written test-first; frontend coverage ≥ 80% (96.1%).
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
