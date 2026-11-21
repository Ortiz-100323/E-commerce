# ECOM-008: Test evidence

| Field | Value |
|---|---|
| Ticket | [ECOM-008](../ECOM-008.md): Storefront search UI |
| Test type | Manual acceptance test (owner), in the browser |
| Tester | Project owner |
| Date | 2026-11-21 |
| Environment | Local compose stack, shop at http://localhost:3000, build of `feature/ECOM-008-storefront-search`, the owner's own 7 active products |
| Result | **Passed**: no defects, no observations |

## Test runs

| # | Step | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| 1 | Choose Category **Gifts** | Only the products in Gifts, gifts shown as "Free" with the Gift badge | "2 products": Collar gift and Small gift Shoes, both "Free" with the Gift badge | **Passed** (criteria 1 and 3) | [01](01-category-gifts-filter.png) |
| 2 | All categories, sort by **Price: high to low** | All 7 active products, the most expensive first; out-of-stock products labelled | "7 products": Trail Shoes $120.00 (Out of stock), Running Shoes $89.99, Normal shoes $55.00, Testing shoes $10.00, … | **Passed** (criteria 1 and 4: the out-of-stock label) | [02](02-sorted-price-high-to-low.png) |

**Owner's verdict:** "It is working pretty well."

## Notes

- In screenshot 01, the Gifts category holds 2 products. The third gift, "shoes for gift", is in the Sports category, so it shows under **Gifts only** but not under Category **Gifts**. Both filters behave as designed.
- Screenshot 02 shows SP-003 "Normal shoes" at $55.00 without a Gift badge: the data fix from migration 0004 (D-083) holds in the shop too.
