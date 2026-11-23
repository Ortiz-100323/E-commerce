# ECOM-020: Buyer sign-up on the login page, and "My orders"

| Field | Value |
|---|---|
| Type | Story (backend and frontend) |
| Phase | 5 |
| Status | **Done**: validated by the owner, committed and pushed; included in `main` by the final delivery merge and push (prompts #048, #053 and #062; D-118). The owner's follow-up (admins don't shop; an all-orders screen) is ECOM-021 |
| Depends on | ECOM-019 (single login, roles, sessions), ECOM-015 |
| Architecture | §3.1 (`identity`), §4.2 (`Order`), §4.5, §5, §7.2 (key scope with a login) |
| Journal | D-114 (the login model), D-116 (this plan), D-117 (as built), D-129; supersedes D-108 |
| Evidence | [Playwright on desktop and phone](ECOM-020-evidence/README.md) |

## Context

The owner's direction (prompt #046):
- the same login page that ECOM-019 builds lets a visitor without an account sign up with name, email and password;
- public sign-up always creates a **buyer**, never an admin;
- a buyer who logs in goes back to the shop with their account available, including "My orders";
- no email confirmation and no password reset.

## Scope

- **Backend, on ECOM-019's `identity` context**
  - **Sign-up:** `POST /api/v1/accounts` with `{name, email, password}`.
    - It always creates a `BUYER`, and refuses any other field, such as `role`, with 422.
    - The buyer is logged in at once: 201 and the session cookie.
    - The same password rules and audit as ECOM-019 (`account.created` with the source "sign-up").
  - **A taken email** (a buyer's or an admin's) answers 409 "An account with this email already exists. Log in instead." No account is created or changed. This reveals that the email is registered, a trade-off the owner accepted, since there is no email confirmation.
  - **Orders:**
    - migration 0011 adds a nullable `orders.buyer_id` and an index on (`buyer_id`, `created_at`);
    - a checkout with a buyer's session links the order to the buyer;
    - without a session, checkout is unchanged (guest);
    - with an admin's session, the order is a guest order;
    - a session cookie that is present but expired gives 401 before anything is charged;
    - the idempotency key's scope becomes (buyer, key) for buyers.
  - **"My orders":** `GET /api/v1/me/orders?page=` returns the buyer's own orders, newest first, 10 per page: number, date, status, total and items. An admin gets 403 `buyer-required`, and a visitor 401.
- **Frontend**
  - **`/login`** gains a second panel, "New here? Create an account" (name, email, password, **Create account**). It sits beside the log-in form on a computer and below it on a phone. After sign-up, the buyer goes back to the shop page they came from, logged in.
  - **The header** shows a buyer their name, **My orders** and **Log out**.
  - **`/account/orders`** lists the orders, each linking to its existing order page. It has an empty state ("No orders yet. Start shopping") and pages.
  - **Checkout** pre-fills the name and email for a buyer. A visitor sees "Log in or create an account to keep this order in My orders" (optional; guest checkout stays).
  - **The confirmation page** links to **My orders** for buyers.

## Acceptance criteria

1. On the login page, a visitor can create an account with name, email and password, and is logged in as a buyer right away.
2. Sign-up never creates an admin: a request carrying a `role` (or any unknown field) is refused, and every new account is a buyer.
3. Signing up with an email that already has an account (buyer or admin) is refused with a clear message, and the existing account is unchanged.
4. A buyer who logs in goes back to the shop, with **My orders** and **Log out** in the header.
5. An order placed by a logged-in buyer appears in "My orders"; a guest order doesn't, and guest checkout works as before.
6. "My orders" shows only the buyer's own orders, newest first; it answers 403 to an admin and 401 to a visitor.
7. A buyer — including one who has just signed up — gets 403 on every admin endpoint and can't open the admin area.
8. Passwords are stored only as scrypt hashes and never appear in the database, responses or logs.

## Test plan (tests first)

- **Use cases with fakes:**
  - sign-up creates a buyer and a session;
  - a taken email;
  - a checkout links the order to the buyer only.
- **API on PostgreSQL:** each criterion, plus:
  - the same idempotency key used by two different buyers creates two orders;
  - a guest checkout is unchanged;
  - an expired cookie at checkout gives 401 with nothing charged.
- **Tests proving a buyer can't become or act as an admin:**
  - sign-up with `role: "ADMIN"`, `role: "admin"` or `is_admin: true` gives 422, with no account created;
  - a normal sign-up's account is `BUYER` in the database;
  - sign-up with the seed admin's email gives 409, and the admin's hash and role are unchanged;
  - an admin creating an admin with a buyer's email gets 409, and the buyer stays a buyer;
  - a contract test over the API description: only `POST /admin/accounts` creates an admin, and no request body accepts a `role`;
  - a freshly signed-up buyer gets 403 on every admin endpoint (ECOM-019's contract test, with this buyer).
- **Frontend:**
  - the sign-up panel and its field errors;
  - the header for a buyer;
  - "My orders" with its empty state and pages;
  - the checkout pre-fill.
- **Browser (desktop and phone):**
  - sign up, buy, and see the order in "My orders";
  - a guest purchase isn't listed;
  - the new buyer is blocked from `/admin`.

## Failure cases and retries (D-072)

| Situation | Expected | Planned result |
|---|---|---|
| Invalid name, email, or a password shorter than 12 characters | 422 under each field | — |
| An email that already has an account | 409; no account created or changed | — |
| A `role` or other extra field in sign-up | 422; nothing created | — |
| Session expired during checkout | 401 before payment; the screen asks to log in again, so an order is never placed as a guest order by accident | — |
| **Retry:** signing up twice at once with the same email | Exactly one account (unique index); the other gets 409 | — |
| **Retry:** paying twice with the same key while logged in | One order, linked once (ECOM-014's replay, scoped to the buyer) | — |
| **Stock:** a buyer's checkout | The same locking and stock checks as a guest's; never oversold | — |

## Out of scope (owner's decision)

Email confirmation, password reset, profile editing, removing accounts, and linking past guest orders.

## As built and verified (2026-11-22, prompt #047, D-117)

Evidence: [ECOM-020-evidence](ECOM-020-evidence/README.md).

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | Sign-up on the login page creates a buyer, logged in at once | **Pass** | Unit, API and component tests; Playwright on both devices |
| 2 | Sign-up never creates an admin; `role` and other extra fields are refused | **Pass** | API tests with `role: "ADMIN"`, `role: "admin"`, `is_admin` and `roles` (422, nothing created); the screen sends only name, email and password; a contract test finds no `role` in any request body |
| 3 | A taken email (buyer's or admin's) is refused, and the account is unchanged | **Pass** | API tests check the admin's hash and role before and after |
| 4 | A buyer goes back to the shop with **My orders** and **Log out** | **Pass** | Component tests; Playwright |
| 5 | A buyer's order is in My orders; a guest order isn't; guest checkout unchanged | **Pass** | API tests; Playwright (buy, then My orders lists exactly that order) |
| 6 | Only the buyer's own orders, newest first; 403 for an admin, 401 for a visitor | **Pass** | API tests (12 orders over 2 pages; another buyer sees none); component tests |
| 7 | A buyer, even a brand-new one, gets 403 on every admin endpoint and can't open the admin area | **Pass** | The ECOM-019 access matrix; an API test right after sign-up; Playwright |
| 8 | scrypt hashes only; no password in the database, responses or logs | **Pass** | The sensitive-value test |

### Failure cases and retries (results)

| Situation | Result |
|---|---|
| Invalid name, email or a short password | Pass: 422 under each field, checked in the screen before sending |
| A taken email | Pass: 409 "An account with this email already exists. Log in instead." |
| A `role` or other extra field | Pass: 422; nothing created |
| Session ended at checkout | Pass: 401 before anything is charged; the screen says "Your login ended, so nothing was charged." and offers to log in again or pay as a guest |
| **Retry:** two sign-ups at the same moment | Pass: exactly one account; the other gets 409 |
| **Retry:** the same key twice by one buyer | Pass: one order, replayed |
| **Retry:** the same key by two buyers | Pass: two orders, never shared |
| **Stock:** a buyer's checkout | Pass: the same locking as a guest; the stock goes down by what was bought |

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` and the browser tests are green locally and on GitHub Actions.
- Journal, prompt history and this ticket are updated; the owner has accepted it (together with ECOM-019).
