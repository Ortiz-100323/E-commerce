# ECOM-019: Single login with roles, and the admin area for admins only

| Field | Value |
|---|---|
| Type | Story (backend and frontend) |
| Phase | 5 |
| Status | **Done**: validated by the owner in the portal together with ECOM-020 (prompt #048, D-118); not committed yet |
| Depends on | ECOM-016, ECOM-018 |
| Architecture | §3.1 (a new `identity` context), §4.5, §4.6, §5, §6.4 (audit actor) |
| Journal | D-114 (the login model), D-115 (this plan), D-117 (as built); supersedes D-107 and D-113 |
| Evidence | [Playwright on desktop and phone](ECOM-019-evidence/README.md) |
| Followed by | [ECOM-020](ECOM-020.md): buyer sign-up and "My orders", on the same login page |

## Context

Today anyone who opens `/admin` can change products and import files. The admin only types a name ("Who is reviewing?"), and the API trusts the `X-Actor-Name` header.

The owner's direction (prompt #046):
- one **Log in** button in the header, leading to one login page;
- after logging in, the app knows the account's role: admins go to the admin area, buyers go back to the shop;
- the first admin comes from a seed, with its email and password in environment variables;
- an admin can create further admin logins inside the admin area;
- a buyer who tries the admin pages or the admin API is blocked;
- no email confirmation and no password reset.

This ticket builds the login, the roles and the admin side. ECOM-020 adds buyer sign-up and "My orders" to the same page.

## Scope

- **Backend: a new `identity` context (D-114)**
  - **`Account`:** id, name, email (unique and case-insensitive across all accounts), scrypt password hash, `role` (`ADMIN` or `BUYER`), active flag and creation time. The role is fixed when the account is created, and no endpoint changes it.
  - **Passwords:**
    - 12 to 128 characters, with no composition rules (NIST SP 800-63B);
    - scrypt from Python's standard library (N = 2^15, r = 8, p = 3), with a 16-byte salt per password and the parameters stored with the hash;
    - no new package.
  - **Sessions:**
    - one cookie, `session`: `HttpOnly; SameSite=Strict; Path=/api`, and `Secure` when `SESSION_COOKIE_SECURE=true`;
    - a random 256-bit token, of which only the SHA-256 is stored;
    - 30 idle minutes, 8 hours in all;
    - the role is read from the database on every request.
  - **Endpoints:**
    - `POST /api/v1/session` logs in and answers `{id, name, email, role}`;
    - `GET /api/v1/session` answers who is logged in;
    - `DELETE /api/v1/session` logs out, with 204 even when already logged out;
    - `GET /api/v1/admin/accounts` lists the admins;
    - `POST /api/v1/admin/accounts` (`{name, email, password}`) creates an admin; admins only.
  - **Brute force:**
    - after 5 failures for one email in 15 minutes, log-in answers 429 with `Retry-After`;
    - every failure gives "The email or password is incorrect.";
    - an unknown email takes the same time as a wrong password.
  - **Changes from another site** are refused with 403 `cross-site-request`: `Sec-Fetch-Site: cross-site`, or an `Origin` that isn't this site. nginx forwards `Host $http_host`, so the port is kept.
  - **Protected (401 without a session, 403 `admin-required` for a buyer):**
    - every product change;
    - product history;
    - product searches with `status=ARCHIVED` or `ALL`;
    - every `/imports` endpoint;
    - `/admin/accounts`.

    The shop's reads, the cart quote, checkout and the order pages stay public.
  - **Audit:**
    - changes are recorded under the logged-in admin's name, and `X-Actor-Name` is ignored;
    - `account.created`, `session.logged_in`, `session.logged_out` and `session.login_failed` are recorded too, never with a password.
  - **Seed:** `python -m ecommerce.identity.seed` runs after the migrations in the backend's start command.
    - It creates the first admin from `ADMIN_SEED_EMAIL`, `ADMIN_SEED_PASSWORD` and `ADMIN_SEED_NAME` (default "Administrator"), but only when no admin exists.
    - It never changes an existing account, and running it again does nothing.
    - compose sets public local values. The README (ECOM-017) says to change them.
- **Frontend**
  - **Header:**
    - logged out: **Log in**;
    - logged in: the person's name and **Log out**;
    - the **Admin** link shows only to admins.
  - **`/login`:** email, password and **Log in**.
    - The generic error on a wrong login, and on 429: "Too many attempts. Try again in N minutes."
    - After logging in, admins go to `/admin/products`, or to the admin page they asked for. Buyers go back to the shop page they came from.
  - **`/admin/*`:**
    - logged out: the login, then back to the page that was asked for;
    - a buyer: "This area is for administrators", with a link to the shop, and no admin API call is made.
  - **Admin area:** a new **Admins** tab lists the admins and has a **Create admin** form (name, email, password).
  - **A 401 during admin work** (an expired session) returns to `/login` with "Your session ended. Log in again." It doesn't raise a red error pop-up.
  - **Removed:** the "Who is reviewing?" prompt, its storage and the API client's `actor` option.
- **Tools:** the smoke test and the browser tests log in with the seeded admin. The API tests' `ANTONIO` and `MARIA` become two seeded admins' session cookies.

## Acceptance criteria

1. The header shows **Log in** to visitors; it leads to the single `/login` page.
2. An admin who logs in lands in the admin area; a buyer lands back in the shop (buyers exist through ECOM-020's sign-up, and through test data until then).
3. A wrong email or password shows "The email or password is incorrect." without saying which part was wrong; after 5 failures in 15 minutes the email is refused with 429, even with the right password, until the window passes.
4. Without a session, every admin API endpoint answers 401; with a buyer's session, 403 `admin-required`; the shop keeps working without logging in.
5. A buyer who opens `/admin` sees "This area is for administrators", never the admin screens, and the **Admin** link isn't shown to buyers.
6. The seed creates the first admin from the environment once; running it again changes nothing.
7. An admin can create another admin; the new admin can log in; a buyer can't create admins (403), and creating an admin with an email that is already taken is refused (409) without changing that account.
8. Logging out ends the session at once; a session also ends after 30 idle minutes or 8 hours.
9. Product changes and imports are recorded under the logged-in admin's name; `X-Actor-Name` alone no longer works.
10. Passwords are stored only as scrypt hashes; no password appears in the database, responses or logs. The cookie is `HttpOnly` and `SameSite=Strict` (`Secure` when configured), and a change sent from another site is refused.

## Test plan (tests first)

- **Domain:**
  - email, name and password rules;
  - hashing and verifying, and the stored parameters;
  - session lifetimes and the throttle window.
- **Use cases with fakes:**
  - log in, log out, the current account and expiry;
  - the throttle, and that a refused attempt isn't counted;
  - creating an admin, and a taken email;
  - the seed: create once, then nothing.
- **API on PostgreSQL:** each criterion. Plus a **contract test** that sends every admin endpoint with no cookie, with only `X-Actor-Name`, with a buyer's cookie and with an admin's cookie, and checks 401, 401, 403 and allowed.
- **Security tests:**
  - a changed or invented cookie gives 401;
  - the role comes from the database, not the cookie;
  - a cross-site `Origin` or `Sec-Fetch-Site` gives 403;
  - no password appears in responses, logs or any table.
- **Frontend:**
  - the header for each state;
  - the login form and its errors;
  - the redirect by role, and back to the page asked for;
  - the admin guard for a buyer;
  - the Admins tab;
  - the "session ended" return.
- **Browser (desktop and phone):**
  - log in as the seeded admin, create an admin, and log in as them;
  - a buyer is blocked from `/admin`;
  - log out.

## Failure cases and retries (D-072)

| Situation | Expected | Planned result |
|---|---|---|
| Wrong password or unknown email | 401 with the same message, in about the same time | — |
| Sixth attempt within 15 minutes | 429 with `Retry-After`; the refused attempt isn't counted | — |
| An expired or logged-out session on an admin call | 401; the screen returns to the login with "Your session ended" | — |
| A buyer's session on an admin call | 403 `admin-required`; nothing changes | — |
| A change posted from another site with an admin's cookie | 403 (the cookie isn't sent with `SameSite=Strict`, and `Origin` is checked) | — |
| Creating an admin with a taken email (twice at once, or an existing buyer's) | 409; exactly one account, with its role unchanged | — |
| **Retry:** logging in twice | Two sessions; each logs out on its own | — |
| **Retry:** logging out twice | 204 both times | — |
| **Retry:** the seed runs on every start | One admin, never changed | — |

## As built and verified (2026-11-22, prompt #047, D-117)

The owner accepted the three recommendations:
- the local seed admin is `admin@example.com` / `local-admin-password-change-me`;
- one login lifetime for everyone;
- an admin's purchases are guest orders.

The architecture is in TECHNICAL_ARCHITECTURE "Logins and roles as built"; the evidence is in [ECOM-019-evidence](ECOM-019-evidence/README.md).

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | **Log in** in the header leads to the single `/login` | **Pass** | Component tests; Playwright on desktop and phone |
| 2 | Admins land in the admin area, buyers back in the shop | **Pass** | Component tests (`next` followed only when it fits the role, and never to another site); Playwright |
| 3 | One generic message; 429 after 5 failures in 15 minutes, even with the right password | **Pass** | Unit tests with a movable clock; API tests on PostgreSQL (`Retry-After`, another email unaffected) |
| 4 | Admin API: 401 without a session, 403 `admin-required` for a buyer | **Pass** | A matrix test sends all 15 admin endpoints with no cookie, only `X-Actor-Name`, an invented cookie, a buyer's and an admin's cookie |
| 5 | A buyer sees "This area is for administrators" and no Admin link | **Pass** | Component test (no admin data is requested); Playwright on both devices |
| 6 | The seed creates the first admin once | **Pass** | PostgreSQL tests: once, never changes a password, never promotes a customer, warns without settings, refuses an invalid seed; the live stack logged "created the first administrator" |
| 7 | Admins create admins; a buyer can't; a taken email is refused without change | **Pass** | Unit, API and component tests; Playwright (the new admin logs in from another browser) |
| 8 | Log-out ends the session at once; 30 idle minutes or 8 hours | **Pass** | Unit tests; API test (the old cookie gets 401 everywhere) |
| 9 | Changes recorded under the logged-in admin; `X-Actor-Name` alone refused | **Pass** | API tests; a contract test checks that no endpoint has the header |
| 10 | scrypt hashes only; no password anywhere; cookie `HttpOnly`, `SameSite=Strict`, `Secure` when set; cross-site changes refused | **Pass** | A sensitive-value test reads responses, `accounts`, `account_sessions` and `audit_log`; cookie-attribute tests; same-site tests (`Origin`, `null`, `Sec-Fetch-Site`) |

### Failure cases and retries (results)

| Situation | Result |
|---|---|
| Wrong password or unknown email | Pass: 401 `invalid-credentials`, same message; the unknown email still runs a scrypt check |
| Sixth attempt within 15 minutes | Pass: 429 with `Retry-After`; the refusal isn't counted |
| Session ended during admin work | Pass: back to the login with "Your session ended. Log in again.", and no red error pop-up |
| A buyer's session on an admin call | Pass: 403 `admin-required`; nothing changes |
| A change from another site | Pass: 403 `cross-site-request` |
| Creating an admin with a taken email (including at the same time) | Pass: 409, one account; two sign-ups at the same moment make exactly one |
| **Retry:** logging in twice | Pass: two sessions; each logs out on its own |
| **Retry:** logging out twice | Pass: 204 both times |
| **Retry:** the seed on every start | Pass: one admin, never changed |
| A stale cookie on a public page or at checkout | Pass: the shop ignores it; a 401 clears it, so the next request is a guest's |

**Totals for ECOM-019 and ECOM-020 together:**
- About 135 new backend tests: unit, use cases, PostgreSQL, API, the access matrix and contracts.
- 21 new frontend tests.
- 3 new browser tests, run on 2 devices.
- `run.py all` passes in the `ci` container: static checks, 11 architecture contracts, 60 tooling tests, 1,076 backend tests (99% coverage), 192 frontend tests and 14 smoke checks.
- 44 browser tests pass (5 skipped by design).
- `run.py containers` and `run.py images` pass.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` and the browser tests are green locally and on GitHub Actions.
- Journal, prompt history and this ticket are updated; the owner has accepted it (together with ECOM-020).
