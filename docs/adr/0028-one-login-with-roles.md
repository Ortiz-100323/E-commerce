# ADR-0028: One login for admins and customers, with a fixed role and server-side sessions

| Field | Value |
|---|---|
| Status | Accepted. Supersedes [ADR-0027](0027-no-authentication-and-self-declared-actor.md) |
| Date | 2026-11-22 |
| Journal | D-107 (superseded), D-108 (superseded), D-114, D-115, D-116, D-117 |

## Context

The admin area had to be closed, and customers wanted to see their orders. The first plan had two separate sign-ins. The owner asked for one **Log in** button and one login page, where the account decides where you land. Public sign-up creates customers only, the first admin comes from a seed, and admins create other admins.

## Decision

- **A new `identity` context with one `Account`:**
  - name, email (unique, case-insensitive), password hash, role (`ADMIN` or `BUYER`) and an active flag;
  - one email has one account and one role.
- **The role is fixed at creation:**
  - sign-up always creates a `BUYER` and refuses unknown fields, so a `role` can't even be sent;
  - only `POST /admin/accounts`, for admins only, creates an admin;
  - an email that already has an account gets 409, so nobody can be promoted or taken over.
- **Sessions are stored on the server:**
  - the cookie `session` is `HttpOnly; SameSite=Strict; Path=/api`, plus `Secure` when `SESSION_COOKIE_SECURE=true`;
  - it holds only a random 256-bit token, and the server stores its SHA-256;
  - the role is read from the database on every request;
  - a session ends after 30 idle minutes, 8 hours in total, or at log-out;
  - a 401 also clears the cookie.
- **Every request is checked on the server:**
  - admin endpoints give 401 `authentication-required` without a session, and 403 `admin-required` for a customer;
  - customer-only endpoints give 403 `buyer-required` for an admin.
- **Passwords and logins:**
  - passwords are hashed with scrypt (N = 2^15, r = 8, p = 3) from the standard library, and must be 12 to 128 characters;
  - 5 failed logins per email in 15 minutes give 429 with `Retry-After`, counted from the audit log;
  - every failure gets one generic message, with the same timing for an unknown email.
- **Changes from another site are refused** (`Sec-Fetch-Site` and `Origin` checks).
- **The first admin is seeded from `ADMIN_SEED_EMAIL` and `ADMIN_SEED_PASSWORD`** after the migrations.
  - It is created only when no admin exists, and it never changes an existing account or promotes a customer.
  - Running it again does nothing.
- **The audit actor is the logged-in admin.** The old `X-Actor-Name` header is gone.
- **The other contexts never import `identity`.** They get a `Principal` through an `Authenticator` port in the shared kernel.

## Alternatives discarded

- **Two account tables or two login systems:** one email could exist in both, and one login page would have to guess which is meant.
- **A JWT in local storage:** readable by scripts, and a log-out or role change can't take effect at once.
- **HTTP Basic auth:** no log-out, no customer sign-up, and a browser pop-up.
- **`SameSite=Lax`:** not needed, because every logged-in call comes from the app's own pages.

## Consequences

- A contract test checks that no request body anywhere accepts a `role`, and that every admin endpoint refuses a customer.
- **Out of scope by the owner's choice:** email confirmation, password reset, profile editing, and removing or deactivating accounts.
- The seeded admin's password in `docker-compose.yml` is a public development value, and must be changed for anything real.
