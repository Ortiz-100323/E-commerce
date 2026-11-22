# ECOM-019: Test evidence

| Field | Value |
|---|---|
| Ticket | [ECOM-019](../ECOM-019.md): single login with roles, and the admin area for admins only |
| Test type | Automated browser tests (Playwright 1.65.0, Chromium headless shell), before the owner's review |
| Date | 2026-11-22 |
| Environment | Local compose stack with the seeded admin `admin@example.com`; test products prefixed `E2E-<run>-` and archived afterwards |
| Devices | **Desktop** 1280 × 800 and **phone** (Pixel 7) |
| Result | **Passed**: 44 browser tests on both devices (5 skipped by design) |

## Screenshots

| # | What it shows | File |
|---|---|---|
| 01 | The single login page on a computer: **I have an account** beside **New here? Create an account**; the header shows only Shop and the cart to a visitor | [01](01-desktop-login-page.png) |
| 02 | The same page on a phone, the two panels stacked | [02](02-mobile-login-page.png) |
| 03 | After the admin logs in: the admin area, with **Admin**, the admin's name and **Log out** in the header | [03](03-desktop-admin-after-login.png) |
| 04 | The same on a phone | [04](04-mobile-admin-after-login.png) |
| 05 | The **Admins** tab: the list of administrators and **Create admin**, after a new admin was created | [05](05-desktop-admins-page.png) |
| 06 | A customer who opens `/admin/products`: "This area is for administrators", and no Admin link | [06](06-desktop-buyer-blocked.png) |
| 07 | The same on a phone | [07](07-mobile-buyer-blocked.png) |

## What the browser tests checked

| Check | Result |
|---|---|
| A visitor sees **Log in** and no Admin link | Pass |
| A wrong password shows "The email or password is incorrect." | Pass |
| The seeded admin logs in and lands in the admin area | Pass |
| **Log out** ends the session; `/admin/products` then asks to log in, with the page remembered | Pass |
| An admin creates an admin, who logs in from another browser and lands in the admin area | Pass (desktop) |
| A customer is shown "This area is for administrators", and the admin API answers 403 | Pass |
| The import, product card and purchase specs work with the admin's login instead of a typed name | Pass |

## Defect found before review

### DEF-01: logging out from an admin page bounced to the login page

- **Found by:** the component test "logs out and shows Log in again".
- **Cause:** the session was cleared before the move to the shop, so the admin guard reacted first and sent the visitor to the login page.
- **Fix:** **Log out** now goes to the shop first, then ends the session.
- **Journal:** D-117.

## Known limitation

Accounts can't be removed (out of scope), so each full browser-test run leaves one test admin (`e2e-admin-…@example.com`) and two test customers in the local database.
