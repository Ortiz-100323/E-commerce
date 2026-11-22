# ECOM-019: Admin login: product management and CSV import only after an admin signs in

| Field | Value |
|---|---|
| Type | Story (backend and frontend) |
| Phase | 5 |
| Status | **Backlog** (second in the owner's order, prompt #037) |
| Depends on | ECOM-016 |
| Architecture | §3.1 (a new `identity` context), §4.5, §4.6, §5, §6.4 (audit actor) |
| Journal | D-107 |

## Context

Today anyone who opens `/admin` can change products and import files. The admin is identified only by the name they type ("Who is reviewing?"), and the API trusts the `X-Actor-Name` header. The owner asked for a login screen, so that product management and CSV import are reachable only after an admin signs in. No admin authentication exists yet, so this ticket adds the minimum needed, done to a production standard.

## Scope

- **Backend:** a new `identity` bounded context.
  - **`AdminAccount`:** id, email (unique, case-insensitive), display name, password hash and active flag.
  - **Passwords:** hashed with **scrypt** from Python's standard library (`hashlib.scrypt`, a random 16-byte salt per password, parameters stored with the hash so they can be raised later). No new package. A password must be 12 to 128 characters, without composition rules (NIST SP 800-63B).
  - **Server-side sessions:**
    - a random 256-bit token, of which only a SHA-256 hash is stored;
    - an idle timeout of 30 minutes and an absolute limit of 8 hours;
    - signing out deletes the session.
  - **Cookie:** `admin_session`, with `HttpOnly`, `SameSite=Strict` and `Path=/api`. It is `Secure` when `SESSION_COOKIE_SECURE=true`, which a real deployment over HTTPS must set.
  - **Endpoints:**
    - `POST /admin/session` signs in;
    - `GET /admin/session` answers who is signed in;
    - `DELETE /admin/session` signs out.
  - **Brute force:** after 5 failed attempts for one email within 15 minutes, sign-in answers **429** with `Retry-After`. Every failure gives the same answer ("The email or password is incorrect."), and an unknown email still takes the time of a hash check, so emails can't be guessed.
  - **CSRF:** `SameSite=Strict`, plus a check that refuses a cookie-authenticated change whose `Origin` header belongs to another site.
  - **What becomes protected** (401 `authentication-required` without a valid session):
    - every product change (create, update, archive, restore);
    - product history;
    - every `/imports` endpoint;
    - product searches for anything other than active products (`status=ARCHIVED` or `ALL`).

    The shop (active products, categories, cart quote, checkout, orders) stays public.
  - **The audit actor comes from the session.** The `X-Actor-Name` header is removed, so the audit log records the signed-in admin's name and nobody can claim to be someone else.
  - **The first admin:** `python -m ecommerce.identity.create_admin --email … --name …` asks for the password, for real deployments. For local Docker, compose creates a development admin when there is none, from `ADMIN_BOOTSTRAP_EMAIL` and `ADMIN_BOOTSTRAP_PASSWORD`. These are public local values, like the database login, and the README tells you to change them.
  - Sign-in, sign-out and failed sign-ins go to the audit log (`admin.signed_in`, `admin.signed_out`, `admin.sign_in_failed`, with the email but never the password).
- **Frontend:**
  - `/admin/login` (email, password, **Sign in**);
  - every `/admin` route requires a session and otherwise goes to the login, then back to the page that was asked for;
  - the header shows "Signed in as Ana · Sign out";
  - a 401 during work, such as an expired session, sends you back to the login with a message;
  - the "Who is reviewing?" prompt is removed.
- **Tests and tools:** the smoke test and the browser tests sign in with the development admin; the contract test proves every admin endpoint answers 401 without a session.

## Acceptance criteria

1. Without signing in, `/admin` shows the login screen, and every admin API endpoint answers 401 `authentication-required`; the shop keeps working.
2. Signing in with a correct email and password opens the admin area; a wrong one shows "The email or password is incorrect." without saying which part was wrong.
3. After 5 failed attempts within 15 minutes, sign-in is refused with 429 for that email, even with the right password, until the window passes.
4. Signing out ends the session at once; the old cookie no longer works. A session also ends after 30 idle minutes or 8 hours.
5. Product changes and imports are recorded in the audit log under the signed-in admin's name; the `X-Actor-Name` header is no longer accepted.
6. Passwords are stored only as scrypt hashes; no password appears in the database, responses or logs.
7. The session cookie is `HttpOnly` and `SameSite=Strict` (and `Secure` when configured), and a change sent from another site's page is refused.

## Test plan

- **Domain:** password rules, hash and verify, the session lifetimes.
- **Use cases with fakes:** sign-in, the throttle, sign-out, expiry.
- **API on PostgreSQL:** each criterion, plus a contract test that sends every admin endpoint without a session.
- **Browser:** sign-in, a protected page, sign-out.
- **A sensitive-value test:** no password in responses, logs or tables.

## Failure cases and retries (D-072)

| Situation | Expected | Planned result |
|---|---|---|
| Wrong password or unknown email | 401 with the same generic message, in about the same time | — |
| Sixth attempt within 15 minutes | 429 with `Retry-After` | — |
| Expired or signed-out session on an admin call | 401; the screen returns to the login with "Your session ended" | — |
| A change posted from another site with the admin's cookie | Refused (cookie not sent with `SameSite=Strict`; `Origin` checked) | — |
| **Retry:** signing in twice | Two valid sessions; each signs out on its own | — |
| **Retry:** signing out twice | 204 both times | — |
| An admin made inactive | Their sessions stop working at the next request | — |

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` and the browser tests are green locally and on GitHub Actions.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
