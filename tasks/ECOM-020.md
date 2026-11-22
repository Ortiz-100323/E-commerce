# ECOM-020: Buyer account: register, sign in and "My orders"

| Field | Value |
|---|---|
| Type | Story (backend and frontend) |
| Phase | 5 |
| Status | **Backlog** (third in the owner's order, prompt #037) |
| Depends on | ECOM-019 (the `identity` context and sessions), ECOM-015 |
| Architecture | §3.1 (`identity`), §4.2 (`Order`), §4.5, §5, §7.2 (key scope with a login) |
| Journal | D-108 |

## Context

The owner asked for a very simple buyer account: register with name, email and password, sign in, and a "My orders" page listing their purchases. Orders made while signed in belong to the buyer, and guest checkout keeps working. It stays minimal: no email confirmation, no password reset and no profile editing.

## Scope

- **Backend, reusing ECOM-019's `identity` context:**
  - **`BuyerAccount`:** id, name, email (unique, case-insensitive) and a scrypt password hash, with the same password rules as admins.
  - **A separate session cookie,** `shop_session`: `HttpOnly`, `SameSite=Lax` (so arriving from another site still shows you signed in, while a cross-site POST never carries it), `Path=/api`, and `Secure` when configured.
  - Admin and buyer sessions never grant each other's rights.
  - **Endpoints:**
    - `POST /account` registers and signs in at once;
    - `POST /account/session` signs in, `GET /account/session` answers who is signed in, `DELETE /account/session` signs out;
    - `GET /account/orders` lists the buyer's own orders, newest first, paginated;
    - `GET /account/orders/{id}` returns one of them.
  - The same sign-in throttle as admins: 5 failures in 15 minutes per email.
  - **Orders:**
    - a nullable `buyer_id` column (migration);
    - a checkout made with a valid `shop_session` is linked to that buyer, and its customer name and email default to the account's;
    - without a session, checkout works exactly as today (guest);
    - the idempotency key's scope becomes (buyer, key) for signed-in buyers, as §7.2 planned.
  - **Privacy:**
    - `GET /account/orders` returns only the buyer's own orders; another buyer's order id gives 404;
    - guest orders placed earlier with the same email are **not** linked automatically, because the email isn't verified.
  - **Registering an email that already has an account** answers 409 "An account with this email already exists. Sign in instead." This is a deliberate trade-off for a minimal shop: it reveals that the email is registered. The alternative, a confirmation email, is out of scope.
  - Audit entries: `buyer.registered`, `buyer.signed_in`, `buyer.signed_out`, `buyer.sign_in_failed`. No password, and no email in the actor.
- **Frontend:**
  - in the header, **Sign in** / **Create account**, or "Hi, Ana · My orders · Sign out";
  - the pages `/account/register`, `/account/login` and `/account/orders`;
  - checkout pre-fills the name and email when signed in, and offers "Sign in to save this order to your account" otherwise;
  - the confirmation page links to "My orders" for signed-in buyers;
  - **My orders** lists the date, order number, items, total and status, with a link to each order.

## Acceptance criteria

1. A visitor can register with name, email and password, and is signed in right away.
2. Registering an email that already has an account is refused with a clear message, and no second account is created.
3. A buyer can sign in and out; wrong details give the same generic message as for admins, and the throttle applies.
4. An order placed while signed in appears in "My orders"; an order placed as a guest doesn't, and guest checkout works as before.
5. "My orders" shows only the signed-in buyer's own orders, newest first; another buyer's order can't be opened through it (404).
6. A buyer session can't use admin endpoints, and an admin session doesn't count as a buyer.
7. Passwords are stored only as scrypt hashes and never appear in the database, responses or logs.

## Test plan

- **Domain and use cases:** register, duplicate email, sign in, the throttle, linking an order.
- **API on PostgreSQL:** each criterion; a retry with the same key by two different buyers creates two orders; a guest checkout is unchanged.
- **Browser:** register → buy → "My orders" shows the order; a guest purchase isn't listed.

## Failure cases and retries (D-072)

| Situation | Expected | Planned result |
|---|---|---|
| Invalid name, email or a password shorter than 12 characters | 422 under each field | — |
| An email that already has an account | 409; no second account | — |
| Wrong details, or a sixth attempt | 401 with a generic message; then 429 | — |
| Session expired during checkout | 401: the screen asks the buyer to sign in again before paying, so an order is never silently placed as a guest order | — |
| **Retry:** registering twice quickly with the same email | Exactly one account (unique index); the second gets 409 | — |
| **Retry:** paying twice with the same key while signed in | One order, linked once (ECOM-014's replay, scoped to the buyer) | — |
| **Stock:** buying while signed in follows the same checkout and stock locking as a guest | — | — |

## Out of scope (owner's decision)

Email confirmation, password reset, profile editing, and linking past guest orders.

## Definition of done

- Acceptance criteria pass, written test-first.
- `run.py all` and the browser tests are green locally and on GitHub Actions.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
