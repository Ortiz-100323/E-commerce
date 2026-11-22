# ECOM-020: Test evidence

| Field | Value |
|---|---|
| Ticket | [ECOM-020](../ECOM-020.md): buyer sign-up on the login page, and "My orders" |
| Test type | Automated browser tests (Playwright 1.65.0), before the owner's review |
| Date | 2026-11-22 |
| Devices | **Desktop** 1280 × 800 and **phone** (Pixel 7) |
| Result | **Passed**, in the same run as ECOM-019 (44 tests) |

## Screenshots

| # | What it shows | File |
|---|---|---|
| 01 | **My orders** after a new customer signed up and bought a test notebook: number, date, total, status and items; **My orders** and **Log out** in the header | [01](01-desktop-my-orders.png) |
| 02 | The same on a phone | [02](02-mobile-my-orders.png) |

The sign-up panel is in the ECOM-019 evidence (screenshots 01 and 02), because both tickets share the one login page.

## What the browser test checked, on both devices

| Step | Result |
|---|---|
| From the shop, **Log in** → **Create account** with name, email and password | Pass: back on the same shop search, logged in, with **My orders** in the header |
| Add to cart → checkout | Pass: name and email already filled in; "This order will be kept in My orders." |
| Pay with the test card | Pass: the confirmation offers **See My orders** |
| My orders | Pass: exactly the one order, with the product's name |
| Open `/admin/products` | Pass: "This area is for administrators"; no Admin link |
| Call the admin API with this customer's cookie | Pass: 403 |

## Owner's test in the portal (2026-11-22, prompt #048)

The owner's name and email were pixelated with `testing/scripts/redact_images.py` (D-103) and checked by eye before the commit.

| # | Step | Result | Evidence |
|---|---|---|---|
| 1 | Create a new account on the login page | Passed: logged in, with **My orders** and **Log out** in the header | [03](03-owner-shop-logged-in.png) |
| 2 | Buy 2 Air Purifiers | Passed: "Your order is paid.", with **See My orders** | [04](04-owner-order-paid.png) |
| 3 | Open My orders | Passed: the order, $379.98, Paid | [05](05-owner-my-orders.png) |
| 4 | Log in to the admin view | Passed | owner's report |

**Owner's verdict:** "Create a new account worked, able to buy, Saw in my orders, got inside of the admin view."

### OBS-01: an admin can buy

- **Observed:** logged in as an admin, the owner could still buy.
- **Why:** this is by design for the MVP. The third recommendation the owner accepted (D-117) makes an admin's purchase a guest order.
- **Owner's direction:** admins should not have Add to cart, and should get an orders screen covering every order. Recorded as [ECOM-021](../ECOM-021.md), after the MVP (D-118).
