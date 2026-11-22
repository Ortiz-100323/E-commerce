# ECOM-021: Test evidence

| Field | Value |
|---|---|
| Ticket | [ECOM-021](../ECOM-021.md): admins don't shop, and an admin orders screen with every order |
| Test type | Automated browser tests (Playwright 1.65.0), before the owner's review |
| Date | 2026-11-22 |
| Devices | **Desktop** 1280 × 800 and **phone** (Pixel 7) |
| Result | **Passed**: 44 browser tests on both devices (5 skipped by design) |

## Screenshots

| # | What it shows | File |
|---|---|---|
| 01 | The admin **Orders** tab, searched by a customer's email: order number, date, customer, **Customer account**, items, total, Paid | [01](01-desktop-admin-orders.png) |
| 02 | The same on a phone: each order as a labelled card | [02](02-mobile-admin-orders.png) |
| 03 | One order in full: the status and account badges, the customer, the lines, the total, the card and the payment reference | [03](03-desktop-admin-order-detail.png) |
| 04 | The same on a phone | [04](04-mobile-admin-order-detail.png) |
| 05 | An admin who opens `/checkout`: "Administrator accounts can't place orders", with **See all orders** and **Log out**; no Cart in the header | [05](05-desktop-admin-cannot-buy.png) |
| 06 | The same on a phone | [06](06-mobile-admin-cannot-buy.png) |

## What the browser test checked, on both devices

| Step | Result |
|---|---|
| A new customer signs up and buys | Pass (ECOM-020's steps) |
| The admin logs in and searches Orders by that customer's email | Pass: exactly one order, marked **Customer account** |
| Opening the order | Pass: the detail page with the product's name |
| The admin on the shop | Pass: the product is listed, with no Add to cart and no Cart |
| The admin opens `/checkout` | Pass: "Administrator accounts can't place orders" |

## Owner's review in the portal (2026-11-22, prompt #051)

| # | What it shows | Result | Evidence |
|---|---|---|---|
| 1 | Admin → **Orders**: all 83 orders, newest first, with Guest and Customer account badges, totals and statuses (Paid, Payment declined) | Accepted | [07](07-owner-admin-orders.png) |

**Owner's verdict:** "great, you can commit and push". The screenshot shows only test data, so it needed no redaction.
