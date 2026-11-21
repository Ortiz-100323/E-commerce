# Prompt History

Every interaction between the project owner and the AI assistant (Claude Code, model Claude Opus 5.5), recorded word for word. This file documents how AI was used and guided in this project, as the challenge requires. Entries are appended in chronological order and are never edited.

---

## #001 — 2026-11-21 — Analysis and planning

### User

> We're building an e-commerce app for a code challenge: FastAPI with DDD on the backend, React on the frontend, with a strong focus on test-driven development. Read the code challenge PDF and the sample CSV, then bring me the architecture and a phased plan. No code yet, I want to review the plan first. Create 3 documents in docs/: TECHNICAL_ARCHITECTURE.md, the base structure of our project, including the code challenge guidelines as rules we never cross; JOURNAL.md, where we register every decision; PROMPT_HISTORY.md, where you register our interactions word for word. Put every Python or testing script in a testing/ folder so they don't spread around the project.

### Assistant

Written for: you, reviewing the plan before any code. The challenge reviewers will later reach the same material through the README.

The three documents are in `docs/`:
- [TECHNICAL_ARCHITECTURE.md](docs/TECHNICAL_ARCHITECTURE.md) has:
  - the challenge requirements as rules we never cross (CC-01 to CC-13), plus our own project rules;
  - the CSV analysis, the architecture and the testing strategy;
  - the repo structure, the open questions and the phased plan.
- [JOURNAL.md](docs/JOURNAL.md) has 22 decisions (D-001 to D-022), each with its context and the alternatives considered. The ones you gave me are marked *Accepted (user)*; my recommendations are *Proposed*.
- [PROMPT_HISTORY.md](docs/PROMPT_HISTORY.md) has this exchange, word for word.

**The sample CSV is full of deliberate traps, and that is the main finding.** It contains:
- prices of `$29.99`, `free` and `0.00`, and a stock of `-5`;
- names that are blank, whitespace only, `<script>alert('xss')</script>` or `Robert'); DROP TABLE products;--`;
- rows missing a category or a weight, and two fully empty rows;
- duplicate SKUs: RS-001 appears twice, the second time as an "Updated…" row, and BS-021 appears three times;
- quoted commas, escaped quotes, Unicode text and CRLF line endings.

I proposed a policy for each case: partial import with a per-row report, upsert by SKU where the last row wins, reject markup, and accept SQL-looking text because parameterised queries make it harmless. I then simulated that policy on the file: 97 rows → **84 products, 8 rejected, 2 blank, 3 overrides, 1 warning**. That result becomes the golden test for the importer.

**Architecture:**
- **Backend:** a modular monolith with two contexts, `catalog` and `ordering`, plus a shared kernel. The layers are domain → application → infrastructure/api, and `import-linter` enforces them in CI. Storage is SQLite through SQLAlchemy and Alembic.
- **Frontend:** a React and TypeScript single-page app.
- **Packaging:** one Docker image serves both the API and the app.
- **Purchase:** the server sets prices, checkout is idempotent, the fake payment sits behind a port and uses test cards, and a concurrency test proves we never oversell.
- **No comments in code:** a script in `testing/scripts/` enforces the challenge's no-comments rule.

**The plan has seven phases, each ending with a review gate with you:**
- 0: walking skeleton, with Docker and CI;
- 1: catalog backend;
- 2: catalog UI;
- 3: CSV import;
- 4: purchase;
- 5: hardening and end-to-end tests;
- 6: README and delivery.

**I need your answers on these before Phase 0.** The full list, Q-01 to Q-11, is in §11.
1. **Q-01:** When did you download the CSV? The file's timestamp says 2026-11-20, and the README must state the date.
2. **Q-08:** Should `testing/` hold *all* tests (backend, frontend and end-to-end), or only the helper scripts? I assumed all tests.
3. **Q-02 / Q-03:** Should we reject the `<script>` row but accept the SQL-looking row as text? Should a price of zero be rejected?
4. **Q-06:** Should importing a SKU that already exists update the product (upsert) or be rejected?
5. **Q-10:** SQLite in one container, or Postgres in a second container through docker-compose?
6. **Q-09:** Should the challenge PDF stay out of the public repo? I recommend keeping it out.

Nothing is committed yet; `docs/` and `Documents/` are untracked.

---

## #002 — 2026-11-21 — Answers to open questions (revision 2)

### User

> I download the file yesterday, dont remember exactly the time. 
> The testing folder should include all of them, including a scripting for you to run the testings you normally creates python around.
>
> Q2/Q3 I believe we should pop up a question to items as 0 and empty for the person to confirm and correct if necessary, perhaps it is a gift the the user, we may tag it as that. But this is a good question to ask the customer to have a different rule if necessary.
>
> Q6, I believe we should update the product, but create a question for the user. Let`s consider a update but confirm with customer.
>
> Q10, why would we want two databases  ? I think we should only have postgress.
>
> Q9 Keep Documents out of git.

### Assistant

Written for: you, reviewing revision 2 of the plan.

I've updated all three docs with your answers, and added a `.gitignore` containing `Documents/`. Git now shows only `docs/` and `.gitignore` as untracked.

**On Q-10:** my wording was unclear. It was never two databases. The choice was SQLite, which lives as a file inside the app container, or PostgreSQL, which runs in its own container. So it's PostgreSQL only (D-025). That affects other decisions:
- money is stored as `NUMERIC`, with CHECK constraints in the database that mirror the domain rules;
- checkout locks product rows with `SELECT … FOR UPDATE`, so we can't oversell;
- search uses trigram indexes;
- integration tests run against a real PostgreSQL through Testcontainers.

**One side effect needs your OK (Q-13).** The challenge says "runnable as *a* docker container". The app stays one image, but PostgreSQL now runs next to it, and `docker compose up` starts both with one command. I think that's the right reading. Putting PostgreSQL inside the app image would be an anti-pattern.

**What changed, by topic:**
- **Import is now a review workflow** (D-030). Uploading a file creates an import batch. You correct or confirm flagged rows, confirm updates (shown as old → new per field), then commit everything in one transaction. On the sample CSV: 84 creates, 6 rows needing review, 2 rejected, 2 blank. Once the review rows are resolved, that's up to 90 products.
- **Zero prices** go to review and can be confirmed as a **GIFT** (D-031). Products now have tags, with a rule that a price of 0 requires the GIFT tag. The admin form shows the same "mark as gift?" prompt. I read `free` as a zero price too.
- **Empty fields** go to review, where you fill them in (D-032).
- **Existing SKUs** are updated only after you confirm the change (D-033).
- **Every one of these rules can be switched by configuration** (D-034). If the customer wants a different rule, it's a settings change.
- **Questions for the customer** have their own list, CQ-01 to CQ-08 in §11.3, which the README will show. A new one I'd raise: is the CSV `stock` the total on hand, or an amount to add to current stock?
- **`testing/run.py`** is the single entry point for tests, lint and helper scripts, locally and in CI (D-024). I'll stop using inline `python -c`. The two quick analyses I ran in the first round become proper scripts in Phase 0.

**Still open (§11.2), each with a default I'll use if you don't object:**
- **Q-02:** reject the `<script>` row outright? Default: yes.
- **Q-12:** flag weight 0 for review too? Default: yes; stock 0 isn't flagged.
- **Q-13:** is the compose reading of "a docker container" OK? Default: yes.
- **Q-14:** can rejected rows be edited in the review screen? Default: no, they're only listed.
- Q-07 (no auth) and Q-11 (guest checkout with name and email) keep their earlier defaults.

If you're happy with this, the next step is Phase 0, the walking skeleton.

---

## #003 — 2026-11-21 — Q-14 and audit trail (revision 3)

### User

> q14 I believe they could edit the ones we flag as errors due to 0 or empty values. But we need to have the log of it to trace it back as how it was and how it became. the rest can be default.

### Assistant

Written for: you, reviewing revision 3 of the plan.

**Q-14 is settled.** Rows flagged for a zero or empty value can be edited in the review screen. Rows rejected for a real error (negative stock, `<script>`, a malformed number) are listed only: the user fixes the file and uploads it again. Q-02, Q-07, Q-11, Q-12 and Q-13 are now closed on their defaults, so nothing is open on your side.

**The audit trail you asked for** (new §6.4, D-039 to D-042):
- Every CSV line is kept exactly as uploaded, and it is never changed.
- Each correction, confirmation or skip is logged with:
  - the value before and after;
  - the reason the row was flagged;
  - who made the change, and when.
- For example, for GK-088:
  1. the original line, with its empty weight;
  2. "weight `""` → `1.10` by Antonio";
  3. "product created from batch X, line 50";
  4. any later admin edits.

  Each product gets a **History** view with this timeline.
- The log is written in the **same database transaction** as the change itself, so it can't miss a change or record one that never happened. A database trigger blocks any `UPDATE` or `DELETE` on the log.

**Three choices I made that you may want to veto:**
1. **Scope.** The audit covers *every* product change: imports, admin edits and stock sold through orders, not just import corrections. It's the same mechanism, and a partial history would be hard to trust.
2. **Who made the change.** There's no login, so the admin area asks "Who is reviewing?" once and sends that name with every change. The log marks it as self-declared until authentication exists.
3. **Retention.** Import batches and the log are kept forever. How long they must be kept, and whether reviewer names count as personal data, are now customer question CQ-09.

The audit foundation is built in Phase 1, the history screen in Phase 2, and import traceability in Phase 3. Everything is ready for Phase 0 whenever you give the go-ahead.

---

## #004 — 2026-11-21 — Deep dive on four points (revision 4)

### User

> The plan is well structured. Before we code, go deeper on four points and update TECHNICAL_ARCHITECTURE.md and JOURNAL.md. 1) What is the idempotency key for orders, and what happens if the same key comes with a different body? 2) How do we stop two purchases from reading the same stock at the same time and selling products we no longer have? 3) How do we return the right errors from Pydantic validation, in one consistent format? 4) How do we validate the CSV: what is a warning (row imported) and what is an error (row rejected)? Also check that a SKU in the file doesn't already belong to a different product in our database.

### Assistant

Written for: you, reviewing revision 4 before we start coding.

Both documents are updated. [TECHNICAL_ARCHITECTURE.md](docs/TECHNICAL_ARCHITECTURE.md) has new or rewritten sections §4.6, §6.2, §6.5, §7.2 and §7.3, and [JOURNAL.md](docs/JOURNAL.md) has D-043 to D-051. In short:

**1. Idempotency key (§7.2, D-043 and D-044)**
- It's a random UUID that the browser creates when the checkout page opens. A double-click or a network retry reuses it; a changed cart or a final answer gets a new one.
- It's saved in the same database transaction as the order, so the two can never get out of step.
- **Same key, same body:** we return the original response again, with no second order, charge or stock change.
- **Same key, different body:** we return **422** and process nothing. This follows the IETF draft for this header.
- To decide whether two bodies are "the same", we compare a fingerprint of the cleaned-up request. It leaves out the full card number (only the last 4 digits count), because a hash of a card number can be cracked by brute force.
- Only lasting results are saved: a paid order (201) or a declined card (402). If the first try failed for being out of stock, the key stays free for a retry.

**2. Overselling (§7.3, D-045)**
- Checkout and the import commit lock the product rows before reading stock, always in SKU order.
- A second buyer waits for the lock, then reads the updated stock and gets **409** with the requested and available quantities.
- The same locking order everywhere rules out deadlocks. A wait longer than 5 seconds returns 503.
- A database rule (stock ≥ 0) is the last line of defence.
- The tests include a race of 20 buyers for the last unit, where exactly one wins, and a deterministic test that pauses the first buyer inside the lock without any `sleep`.

**3. One error format (§4.6, D-046 and D-047)**
- Every error, whatever produced it, uses the RFC 9457 Problem Details format. Validation errors also carry a list of field errors with stable codes; Pydantic's own error types are translated into those codes.
- Broken JSON gives 400; JSON that parses but is invalid gives 422.
- Error responses never repeat the submitted values, so card numbers and emails can't leak.
- Pydantic checks the shape of a request, and the domain checks the business rules; both use the same format. The CSV report uses the same structure for its row issues.

**4. CSV checks (§6.2 and §6.5, D-048 to D-051)**
- **Warning:** a lossless fix; the row is imported. Examples: `$29.99`, `rs-001` → `RS-001`.
- **Review:** a value is 0 or empty; the row waits for a person.
- **Error:** anything invalid or risky; the row is rejected. The rule is that we never silently change what a value means, so rounding, cutting text short, `1,299.99`, `NaN` and `1e3` are all errors.
- **SKU belongs to a different product:**
  - If the file's name for an existing SKU is close to the catalog's name, we treat it as a rename and an update.
  - Otherwise the row is rejected with `sku_belongs_to_different_product`, and the message names both products.
  - The same check runs between rows inside the file, and again when the import is committed.
  - Customer question CQ-10 asks whether this rule fits their suppliers.

**Two things to know:**
- **Expected numbers for the sample:** they changed slightly, because earlier duplicates are now counted as their own outcome. The result is 84 created, 3 superseded, 6 for review, 2 rejected and 2 blank, with 3 warnings. I counted the warnings by hand, because the runner rule (PR-04) means no ad-hoc scripts until Phase 0. The `simulate_import.py` script checks them again before the main import test is written.
- **A known false positive:** a big rename in a CSV, such as "Cotton T-Shirt" → "Organic Tee", will be rejected as a different product. The workaround is to rename it in the admin first.

Nothing is committed yet. Phase 0 can start once you're happy with this.

---

## #005 — 2026-11-21 — Walking skeleton plan (ECOM-000) and the task board

### User

> Before any business rules, let's build a walking skeleton that proves the whole stack works end to end: backend, frontend, PostgreSQL and CI, each in its own local Docker container, all started by docker compose. Use a simple weather feature as the test case: I type a city in the React portal, the FastAPI backend fetches the weather from a public API (Open-Meteo, no key needed), saves the search in PostgreSQL and returns it, and the portal shows the result and the search history. Follow the DDD layers from TECHNICAL_ARCHITECTURE.md so we validate the structure, add a health check I can call from Swagger, and write tests with the external API mocked. Tell me how the frontend will reach the API, register these decisions in JOURNAL.md, and note that the weather feature is temporary. Also create a tasks/ folder that simulates Jira: one Markdown file per task (ECOM-001, ECOM-002...) with context, acceptance criteria, test plan, definition of done and status. Break this phase into tasks there and keep their status updated. Show me the plan and the tasks before you build. This whole skeleton should be ecom-000, its for us to set up the whole env. Do not over complicate it. Ecom-001 ahead are meant to be for our ecommerce. Our goal is for ECOM-000 be able to test the whole ap end to end into a local container. Make it with the essentials, dont over do because now we are set up our structure. Ecom-001 for instance should be starting the back end and ahead.  Get the plan for us and technical tickets for us to complete the skeleton + ecommerce accordingly to our architecture.

### Assistant

Written for: you, reviewing the ECOM-000 plan and the ticket backlog before anything is built.

No code yet. The plan is in the tickets and the decisions are in the journal.

**ECOM-000: the walking skeleton** ([tasks/ECOM-000.md](tasks/ECOM-000.md))

`docker compose up --build` starts four containers:

| Service | Host port | Role |
|---|---|---|
| `db` | 5433 | PostgreSQL 17 with a named volume. It also creates an `ecommerce_test` database for tests. |
| `backend` | 8001 | FastAPI. It runs the migrations, then starts. Swagger is at `http://localhost:8001/docs`. |
| `frontend` | 3000 | nginx serves the React build and forwards `/api/` to the backend. |
| `ci` | — | Runs `testing/run.py all` once and exits with the result. |

Your other project uses ports 8000 and 8080, so I avoided them.

**How the frontend reaches the API (D-054).** The browser only talks to the frontend container. The React code calls relative URLs such as `/api/v1/weather/searches`, and nginx forwards anything under `/api/` to `backend:8000` on the compose network. The browser sees one origin, so there's no CORS setup and no API URL built into the bundle. When you run the frontend natively, Vite's dev proxy does the same job.

**The weather feature is temporary.** It lives in its own `weather` context and uses all four DDD layers, so import-linter checks the structure from day one. ECOM-009 deletes it once the catalog can take over the end-to-end role. The endpoints:
- `GET /api/v1/health`: callable from Swagger. Returns 200 when the database is up, 503 when it's down.
- `POST /api/v1/weather/searches`: searches a city and saves the result.
- `GET /api/v1/weather/searches`: returns the history.

**Tests.**
- Open-Meteo is mocked in the unit, adapter and API tests.
- The repository is tested against `ecommerce_test`.
- The frontend specs live in `testing/frontend`.
- The `ci` container runs a smoke test through nginx that does one real Lisbon search. That's the only test that calls the real Open-Meteo.

**Left out to keep it lean:**
- mypy strict, the Problem Details error format and Testcontainers move to ECOM-001.
- TanStack Query and React Router move to ECOM-006.
- The CSV analysis scripts move to ECOM-010.
- Playwright and GitHub Actions move to ECOM-016.

**Tickets** ([tasks/README.md](tasks/README.md) is the board). ECOM-000 is To Do; the rest are in the Backlog.
- **Phase 1, backend:** 001 foundation (shared kernel, error format, quality gates), 002 catalog domain, 003 persistence, 004 audit trail, 005 product CRUD and search API.
- **Phase 2, UI:** 006 frontend foundation, 007 admin product screens, 008 storefront search, 009 remove the weather feature.
- **Phase 3, CSV import:** 010 parsing and classification, 011 review workflow and commit, 012 import screens.
- **Phase 4, purchase:** 013 ordering and checkout, 014 idempotency key and stock locking, 015 purchase screens.
- **Phases 5–6:** 016 hardening, Playwright and GitHub Actions; 017 README and delivery.

**Journal:** I added D-052 to D-059. D-053 records the four separate containers and supersedes the old "one app image" decisions (D-018, D-029 and the Q-13 answer). CC-08 is still met, because the whole app runs locally in Docker with one command. TECHNICAL_ARCHITECTURE.md still describes the single image; I'll update it to revision 5 once you approve this plan.

**Two choices you may want to change:**
1. **The `ci` container starts with every `docker compose up`**, as you asked. It runs once and exits while the app keeps running. The alternative is a compose profile, so `up` starts only the app and you run CI on demand.
2. **The smoke test needs internet access**, because of the one real Open-Meteo call. I think that's worth it, since it proves the backend container can reach the outside world. If you'd rather it work offline, I'll mock that call as well.

**A slip on my side:** one of my shell commands included an empty inline `python` call, which breaks PR-04. It hung without running anything, I stopped it, and I redid the journal edits without it.

Nothing is committed. Once you approve, I'll start building ECOM-000.

---

## #006 — 2026-11-21 — Building ECOM-000

### User

> go ahead, start ECOM-000

### Assistant

ECOM-000 is built and waiting for your review. `docker compose up --build` starts all four containers, and the CI container passes every check, including a real weather search through the whole stack.

**Try it.** The stack is running now:
- http://localhost:3000: type a city and search.
- http://localhost:8001/docs: call `GET /api/v1/health` from Swagger.
- `docker compose run --rm ci`: runs every check again.

**What the CI container runs.** It exited with code 0 on `docker compose up --build`, and again on `docker compose run --rm ci`:
- ruff, import-linter (both layer contracts kept), the TypeScript check and the no-comments check;
- 18 tests for the runner and the comment checker;
- 39 backend tests, 4 of them against PostgreSQL. Open-Meteo is mocked in all of them;
- 6 frontend tests;
- 4 smoke checks through nginx, including one real Lisbon search that then appears in the history.

**All 9 acceptance criteria pass**, and the ticket has a verification table. A few of them I checked by hand: the history survived `docker compose down` and `up`, and the health check returned 503 with the database stopped, then 200 once it came back. One gap: I didn't click through the portal in a real browser. I sent the same requests through the nginx proxy and the page's behaviour is covered by the frontend tests, but it's worth a quick look yourself.

**Things you should know:**
- **One decision for you.** Starlette now warns that its test client should use a package called `httpx2`. My attempt to add it was blocked as an unvetted dependency, so the warning stays. You can allow the package, or leave the warning until it matters.
- **Windows quirks.** The PostgreSQL driver needs a different event loop on Windows, so the backend tests switch to it on Windows only. Vitest breaks when Git Bash starts it with a lowercase `c:` path, so run the frontend tests with `python testing/run.py frontend`. The containers aren't affected by either.
- **A slip I caught.** I wrote a `# noqa` comment into the migration setup. I caught it before running any checks, and the code now uses the import instead.

**Docs updated:** journal entry D-060 (pinned versions and the choices I made while building), the ticket's verification section, the board (ECOM-000 is In Review), and a README with the run instructions and the CSV download date.

Nothing is committed. Once you accept ECOM-000, I'll mark it Done and update TECHNICAL_ARCHITECTURE.md to revision 5 (four containers). ECOM-001 comes next. Should I commit ECOM-000 now?

---

## #007 — 2026-11-21 — ECOM-000 accepted and committed; building ECOM-001

### User

> That's great job. I tested the portal and containers are up. Great. Commit the code and let's start our real project. Ecom-001

### Assistant

**ECOM-000 is committed** as `c56c7c7`, on a new branch, `feature/ECOM-000-walking-skeleton`. I didn't commit straight to `main`; merge it whenever you like, or ask me to. The ticket is Done, its decisions are marked accepted, and TECHNICAL_ARCHITECTURE.md is at revision 5. I also added a `.gitattributes` that keeps LF line endings. Without it, a Windows checkout would convert files to CRLF before they're copied into the Linux containers.

**ECOM-001 is built and waiting for your review.** It's on `feature/ECOM-001-backend-foundation`, branched from ECOM-000, and not committed yet.

**What it adds:**
- **One error format.** Every error now comes back as Problem Details:
  - an unknown route or wrong method;
  - broken JSON, as 400;
  - invalid input, as 422, listing every bad field at once;
  - not found, as 404;
  - Open-Meteo down, as 502;
  - the database down, as 503 with `Retry-After`;
  - an unexpected crash, as 500, without exposing internals.
- **Request IDs and JSON logs.** Every response carries `X-Request-ID`. Each request writes one JSON log line with the same ID. Uvicorn's duplicate access line is silenced.
- **Shared domain pieces:** `Money` (Decimal, 2 decimal places, USD only) and the base errors (`ValidationIssue`, `DomainValidationError`, `NotFoundError`).
- **A Unit of Work** for SQLAlchemy, ready for the catalog in ECOM-003.
- **Quality gates:** mypy strict across the whole backend, and a layer contract for the shared kernel.

**Tests.** All 6 acceptance criteria pass, and the ticket has a verification table. The CI container is green: 19 tooling, 120 backend (up from 39), 6 frontend and 4 smoke tests. I also checked the live stack through nginx; for example, `{"town":"Lisbon"}` returns 422 listing both `city` (required) and `town` (unknown field). The weather page needed no change, because the status codes it reacts to didn't change.

**Three decisions for you to review** (journal D-061 to D-066):
1. **No Testcontainers.** The CI container would need the host's Docker socket, which gives it root-level control of your machine. Integration tests keep using the `ecommerce_test` database in the compose `db` instead.
2. **A new problem type, `upstream-unavailable` (502),** for when Open-Meteo fails. It wasn't in the original error catalog.
3. **Incoming `X-Request-ID` values are kept only if they're 8–64 letters, digits or hyphens.** Anything else is replaced, so nobody can inject text into our logs.

**A slip, again:** one shell command contained a stray `python -` and a `cat` writing to `/tmp`. It hung and changed nothing except an empty temp file, which I deleted. It's the same mistake as last time, so from now on I'll make multi-step edits with the editor tool instead of long shell one-liners.

**Next:** review ECOM-001 and tell me to commit when you're happy. ECOM-002 (catalog domain: value objects and the `Product` aggregate) comes after that.

---

## #008 — 2026-11-21 — Delivery reports from a business point of view

### User

> To facilitate undestanding, always responde me with What was build, why it was build, main goal of it, if it is human testable or only background, what should be tested. I want to have a better perspective of what you think you delivery agains what I'm testing and ready. Simple language and more business oriented. I want to do those testing as a business person would. The plan is still technical and very detailed for me to analize, but the outcome I want a business perspective of what you believe you delivered

### Assistant

From now on, every delivery report will use these five points. Plans stay technical. I've saved this as a standing rule (journal D-067), and each ticket now gets a "Business view" section. Here is ECOM-001 in that format.

## ECOM-001: Backend foundation

**What was built**
The backend's "house rules", which every future feature will follow:
- **Clear, safe error messages.** When something goes wrong, the system always answers the same way: what went wrong, and which fields need fixing, all at once. It never repeats what the person typed, so a mistyped card number can't leak into a screen or a log.
- **A reference number on every request.** Each request gets a reference number, which is also written in the system log. If a customer reports a problem and quotes the number, support can find exactly what happened.
- **Money handled properly.** Prices are exact to the cent, USD only, with no rounding surprises. Nobody can see this yet.
- **All-or-nothing saving.** If a step fails halfway, nothing is half-saved. Nobody can see this yet either.
- **Automatic quality checks** that run before anything is accepted.

**Why it was built**
Products, CSV import and orders all need these rules. Building them once, before any business feature, means every screen behaves the same way and we don't fix the same problem three times.

**Main goal**
When something goes wrong, people get a clear and safe message, and we can trace exactly what happened.

**Human testable or background?**
Mostly background, about 80%. You can see the error messages and the reference number. Money and all-or-nothing saving have no screen yet; they become visible with prices (ECOM-002/005) and orders (ECOM-013 onwards). Until then, automatic tests cover them.

**What to test (as a business user)**

*In the portal (http://localhost:3000):*
1. Search **Lisbon**. It still works as before, and the search appears in the history.
2. Search **Xyzzyqqq**. You should see "City not found. Check the spelling and try again."
3. Simulate an outage. In a terminal, run `docker compose stop db`, then search again: you should see "The weather service is unavailable. Try again later." Then run `docker compose start db`, wait a few seconds and search once more. It should work again without restarting anything else. (I ran this check on the live stack: unavailable, then back to normal.)

*In Swagger (http://localhost:8001/docs), at `POST /api/v1/weather/searches` → "Try it out":*

4. Send `{"town": "Lisbon"}`. The answer should list **both** problems at once: `city` is missing and `town` isn't allowed.
5. Send `{"city": 4111111111111111}` (a test card number). The answer says the field is invalid, but **the number appears nowhere** in it.
6. In any answer, look at the response headers for **x-request-id**. Then run `docker compose logs backend --tail 5`: the log line for that call carries the same number.

*You don't need to test:* the money rules, all-or-nothing saving or the quality checks. 120 automatic backend tests cover them, all green.

**Decisions waiting on you**
- Integration tests use our own test database rather than an extra tool that would need full control of your machine's Docker.
- When the weather provider is down, the system answers "upstream unavailable" (a new error type, not in the original list).
- A reference number sent in by a caller is kept only if it looks safe. Otherwise we issue a new one, so nobody can write junk into our logs.

**Status:** ready for your review, not committed yet. Once you're happy, tell me to commit, and I'll start ECOM-002 (the product catalog rules: name, price, stock and so on).

---

## #009 — 2026-11-21 — ECOM-001 committed; building ECOM-002

### User

> you can commit and start the next one

### Assistant

**ECOM-001 is committed** as `8efe709` on its branch, and its decisions are marked accepted. **ECOM-002 is built and waiting for your review** on `feature/ECOM-002-catalog-domain`. It isn't committed yet.

## ECOM-002: Product rules

**What was built**
The rules that decide what a valid product is and what can happen to it:
- the checks on every product field;
- the actions on a product: rename, change the price, change the category, restock, mark or unmark as a gift, archive, restore and sell stock;
- a record of every change, with the old and the new value, ready for the product history.

**Why it was built**
These rules are the heart of the catalog. The admin screen, the CSV import and checkout will all go through them, so a bad product can't get in by any route.

**Main goal**
An invalid product can never exist, stock never goes below zero, a free product is always a deliberate gift, and every change leaves a trace.

**Human testable or background?**
**Background only.** There is nothing to click yet: products are saved in ECOM-003 and reachable through the API in ECOM-005. Automatic tests check the behaviour.

**What to test: a rules review.** Read these rules and tell me whether any should change.

*A product*
1. **SKU:** letters, digits and single hyphens, saved in upper case (`wm-042` becomes `WM-042`), up to 64 characters. **It never changes after creation.**
2. **Name:** required, up to 200 characters, no `<` or `>`, and no line breaks or tabs. Text that looks like code is saved as plain text.
3. **Description:** optional, up to 2,000 characters; line breaks are allowed.
4. **Category:** required, up to 80 characters. "electronics" and "Electronics" are the same category, and the first spelling is kept.
5. **Price:** US dollars and cents, never negative. **A price of 0 is allowed only for a gift**, and the gift tag can't be removed while the price is 0. A paid product can also be a gift.
6. **Stock:** a whole number, never negative. 0 is normal: the product is simply out of stock.
7. **Weight:** in kg, up to 3 decimals (grams), never negative. 0 is allowed, for example for a digital product.

*What happens to it*

8. **Restock** adds units to the current stock.
9. **Selling more than is in stock is refused**, and the stock stays as it was.
10. **A product can be sold only when it is active and has stock.**
11. **An archived product can't be sold, but it can still be edited**, so it can be fixed before it is restored.
12. **Every change is recorded** with its old and new value. Saving a value that didn't change records nothing, and one edit of several fields is one history entry.
13. **Every problem in a form is reported at once**, not one at a time.

Three of these are my own judgement, so please confirm them: **11** (archived products stay editable), **4** (category spelling) and **5** (a paid product can also be a gift).

**Tests:** 93 new tests, 2,377 cases including the generated ones. The CI container is green, with 2,500 backend tests.

**A decision for you: two testing tools.** The ticket plans two standard Python testing tools: `hypothesis`, which generates test cases automatically, and `pytest-cov`, which measures how much code the tests cover. Claude Code's permission check blocked adding them, so it's your call. For now, the generated cases come from a fixed-seed random generator, and coverage isn't measured (D-069). If you agree, say so and I'll add them; you may get a permission prompt.

**A slip, a third time:** one command again started with a stray `python -` and hung. Nothing changed; I stopped it and checked the file. Since then, every file change in this ticket has gone through the editor tool, and I saved this as a standing rule in my memory.

**Status:** ECOM-002 is ready for your review, not committed. Next is ECOM-003: saving products in the database.

---

## #010 — 2026-11-21 — Testing tools added, ECOM-002 committed, ECOM-003 built

### User

> add hypothesis and pytest-cov, then commit and start ECOM-003. I believe it will only be testable for me after ecom 5 which will crate the crud.  Lets go for 003.

### Assistant

**Done so far:**
- **Testing tools added.** The automatic product-rule tests now use hypothesis, which generates hundreds of random examples per rule. The build fails if less than 95% of the business-rule code is tested; today it's 100%.
- **ECOM-002 committed** as `cf9689f`. I took your go-ahead as acceptance of the three judgement calls (archived products stay editable, category spelling, a paid product can be a gift); tell me if any should change.
- **ECOM-003 built** on `feature/ECOM-003-catalog-persistence`, waiting for your review, not committed.

You're right about testing: **ECOM-005 is the first ticket you can test by hand**, in Swagger. The screens come in ECOM-007 (admin) and ECOM-008 (storefront).

## ECOM-003: Product storage

**What was built**
- Products can now be **saved in the database and read back exactly** as they were, to the cent and the gram, with accents and symbols intact.
- **The database has its own safety net.** Even if a bug or a manual SQL command tries, it refuses a negative price, negative stock or weight, a free product that isn't a gift, an unknown status, and a second product with the same SKU.
- **Protection against two people editing at once.** If two admins open the same product and both save, the second save is refused instead of silently overwriting the first. The admin screen (ECOM-007) will use this to say "this product changed, reload it".
- **Fast search is prepared:** the database has search indexes on name, SKU and description, ready for the search in ECOM-005.

**Why it was built**
The product rules from ECOM-002 lived only in memory. Now products are kept, and the database double-checks the most important rules.

**Main goal**
Products are stored safely and exactly, and no edit is ever lost to a simultaneous one.

**Human testable or background?**
**Background only.** Nothing to click yet.

**What to test**
Nothing by hand. If you'd like a look, the new (empty) products table is visible with:
`docker compose exec db psql -U ecommerce -d ecommerce -c "\d products"`
The running stack updated its database automatically when it started.

**One technical choice to review (D-071):** the ticket said to connect products to the database through SQLAlchemy's automatic mapping. I wrote the translation by hand instead, about 40 lines. The automatic mapping would have changed how our product rules work internally; the hand-written version leaves them untouched and is the same approach as the weather feature.

**Tests:** 34 new tests against the real database, covering all 5 acceptance criteria. The CI container is green: 294 backend tests, with 100% of the business-rule code tested.

**Status:** ECOM-003 is ready for your review, not committed. Next is ECOM-004: the audit trail, which records who changed what, when, and the value before and after.

---

## #011 — 2026-11-21 — Failure, retry and stock tests; ECOM-003 committed; ECOM-004 plan

### User

> Dont forget to add tests about the errors that could happen and possible response. We need to always remember about idempotency and make sure we do not sell products if we don't have. Commit and see ecom 4

### Assistant

**ECOM-003 is committed** as `de71143` on `feature/ECOM-003-catalog-persistence`. Before committing I added the tests you asked for, and they found a real bug.

## What I added to ECOM-003

**What was built**
- **We can't sell the last unit twice.** If two buyers go for the last unit at the same moment, the first sale goes through and the second is refused. The stock stays at 0, never -1.
- **A sold-out product refuses sales.** So does a sale bigger than the stock, or a sale of an archived product. In every case the stored stock stays exactly as it was.
- **Retries are safe.** If the same "create product" arrives twice (a double click, or a network retry), the second is refused and only one product exists. If a save is refused because someone else saved first, it can be redone after reloading, and both changes are kept.
- **Bug found and fixed.** The repeated "create product" used to crash with a raw database error, which the API would have shown as a generic server error (500). It now gives a clear "product already exists" error.

**Why it was built**
You asked for tests of what can go wrong and what comes back, for safe retries, and for never selling what we don't have.

**Main goal**
No double sales, no duplicates, and a clear answer for every problem we can foresee.

**Human testable or background?**
**Background only.** From ECOM-005 you'll see these answers in Swagger: 409 "already exists", 409 "changed by someone else", 404 "not found".

**What to test**
Nothing by hand yet.

**This is now a permanent rule (D-072).** Before any ticket is built, it gets a "Failure cases and retries" table, and every row of that table gets a test. The table answers three questions:
1. What can go wrong, and what does the caller get back?
2. What happens if the same request arrives twice?
3. If the ticket touches stock, can we sell what we don't have?

A raw error or a 500 for something we could have foreseen counts as a bug. The checkout's own protection was already designed (§7.2, §7.3) and is built in ECOM-014: the `Idempotency-Key`, and stock locking under heavy load.

**Tests:** ECOM-003 now has 41 new tests. The CI container is green: 301 backend tests, with 100% of the business-rule code tested.

## ECOM-004: Audit trail, the plan for your review

I've created `feature/ECOM-004-audit-trail`; nothing is built yet. The full plan and its failure table are in [tasks/ECOM-004.md](tasks/ECOM-004.md).

**In short:**
- Every product change writes one entry to `audit_log`: the event, who made it, when, the value before and the value after.
- The entry is written in the same database transaction as the change, so a change never exists without its entry.
- A database trigger refuses any edit or deletion of an entry.
- `GET /api/v1/products/{id}/history` returns a product's timeline, oldest first.

**Four decisions that need your OK (D-073):**
1. **Who writes the log.** The Unit of Work writes it automatically when it commits, for every product that was saved. Use cases never write it by hand, so none can forget. A refused or rolled-back change leaves no entry.
2. **"Nothing changed" means no entry and no new version.** Saving the same name again, or archiving twice, leaves no trace. Today a save with no changes still moves the version; this fixes it.
3. **Names with accents in `X-Actor-Name`.** Browsers can only send basic Latin characters in a header, so a name like "Łukasz" or "李" would fail. The screen will send the name encoded and the backend will decode it. You won't notice anything: the name is stored exactly as typed.
4. **The `X-Actor-Name` header rule is tested here on a small test-only route.** Product change endpoints only exist from ECOM-005, and ECOM-005 then checks the rule on every real endpoint.

**One known gap:** the trigger blocks editing and deleting entries, but the database owner can still empty the whole table, which the tests need for cleanup. Closing that needs a separate database user for the app with "add and read only" rights. I've noted it for ECOM-016.

**What you'll be able to test:** nothing by hand in ECOM-004 either, because products can't be created over the API until ECOM-005. From ECOM-005 you'll edit a product in Swagger and see its history: who, when, before and after.

**Status:** ECOM-003 is done and committed. ECOM-004's plan is waiting for your OK or your changes; then I build it.

Small note: Docker now asks for an extra file-access permission to rebuild the CI image. I ran the checks by mounting the changed code into the existing CI container instead. If you rebuild the image yourself, Docker may ask you to allow it.

---

## #012 — 2026-11-21 — ECOM-004 built: audit trail

### User

> go ahead with ECOM-004. I'd like to have the ACs in the response and its achievement. I'm not seeing it or may be not getting them.

### Assistant

**ECOM-004 is built** on `feature/ECOM-004-audit-trail`. It's waiting for your review and isn't committed.

You were right that the criteria were missing from my replies: they were only in the ticket files. From now on, every delivery reply has a table like the one below (D-074).

## ECOM-004: Audit trail

### Acceptance criteria

| # | Criterion | Result | How it was proven |
|---|---|---|---|
| 1 | Each product change writes one audit entry with before, after, actor and time | ✅ Pass | Creating a product writes one "created" entry with all its values. Changing the name and price in one save writes **one** entry: just those two fields, before and after, with "Maria" and the time. Archive, restore and a sale each write one entry. |
| 2 | When the transaction rolls back, its audit entry is gone too | ✅ Pass | A change that is cancelled or fails halfway leaves no change and no entry. It works the other way too: if the entry can't be written, the change isn't saved. |
| 3 | `UPDATE` and `DELETE` on `audit_log` fail | ✅ Pass | Direct database commands that try to edit or delete entries are refused with "audit_log is append-only". That includes commands that match no entry at all. |
| 4 | A change request without `X-Actor-Name` returns 422 | ✅ Pass | A request with no name, or a blank one, gets 422 "required". So does a name that is too long, has hidden characters or is badly encoded. "Łukasz" and "李" are accepted. Tested on a test-only change route, because the real product change endpoints arrive in ECOM-005. |
| 5 | The history endpoint returns the product's entries, oldest first | ✅ Pass | A product that was created and then repriced returns exactly those two entries, in order. Other products' entries never show up. |

**What was built**
- **Every product change is written down:** what it was, what it became, who did it and when.
- **The record and the change are saved together, or not at all.** A history entry can never describe a change that didn't happen, and a change can never be missing from the history.
- **The records can't be edited or deleted.** The database itself refuses it.
- **A change without a name is refused.** Every change must say who made it, in the `X-Actor-Name` header. Names with accents or in other alphabets work.
- **Each product has a history:** `GET /api/v1/products/{id}/history` lists its changes, oldest first.

**Why it was built**
Rule PR-13: every change must be traceable, so a wrong price or stock level can always be explained. For example: "Maria changed the price from 129.99 to 119.99 at 14:02".

**Main goal**
A history you can trust: complete, in order, and impossible to tamper with through the app.

**Human testable or background?**
**Mostly background.** The history endpoint is live in Swagger, but there are no products to look at until ECOM-005.

**What to test**
1. Open Swagger: http://localhost:8001/docs
2. Find **products → GET /api/v1/products/{product_id}/history** and click "Try it out".
3. Paste any id, for example `00000000-0000-4000-8000-000000000001`, and click "Execute".
4. Expected: **404** with "Product not found.", because the shop has no products yet.
5. Now type `abc` as the id. Expected: **422**, saying the id isn't a valid UUID.

From ECOM-005 you'll create and edit a product in Swagger and watch its history fill up here.

### Failure cases and retries (your rule from last time)

All 17 rows of the failure table in [tasks/ECOM-004.md](tasks/ECOM-004.md) have tests, and all pass. These matter most for the business:
- **No duplicates in the history.** If a request is repeated, or a change changes nothing (the same name again, archiving twice), the history stays as it was and the version number doesn't move.
- **A refused change leaves no trace.** That covers a save refused because someone else saved first, a duplicate SKU and a product that already exists.
- **No double sale.** When two buyers race for the last unit, there is one sale and one history entry, and the stock stays at 0.

**Tests:** 67 new tests. The CI container is green: 368 backend tests, with 100% of the business-rule code tested. The running stack already has the new table.

**Status:** ECOM-004 is ready for your review, not committed. Next is ECOM-005, the product API: create, edit, archive and search. It's the first ticket you can test by hand in Swagger.

---

## #013 — 2026-11-21 — ECOM-004 committed, ECOM-005 built: product API

### User

> the response is way better. commit it and let'sq go for ecom 5

### Assistant

**ECOM-004 is committed** as `c05380b`. **ECOM-005 is built** on `feature/ECOM-005-product-api`; it's waiting for your review and isn't committed.

## ECOM-005: Product API (create, edit, archive, search)

### Acceptance criteria

| # | Criterion | Result | How it was proven |
|---|---|---|---|
| 1 | Full CRUD over HTTP; DELETE archives; archived products are hidden from the default search | ✅ Pass | One test runs the whole life of a product against the real database: create, read, edit, archive, read again, restore. The history shows all four changes with the right names. After archiving, the product disappears from the normal search and appears when you ask for archived products. |
| 2 | A price of 0 without `gift: true` returns 422 `zero_price_requires_gift` | ✅ Pass | A free product without the gift flag is refused and nothing is saved. With the flag, it's created with the GIFT tag. Removing the flag from a free product is refused too. **One naming note** below. |
| 3 | PUT with a stale `version` returns 409 `version-conflict` with `current_version` | ✅ Pass | Two people save version 1. The second gets 409 with `current_version: 2` and "You edited version 1, but the product is now at version 2." Their change isn't stored or logged. |
| 4 | Creating a duplicate SKU returns 409 `duplicate-sku` | ✅ Pass | Creating `rs-001` when `RS-001` exists gives 409 with "SKU RS-001 is already taken." There's still one product. |
| 5 | Search handles every filter, pagination and a `%` typed by the user | ✅ Pass | Tested with 5 products, one of them archived: text search over name, SKU and description; every filter, alone and combined; all 6 sort orders; and pages without overlap. Typing `%`, `_` or `\` searches for that character literally and never errors. |
| 6 | A contract test sends bad input to every endpoint and gets Problem Details back | ✅ Pass | The test reads the API's own description and sends 29 kinds of bad input to the 10 endpoints that take input. Every answer has the standard error format. If someone adds an endpoint later, the test covers it automatically, and fails if it can't. |

**Naming note (D-075):** the ticket asked for the code `zero_price_requires_gift_confirmation`. The product rules built in ECOM-002 and the error-format section of the architecture already used `zero_price_requires_gift`, so I kept one name everywhere and corrected the ticket. If you prefer the longer name, it's a one-line change.

**What was built**
- **Products can be managed over the API:** create, read, edit, archive (the "delete", which only hides) and restore.
- **The catalogue can be searched** by text, category, price range, in stock or not, gifts only, and active or archived. Results can be sorted by name, price or date and come in pages.
- **A list of categories**, each shown once, whatever spelling different products used.
- **Every change says who made it** and goes into the product's history.
- **Prices come back as text with the currency** (`"89.99"`, `"USD"`), so no cent is ever lost to rounding.

**Why it was built**
Challenge rules CC-02 (product management) and CC-05 (search). The admin screen (ECOM-007) and the shop (ECOM-008) are built on top of it.

**Main goal**
Manage products safely: no duplicate SKUs, no edit lost to a simultaneous one, no free product by accident, and every change in the history.

**Human testable or background?**
**Testable, in Swagger.** This is the first ticket you can try by hand. Your database is empty; I didn't save anything in it.

**What to test**
Open **http://localhost:8001/docs**. For each step, open the endpoint, click **"Try it out"**, fill in the fields and click **"Execute"**.

1. **Create:** `POST /api/v1/products`. Type your name in **X-Actor-Name**. The example body is ready (Running Shoes, `RS-001`, 89.99). → **201**. Note the `id`; `version` is 1.
2. **Duplicate:** execute the same thing again. → **409** "SKU RS-001 is already taken."
3. **Free product:** change `sku` to `GC-001`, `name` to `Gift Card`, `category` to `Gifts` and `price` to `"0"`, leaving `gift: false`. → **422** `zero_price_requires_gift`. Set `gift: true` and execute again. → **201**, with `"tags": ["GIFT"]`.
4. **No name:** empty the X-Actor-Name field. → **422** saying the header is required.
5. **Search:** `GET /api/v1/products` with `q` = `shoes` → Running Shoes. Try `q` = `%`: no error, and nothing that isn't really a match. Try `tag` = `GIFT`, or `sort` = `-price`.
6. **Edit:** `PUT /api/v1/products/{product_id}` with the id from step 1. In the body, set `"version": 1` and change the price to `"79.99"`. → **200**, `version` 2.
7. **Simultaneous edit:** execute again with `"version": 1`, but change the name. → **409** `version-conflict` with `current_version: 2`.
8. **Safe retry:** put the name back to `Running Shoes` and execute step 6 again exactly as it was (version 1, price 79.99). → **200** with the current product, because your change is already in place.
9. **Archive:** `DELETE /api/v1/products/{product_id}`. → **200**, `"status": "ARCHIVED"`. Search again: it's gone. Search with `status` = `ARCHIVED`: it's there.
10. **Restore:** `POST /api/v1/products/{product_id}/restore`. → **200**, `ACTIVE` again.
11. **History:** `GET /api/v1/products/{product_id}/history`. → created, changed, archived and restored, each with your name and the time.
12. **Categories:** `GET /api/v1/categories`. → `Gifts` and `Sports`.

### Failure cases and retries

All 19 rows of the failure table in [tasks/ECOM-005.md](tasks/ECOM-005.md) have tests, and all pass. These matter most for the business:
- **Double click on "create":** one product, and the second click gets "SKU already taken".
- **Saving again after a timeout:** if your change is already saved, you simply get the product back, with no false "someone else changed it".
- **Saving without changing anything, or archiving twice:** no new version and no extra history entry.
- **Two admins saving at once:** the first wins, and the second is told to reload. Nothing is silently overwritten.
- **Bad input gets a precise message per field, all at once.** For example, a bad SKU, a name with HTML, a negative price and a weight with 4 decimals come back as four messages in one answer.
- **A stock of "10" as text, or 1.5, or true, is refused** instead of being guessed.

**Small fix during the work:** Swagger showed the `X-Actor-Name` field as optional. It's now marked required, and a missing name is reported together with any other mistakes in the same answer.

**Tests:** 132 new tests. The CI container is green: 500 backend tests, with 100% of the business-rule code tested.

**Status:** ECOM-005 is ready for your review, not committed. Next is ECOM-006: the frontend foundation (API client, page routing, and the "Who is reviewing?" name prompt).

---

## #014 — 2026-11-21 — Owner tested ECOM-005; committed; ECOM-006 planned

### User

> It is working well
>
> I've created the items
>
> ```json
> {
>   "items": [
>     {
>       "id": "a9afd68e-9fdb-45bc-91c1-18daad984026",
>       "sku": "RS-001",
>       "name": "Running Shoes",
>       "description": "Lightweight shoes.",
>       "category": "Sports",
>       "price": "89.99",
>       "currency": "USD",
>       "stock": 10,
>       "weight_kg": "0.800",
>       "gift": false,
>       "tags": [],
>       "status": "ACTIVE",
>       "is_sellable": true,
>       "version": 1,
>       "created_at": "2026-11-21T16:50:27.113338Z",
>       "updated_at": "2026-11-21T16:50:27.113338Z"
>     },
>     {
>       "id": "40d20d85-b3d4-4ad0-a82c-4c396bfd7d6c",
>       "sku": "GC-001",
>       "name": "Small gift Shoes",
>       "description": "Lightweight shoes",
>       "category": "Gifts",
>       "price": "0.00",
>       "currency": "USD",
>       "stock": 10,
>       "weight_kg": "0.800",
>       "gift": true,
>       "tags": [
>         "GIFT"
>       ],
>       "status": "ACTIVE",
>       "is_sellable": true,
>       "version": 1,
>       "created_at": "2026-11-21T16:53:59.895056Z",
>       "updated_at": "2026-11-21T16:53:59.895056Z"
>     }
>   ],
>   "total": 2,
>   "page": 1,
>   "page_size": 20
> }
> ```
>
> Then changed to
>
> ```json
> {
>   "id": "40d20d85-b3d4-4ad0-a82c-4c396bfd7d6c",
>   "sku": "GC-001",
>   "name": "Small gift Shoes",
>   "description": "Lightweight shoes",
>   "category": "Gifts",
>   "price": "0.00",
>   "currency": "USD",
>   "stock": 10,
>   "weight_kg": "0.800",
>   "gift": true,
>   "tags": [
>     "GIFT"
>   ],
>   "status": "ACTIVE",
>   "is_sellable": true,
>   "version": 1,
>   "created_at": "2026-11-21T16:53:59.895056Z",
>   "updated_at": "2026-11-21T16:53:59.895056Z"
> }
> ```
>
> And deleted (archived)
> 40d20d85-b3d4-4ad0-a82c-4c396bfd7d6c
>
> And restored
>
> ```json
> {
>   "id": "40d20d85-b3d4-4ad0-a82c-4c396bfd7d6c",
>   "sku": "GC-001",
>   "name": "Small gift Shoes",
>   "description": "Lightweight shoes",
>   "category": "Gifts",
>   "price": "0.00",
>   "currency": "USD",
>   "stock": 10,
>   "weight_kg": "0.800",
>   "gift": true,
>   "tags": [
>     "GIFT"
>   ],
>   "status": "ACTIVE",
>   "is_sellable": true,
>   "version": 3,
>   "created_at": "2026-11-21T16:53:59.895056Z",
>   "updated_at": "2026-11-21T16:59:44.644676Z"
> }
> ```
>
> All categories mapped
>
> ```json
> {
>   "items": [
>     "Gifts",
>     "Sports"
>   ]
> }
> ```
>
> So All tests done. You did a great job!
>
> Lets commit and next task.

### Assistant

**ECOM-005 is committed** as `22e2ea4`, with your Swagger test recorded in the ticket.

Your results are exactly what the rules say should happen. One detail, confirmed from the product's history:
- **The "change" came back as version 1.** The values you sent were the ones the product already had, so nothing was saved and no history entry was written. That's the "nothing changed, no new version" rule working.
- **Archiving took it to version 2 and restoring to version 3.** The gift's history reads: created → archived → restored.
- **Names are stored exactly as typed** in the X-Actor-Name field: "x-c4-Antonio" for the create, and "X-AON-Antonio" for the archive and restore.

## ECOM-006: Frontend foundation, the plan for your approval

I've created `feature/ECOM-006-frontend-foundation`; nothing is built yet. This ticket needs **new packages**, and our rule is that you approve them first. The full plan and failure table are in [tasks/ECOM-006.md](tasks/ECOM-006.md).

**What it will give you (business view):** the base that every screen is built on. Pages and links for the shop and the admin area. One consistent way of showing errors: messages under the right form fields, and a notice for anything else, with a reference number when the server fails. And the "Who is reviewing?" prompt that asks for your name once and attaches it to every change.

**Packages to approve:**

| Package | Used for |
|---|---|
| `@tanstack/react-query` | Loading and caching data from the API, with loading and error states |
| `react-router` | Pages and URLs (shop, admin) |
| `react-hook-form` + `zod` + `@hookform/resolvers` | Forms, with the same rules as the server, and server errors shown on the right field |
| `msw` (tests only) | Fake API answers in tests: 422, 409, server errors, network down |
| `eslint` + `typescript-eslint` + `eslint-plugin-react` + `eslint-plugin-react-hooks` + `@eslint/js` + `globals` (tests and CI only) | Code checks, including a ban on injecting raw HTML |
| `prettier` (tests and CI only) | One code format |

All of these were chosen in the architecture (§5). Each will be pinned to an exact version at least two weeks old. **One risk:** we use the new TypeScript 7, which the ESLint TypeScript plugin may not support yet. If not, ESLint still runs its React and HTML-injection checks, and the TypeScript compiler keeps checking types.

**Following your rules on retries and errors:**
- **A failed change is never retried automatically,** so a "create" can't be sent twice behind your back. Only reading data is retried, at most twice, and only when the server or network failed.
- **The submit button is disabled while saving,** so a double click sends one request.
- **Every kind of failure has a clear message:** field errors, conflicts, not found, server error with a reference, network down, or a broken response from the proxy.

**Acceptance criteria (to be proven when built):**
1. Routes for both areas render inside the shell.
2. A validation problem from the API marks the matching form fields.
3. A 5xx problem shows a notification that includes the `request_id`.
4. The admin area asks for the reviewer's name once, and every change request carries it.

**What you'll be able to test after ECOM-006:** the shell, the two areas, the name prompt (ask once, remembered, "Change" link), and "Page not found". The product screens themselves come in ECOM-007 (admin) and ECOM-008 (shop).

**Status:** ECOM-005 is done and committed. **Can I add these packages and build ECOM-006?**

---

## #015 — 2026-11-21 — Packages added, ECOM-006 built: frontend foundation

### User

> yes, add the packages and build ECOM-006

### Assistant

**ECOM-006 is built** on `feature/ECOM-006-frontend-foundation`. It's waiting for your review and isn't committed.

**Packages added, each pinned to the newest version from at least two weeks ago:**
- `@tanstack/react-query` 5.108.2
- `react-router` 8.5.2
- `react-hook-form` 7.92.0
- `zod` 4.6.7
- `@hookform/resolvers` 7.0.8
- `msw` 3.0.7 (tests only)
- `prettier` 3.10.1 (tests only)

**One change from the plan (D-077): ESLint is not installed.** The risk I mentioned came true, and it's worse than expected. The ESLint TypeScript plugin supports TypeScript only up to 6.0, and our TypeScript 7 has dropped the part it needs, so ESLint can't read our files at all. What ESLint was mainly for, blocking raw HTML injection, is now done by a small checker in `testing/scripts`. The build fails if anyone uses `dangerouslySetInnerHTML`, `innerHTML` or similar. It has its own 13 tests. What we lose for now are the React "hooks" rules; the tests and reviews cover them. Options are at the end.

## ECOM-006: Frontend foundation

### Acceptance criteria

| # | Criterion | Result | How it was proven |
|---|---|---|---|
| 1 | Routes for both areas render inside the shell | ✅ Pass | The shop at `/`, the admin products page at `/admin/products` (`/admin` goes there), the weather page at `/weather`, and "Page not found" for anything else. All of them render inside the same header and menu, and the header links move between them. |
| 2 | A validation problem from the API marks the matching form fields | ✅ Pass | A test form sends to a fake API that answers 422. The SKU and price fields turn red with the server's exact messages, and the cursor goes to the first one. Messages that match no field, such as "Reviewer name: Field required", are listed at the top of the form. No pop-up appears for this kind of error. |
| 3 | A 5xx problem shows a notification that includes the `request_id` | ✅ Pass | When loading keeps failing with a server error, the app tries 3 times in total, then shows "An unexpected error occurred. Reference: req-7f3a". If the second try works, you see nothing. A failed **change** shows its reference after **one** try. |
| 4 | The admin area asks for the reviewer's name once, and every change request carries it | ✅ Pass | The first visit to Admin asks "Who is reviewing?" and hides the page until you answer. The name is remembered when you come back. Archive and restore both send it, and "Łukasz" arrives intact. The shop never asks. |

**I also checked that the tests can fail.** I broke the rules on purpose: once to let a failed change retry, once to let a "not found" retry. The tests turned red both times, and the code was put back.

**What was built**
- **The frame of the website:** a header with **Shop** and **Admin**, a page for each, and "Page not found" for wrong addresses.
- **"Who is reviewing?"** Asked once, remembered, and changeable with **Change**. Even with browser storage blocked, it works for the session.
- **One way to talk to the API and show its errors:** messages under the right fields, and a pop-up for other problems. Server errors show a reference number, so a log line can be found.

**Why it was built**
Every screen from now on (admin products in ECOM-007, shop search in ECOM-008, import, checkout) sits on this frame. Errors will look the same everywhere, and no change can be sent without your name.

**Main goal**
A reliable base: clear errors, no change ever repeated automatically, and no change without a name.

**Human testable or background?**
**Partly testable**, in the browser. The pages and the name prompt can be tried now. The error messages on forms become visible in ECOM-007, when the first real form talks to the API; for now the tests prove them.

**What to test** (http://localhost:3000)
1. Open **http://localhost:3000**. → A dark header with **E-commerce**, **Shop** and **Admin**, and a "Shop" page saying search arrives in ECOM-008.
2. Click **Admin**. → A window asks **"Who is reviewing?"**. Click **Continue** with the box empty. → "Tell us who is making this change."
3. Type your name and click **Continue**. → "Admin, Reviewing as <your name>", with a **Products** tab, and the address becomes `/admin/products`.
4. **Refresh the page (F5).** → You're not asked again.
5. Click **Change**, type another name and click **Continue**. → The header shows the new name. Try **Cancel** too: the name stays.
6. Go to **http://localhost:3000/anything**. → "Page not found", with a link back to the shop.
7. Go to **http://localhost:3000/weather**. → The temporary weather page still works.
8. Optional: open a private window and go to Admin. → It asks again, since that window has its own storage.

### Failure cases and retries

All 12 rows of the failure table in [tasks/ECOM-006.md](tasks/ECOM-006.md) have tests, and all pass. These matter most for the business:
- **A failed change is never repeated automatically.** One click is one request, even when the server fails.
- **Double click on a save button:** one request; the button is disabled while saving.
- **Server or network trouble when reading:** two quiet retries, then a clear message.
- **A broken answer from the server** (an HTML error page, or text instead of data): a clear message, never a blank or crashed screen.

**Tests:** 54 new tests: 41 for the frontend and 13 for the raw-HTML checker. The CI container is green: all checks including Prettier and the HTML check, 33 tooling tests, 500 backend tests and 47 frontend tests. The running site has been rebuilt, and the smoke test passes on it.

**Known local issue:** on this Windows machine, the frontend tests sometimes stop before starting ("failed to find the runner") and pass on the next run. It never happened in the CI container, which is the reference.

**Your choice on linting (D-077, no rush):**
- **A. Keep it as it is.** The raw-HTML checker and strict TypeScript are in place, and ESLint comes back when its TypeScript plugin supports TypeScript 7. This is my recommendation for now.
- **B. Approve `oxlint`.** It's a single fast linter that reads TypeScript without the compiler, and should cover the React and hooks rules. I'd confirm that at install time.
- **C. Approve ESLint 9 with Babel's TypeScript parser.** That's more packages (`@babel/eslint-parser` and its presets).

**Status:** ECOM-006 is ready for your review, not committed. Next is ECOM-007: the admin product screen (table, form, gift confirmation, history).

---

## #016 — 2026-11-21 — Lint option A, ECOM-006 committed, ECOM-007 built: admin product screens

### User

> go with A, commit and start ECOM-007. It is looking great our work

### Assistant

Thank you! **ECOM-006 is committed** as `8849272`, with option A recorded (D-077). **ECOM-007 is built** on `feature/ECOM-007-admin-product-ui`; it's waiting for your review and isn't committed.

**First, a correction I owe you (D-079).** In ECOM-006 I said every new package was at least two weeks old. **That was wrong.** The npm option I used to filter by date was silently ignored. Six of the seven packages were between 1 and 10 days old. I found it today while checking the coverage package. All six are now pinned to versions that really are two weeks old (a few patch versions back, nothing major), and everything passes on them. The ECOM-006 ticket and the journal record the correction, and from now on I check each version's real publish date.

## ECOM-007: Admin product screens

### Acceptance criteria

| # | Criterion | Result | How it was proven |
|---|---|---|---|
| 1 | The admin can create, edit, archive and restore a product, and the table reflects each change | ✅ Pass | Each action is done through the screens against a fake API that behaves like ours (versions, duplicate SKUs, the gift rule, history). After each one, the table shows the new row, the new values or the new status, with a green confirmation. The reviewer's name ("Łukasz") travels with every change. |
| 2 | Saving a price of 0 asks for gift confirmation, and refusing keeps the form open | ✅ Pass | Price 0 opens "Price is 0. Mark this product as a gift?". **"No, go back"** keeps the form, your values and the cursor on the price, and **sends nothing**. **"Yes"** saves it as a gift. With "Free gift" already ticked, there's no question. |
| 3 | Server validation errors appear on the matching fields | ✅ Pass | A name with HTML comes back from the server as an error under the Name field, with the cursor placed there. A taken SKU appears under the SKU field. Everything you typed stays. |
| 4 | A 409 version conflict shows a reload message | ✅ Pass | If someone else saved the product while you had it open, Save shows "This product was changed by someone else since you opened it. Reload to see the latest version; your unsaved changes will be lost." **Reload** brings the latest values. |
| 5 | The history page lists every change, oldest first | ✅ Pass | Created (by Maria, with all values), Changed (by someone else: "Price 89.99 → 79.99", "Stock 10 → 3") and Archived, in that order, each with its time. |

**A real bug found and fixed on the way.** My first version of the edit form updated itself whenever the product's version changed. A test showed what that could cause: if the page refreshed in the background while you were editing, your save could silently **overwrite another person's change**. That's exactly the "lost edit" we protect against. Now the form keeps the version it was opened with, and only **Reload** updates it. A test proves it: I put the first design back on purpose and that test turned red.

**What was built**
- **Product list:** search (name, SKU, description), a filter for Active, Archived or All, and pages. Price with currency, a **Gift** badge and an **Out of stock** badge. Your search stays in the address, so refreshing keeps it.
- **Create and edit form,** with category suggestions, the **gift question** for price 0, and messages under each field.
- **Archive** (with a confirmation) and **Restore**, each with a green confirmation.
- **History page** for each product: who, when (UTC), and the value before → after for every field.

**Why it was built**
Challenge rules CC-02 (manage products) and CC-07 (a usable interface). Until now this was only possible in Swagger.

**Main goal**
Manage the catalogue safely from the browser. No accidental free products, no lost edits, clear messages, and the full story of every product.

**Human testable or background?**
**Testable**, in the browser. Your two products from Swagger are already there.

**What to test** (http://localhost:3000/admin)
1. **List:** you see "Small gift Shoes" (Gift badge, $0.00) and "Running Shoes" ($89.99).
2. **Create:** **New product** → SKU `TS-002`, Name `Trail Shoes`, Category `Sports` (it's suggested), Price `120`, Stock `0`, Weight `1.1` → **Create product**. → Back on the list, with "Product created", and Trail Shoes shows **Out of stock**.
3. **Duplicate:** create another product with SKU `rs-001`. → "SKU RS-001 is already taken." under the SKU field.
4. **Gift question:** create a product with price `0` and "Free gift" unticked. → The question appears. **No, go back** keeps the form; then **Yes, mark as gift** saves it with the Gift badge.
5. **Mistakes:** type `<b>Shoes</b>` as a name, or `-1` as stock. → A message appears under the field.
6. **Edit:** **Edit** on Running Shoes, change the price to `79.99`, **Save changes**. → The list shows $79.99.
7. **Two people at once:** open Edit for Running Shoes in **two browser tabs**. Save a change in the first tab, then save a different change in the second. → The second shows the yellow "changed by someone else" message. **Reload** brings the first tab's change.
8. **Archive and restore:** **Archive** Trail Shoes and confirm. → It leaves the Active list. Choose **Status: All** to see it as Archived, then **Restore**.
9. **History:** **History** on Running Shoes. → Every change, oldest first, with your name, the time and before → after.
10. **Search:** type `shoes` and press **Search**. The address shows `?q=shoes`, and refreshing keeps the results.

### Failure cases and retries

All 13 rows of the failure table in [tasks/ECOM-007.md](tasks/ECOM-007.md) have tests, and all pass. These matter most for the business:
- **No lost edits,** even when the page refreshes in the background.
- **Double click on Save or Archive:** one request.
- **A failed save is never repeated automatically.** Your values stay, so you can just press Save again.
- **Server trouble:** a clear message with a reference number, and the list offers **Try again**.

**Tests:** 24 new frontend tests. The CI container is green: all checks, 33 tooling, 500 backend and 71 frontend tests. The website has been rebuilt with these screens.

**One approval needed to finish the ticket:** its definition of done asks for frontend test coverage of at least 80%. Measuring that needs **`@vitest/coverage-v8`**. It must match the test runner's version exactly. Our test runner (Vitest 5.1.1, from ECOM-000) is itself only 3 days old, so I'd pin both to **5.1.0** (19 days old). **May I add `@vitest/coverage-v8` 5.1.0 and move Vitest to 5.1.0?**

**Status:** ECOM-007 is ready for your review, not committed. Next is ECOM-008: the shop's product search page.

---

## #017 — 2026-11-21 — Owner's ECOM-007 test: evidence filed, DEF-01 fixed, UI polish ticket

### User

> Perfect, don`t forget to log into our journal the bug you found and how it was solved,
>
> The drop down is very off, it is okay for now but let`s focus on a better user experience when we focus on UI. Also, it created the item but I receive two messages,  Also, Store those images as recording of testing. It should be as we would respond a jira. Put it into task folder, under the task name + evidence.
>
> The duplicate test is good. For future record, perhaps we should show the item so the person can undestand which duplicate item is in its place.
>
> The gift pop up appeard, but ig provide me more two errors. Edit is also creating error message. Check on them
>
> *(Three screenshots attached, now stored as [01-table-after-create-two-messages.png](../tasks/ECOM-007-evidence/01-table-after-create-two-messages.png), [02-duplicate-sku-on-field.png](../tasks/ECOM-007-evidence/02-duplicate-sku-on-field.png) and [03-gift-confirmation-dialog.png](../tasks/ECOM-007-evidence/03-gift-confirmation-dialog.png).)*

### Assistant

Thank you for testing it in the browser: you found a real defect that my tests missed. Everything below is on `feature/ECOM-007-admin-product-ui`, not committed.

## The extra red messages (DEF-01): found and fixed

**What you saw:** the product was saved correctly, but a red "Something unexpected went wrong" appeared next to "Product created". Two appeared after the gift, and more after an edit.

**Why it happened:**
- After a save, the app keeps a copy of the saved product, so the screens don't have to ask the server again.
- Then it refreshes every product list, so the table is up to date. That refresh also tried to reload those kept copies, and they had no instructions for reloading. Each one failed with an internal error, which the app showed as "Something unexpected".
- Every product created in the session added one more failing copy. That's why there was one message, then two, then more.

**Why my tests missed it:** they checked that "Product created" appeared, but never that **no** error appeared next to it. That was a gap in how I wrote the tests.

**The fix:** after a save, only the product lists, that product's history and the categories are refreshed. The saved product is already up to date from the server's answer.

**So it can't come back:**
- **A test replays your exact session:** create Trail Shoes, create a gift through the dialog, edit Running Shoes. It requires 3 green messages and zero red ones.
- **Every frontend test now fails** if the app hits an unexpected error, even when the test is about something else.
- **Proof:** with the old code put back, 7 tests fail on exactly this error; with the fix, all 72 pass.
- Unexpected errors are also written to the browser console now, to make any future diagnosis faster.

## Test evidence, filed like a Jira test record

Your screenshots are in **[tasks/ECOM-007-evidence/](tasks/ECOM-007-evidence/README.md)**, with a README that records:
- the environment, and each step with its expected result, actual result and outcome;
- the defect DEF-01, with its cause, fix, guards and status ("waiting for your re-test");
- your observations, and a **re-test checklist** for you.

From now on, every hand test gets the same treatment (D-082).

## Journal

- **D-080: the bug I found while building.** The edit form could have silently overwritten another admin's change after a background refresh. The entry covers how it was found, the cause, the fix, and the test that guards it (which fails on the old code).
- **D-081: the bug you found** (DEF-01), with the same details.
- **D-082:** the evidence folders, and the new UI-polish ticket.

## Your UX remarks: a new ticket, ECOM-018 (UI polish)

As you asked, these wait for the UI-focused work. The ticket collects:
- **Drop-downs:** a proper look for the status filter and the category picker, with no light-blue autofill background.
- **Table on narrow windows:** your screenshot shows wrapping SKUs and a cut-off Archive button. The actions should always be visible.
- **Notifications:** green messages should close by themselves and not cover the table.
- **Duplicate SKU, show who owns it:** "SKU RS-001 is already taken by **Running Shoes**", with links to view or edit it. That's your suggestion, recorded for later.

**What to re-test** (http://localhost:3000/admin, already rebuilt with the fix):
1. Create a product. → Only the green "Product created".
2. Create a free product and answer **Yes, mark as gift**. → Only the green message.
3. Edit a product and save. → Only "Changes saved".
4. Repeat a few creates and edits. → Still no red messages.

**Tests:** the CI container is green: all checks, 33 tooling, 500 backend and 72 frontend tests.

**Still open from my last message:** may I add `@vitest/coverage-v8` 5.1.0 and move Vitest to 5.1.0, both 19 days old? ECOM-007's definition of done asks for at least 80% frontend coverage, and that needs it.

**Status:** ECOM-007 is in review, waiting for your re-test of DEF-01 and the coverage answer. Then I commit it and start ECOM-008 (the shop's search page).

---

## #018 — 2026-11-21 — Re-test: the stale tab (DEF-02), gifts always free (CR-01), whole-page test checks

### User

> Every test, get the whole body to check if any error message appears. Log into our  journal the error and what created it. I believe a gift should be a upper option, I was able to create a gift with value which makes no sense. The error is still apearing. Or is it a cache problem ?
>
> *(Screenshot attached, now stored as [04-retest-errors-from-stale-tab.png](../tasks/ECOM-007-evidence/04-retest-errors-from-stale-tab.png).)*

### Question asked during the turn, and the owner's answer

> **Gift rule:** today a product can be a paid gift (SP-003 "Normal shoes" is $55 with the Gift tag). Should a gift always be free?
> - Gifts are always free (Recommended): Gift ⇔ price 0. In the form, "Free gift" moves to the top; ticking it sets the price to 0 and locks the field. The API and the database refuse a paid gift (422). A one-off, audited data fix removes the Gift tag from SP-003 (it keeps its $55 price), recorded in its history as done by "Data migration".
> - Keep paid gifts allowed: Gift stays a label any product can carry; only a price of 0 requires it. I would just move the gift option to the top of the form. SP-003 stays as it is.
>
> **Answer:** Gifts are always free (Recommended)

### Assistant

**You were right: it was a cache problem.** Your browser tab was still running the old code. Everything below is on `feature/ECOM-007-admin-product-ui`, not committed.

## Why the red messages "came back" (DEF-02)

**What I checked:** the server's access log.
- The fix went live at 18:53 (server time).
- Your two creates arrived at 19:09 and 19:11. Your browser **never downloaded the new code** in between; the only download of it was my own check at 19:12.
- A web app like ours loads its code once per tab, so your open tab kept running the version with the bug.

**What made it possible:** the web server sent no caching instructions. Even a refresh could reuse an old copy of the page.

**Fixed:**
- The page now always tells the browser to check for a newer version, and the smoke test verifies that on every CI run.
- A "new version available — reload" banner is added to ECOM-018, so a long-open tab can warn you.

**Logged in the journal as you asked (D-084):** the error, what created it, the server-log evidence, the fix, and how to diagnose it next time.

## Gifts are always free (your decision, D-083)

**What changed:**
- **The form:** "Free gift (gifts are always priced at 0)" is now the **first option**. Ticking it sets the price to 0 and locks the field ("Gifts are always free."). Unticking it brings back the price you had typed.
- **The API:** a gift with a price is refused with a clear message: "A gift must be free. Set the price to 0, or untick the gift."
- **The database:** it refuses a paid gift too, as a safety net.
- **Your existing data:** SP-003 "Normal shoes" was the only paid gift. It lost the Gift tag and kept its $55 price. Its **History** shows "Changed by Data migration: tags GIFT → (none)", with the reason. I verified this on your database.

## Every test now checks the whole page (D-085)

As you asked, when each frontend test finishes it inspects the whole page. The test fails if:
- the page shows "Something unexpected went wrong";
- **any red pop-up** appeared that the test didn't declare in advance (only the 8 tests whose purpose is to cause an error declare one);
- the app logged an unexpected error.

**The check found one more double message right away:** the "Product not found" page also showed a red "not found" pop-up. Fixed.

## Evidence

[tasks/ECOM-007-evidence/](tasks/ECOM-007-evidence/README.md) now holds your 4th screenshot, together with:
- re-test 1;
- **DEF-02** (the stale tab), with the log evidence;
- **CR-01** (gifts always free);
- an updated re-test checklist.

**What to re-test** (http://localhost:3000/admin):
1. **Reload once with Ctrl+F5.** That's the last time it's needed: from now on a normal refresh always gets the newest version.
2. Create a product. → Only the green "Product created".
3. Create a gift: tick **Free gift** first. → The price becomes 0 and is locked; save. → Only the green message.
4. Try to give a gift a price. → You can't: the price stays locked while the gift box is ticked.
5. Edit and save. → Only "Changes saved".
6. Open **SP-003 Normal shoes**. → No Gift badge; its History shows the "Data migration" entry.

**Tests:** the CI container is green: all checks, 33 tooling, 505 backend and 75 frontend tests, and the smoke checks (now including "the page is never served stale").

**Still open:** may I add `@vitest/coverage-v8` 5.1.0 and move Vitest to 5.1.0, to measure the 80% frontend coverage?

**Status:** ECOM-007 is in review, waiting for your re-test. Then I commit it and start ECOM-008 (the shop's search page).

---

## #019 — 2026-11-21 — Re-test 2 passed; frontend coverage gate added

### User

> Great, no error this time. Yes, move it. We will improve the interface later. It is good for testing the backend.
>
> *(Screenshot attached, now stored as [05-retest-2-only-success-message.png](../tasks/ECOM-007-evidence/05-retest-2-only-success-message.png).)*

### Assistant

Good to hear: **re-test 2 passed.** GF-04 was created as a free gift with only the green message, and SP-003 now shows $55.00 without the Gift badge. Everything is on `feature/ECOM-007-admin-product-ui`, not committed.

## What I did

**1. Filed your re-test as evidence.** Screenshot 05 is in [tasks/ECOM-007-evidence/](tasks/ECOM-007-evidence/README.md). The record now says **Passed**: both defects are verified by you, and the gift change is done. In the re-test checklist I ticked only what you actually confirmed. "A gift can't have a price" and "Edit shows only Changes saved" weren't in your report, so they stay unticked, with a note that the automated tests cover them.

**2. Added the frontend coverage check (your "yes, move it", D-086).**
- The test runner moved to Vitest 5.1.0, and the coverage tool is the matching 5.1.0. Both are 19 days old, dates checked properly this time.
- **Result: 95.7%** of the frontend code is exercised by tests (89% of the branches), well above the 80% minimum. From now on, CI fails if it drops below 80%.
- **One hiccup on the way:** npm itself crashed while installing (a bug in npm's handling of the test tool's optional parts). A one-line setting that pins the test runner fixed it. The package lock file had to be rebuilt, but every package we chose keeps its exact version.

**3. Noted your direction.** The interface gets its polish later, in ECOM-018. For now the screens are good enough to test the backend.

## ECOM-007: final state

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | Create, edit, archive and restore, with the table reflecting each change | ✅ Pass (automated, and by you in the browser) |
| 2 | A price of 0 asks for gift confirmation; refusing keeps the form open | ✅ Pass (automated, and by you) |
| 3 | Server validation errors on the matching fields | ✅ Pass (automated; you saw the duplicate SKU) |
| 4 | A version conflict shows a reload message | ✅ Pass (automated) |
| 5 | History lists every change, oldest first | ✅ Pass (automated) |
| DoD | Frontend coverage ≥ 80% | ✅ 95.7% |

**Tests:** the CI container is green: all checks, 34 tooling, 505 backend and 75 frontend tests (with the coverage check), and the smoke checks.

**Status:** ECOM-007 has passed your re-test and its definition of done. **Shall I commit it and start ECOM-008** (the shop's product search page)?

---

## #020 — 2026-11-21 — ECOM-007 committed, ECOM-008 built: the shop

### User

> Perfect, commit and lets go for next one.

### Assistant

**ECOM-007 is committed** as `f47c000`. **ECOM-008 is built** on `feature/ECOM-008-storefront-search`; it's waiting for your review and isn't committed. No new packages were needed.

## ECOM-008: The shop's search page

### Acceptance criteria

| # | Criterion | Result | How it was proven |
|---|---|---|---|
| 1 | Typing a query and applying filters updates the results and the URL | ✅ Pass | Searching "shoes", ticking "In stock only" and sorting by price narrow the list each time. The address becomes `?q=shoes&in_stock=true&sort=-price`. Category, price range and "Gifts only" work the same way, and so do all 5 sort orders and the pages. |
| 2 | Reloading the page keeps the same search | ✅ Pass | The page is opened, closed and opened again at the same address. The results, the search box, the check boxes and the sort order all come back the same. |
| 3 | Gift products show the badge | ✅ Pass | Gifts show the **Gift** badge and the price **"Free"**, in the list and on their own page. |
| 4 | Out-of-stock products cannot be added to the cart | ✅ Pass | An out-of-stock product shows "Out of stock" and its button is disabled. A product with 2 in stock, clicked 3 times fast, stops at 2: "Only 2 in stock". I loosened that limit by one on purpose, and the test caught it. |

**What was built**
- **The shop page** (http://localhost:3000):
  - search by name, SKU or description;
  - filters for category, minimum and maximum price, "In stock only" and "Gifts only";
  - 5 sort orders, and pages of 12 products.
- **Everything is in the address,** so a refresh or a shared link shows the same results. A badly edited link never breaks the page: wrong values are simply ignored.
- **A page for each product,** with its price ("Free" for gifts), description, category, weight, stock and **Add to cart**.
- **A simple cart** that counts items in the header ("Cart: 2 items") and survives a refresh. **It never holds more than the stock.** The cart page and checkout come in ECOM-015, and the server checks stock again at payment (ECOM-014).

**Why it was built**
Challenge rules CC-05 (search) and CC-07 (a usable interface). It's the shopper's half of the store.

**Main goal**
Shoppers find products easily, and can never put more in the cart than there is.

**Human testable or background?**
**Testable** in the browser. Your own products are already there. I checked the shop's search against your data: 7 active products, 3 of them gifts.

**What to test** (http://localhost:3000; refresh once to get the new version)
1. **Shop:** your 7 products appear as cards. The 3 gifts say **Free**, with a **Gift** badge.
2. **Search:** type `shoes` and press **Search**. → Only shoes. The address shows `?q=shoes`.
3. **Gifts only:** click **Shop** in the header to clear the search, then tick **Gifts only**. → Collar gift, shoes for gift and Small gift Shoes.
4. **Filters together:** click **Shop**, choose Category **Sports**, type Min price `50` and press **Search**. → Normal shoes, Running Shoes and Trail Shoes.
5. **Sort** by "Price: high to low". → Trail Shoes first.
6. **Refresh the page (F5).** → Same results, same filters.
7. **Wrong prices:** Min `100`, Max `10`, **Search**. → "The minimum price must not be above the maximum." and nothing changes.
8. **Product page:** click **Running Shoes**, then **Add to cart**. → "Added to cart", and the header says "Cart: 1 item". Keep clicking: it stops at the stock ("Only N in stock").
9. **Out of stock:** in Admin, set a product's stock to 0, then open it in the shop. → "Out of stock", and the button can't be clicked.
10. **Wrong link:** http://localhost:3000/products/abc → "Product not found", with a link back to the shop.

### Failure cases and retries

All 13 rows of the failure table in [tasks/ECOM-008.md](tasks/ECOM-008.md) have tests, and all pass. These matter most for the business:
- **Never more than the stock:** an out-of-stock product can't be added, the cart stops at the stock even with fast clicks, and an archived product says "No longer available".
- **Bad input never breaks the page:** wrong prices get a message and send nothing, and bad links fall back to the normal list.
- **Server trouble:** a clear message with **Try again**.
- **A small accessibility bug found by the tests:** the price error messages had been placed inside the field labels, which garbled the field names for screen readers. Fixed.

**Tests:** 19 new tests for the shop. The CI container is green: all checks, 34 tooling, 505 backend and 94 frontend tests (96% coverage), and the smoke checks. Every test also checks the whole page for errors, as you asked.

**Status:** ECOM-008 is ready for your review, not committed. Next is ECOM-009: removing the temporary weather feature from ECOM-000.

---

## #021 — 2026-11-21 — ECOM-008 accepted and committed, ECOM-009 built: weather removed

### User

> It is working pretty well. Commit and lets go for next. Store the evidences.
>
> *(Two screenshots attached, now stored as [01-category-gifts-filter.png](../tasks/ECOM-008-evidence/01-category-gifts-filter.png) and [02-sorted-price-high-to-low.png](../tasks/ECOM-008-evidence/02-sorted-price-high-to-low.png).)*

### Assistant

**ECOM-008 is committed** as `ee13bf8`. Your two screenshots are filed in [tasks/ECOM-008-evidence/](tasks/ECOM-008-evidence/README.md) as a passed test record:
- Category **Gifts** showed 2 free gifts with the badge;
- sorting by price showed all 7 products, with Trail Shoes "Out of stock" first.

The record also notes why the Gifts category shows 2 while "Gifts only" shows 3: "shoes for gift" is in the Sports category. Both filters behave as designed.

**ECOM-009 is built** on `feature/ECOM-009-remove-weather`; it's waiting for your review and isn't committed.

## ECOM-009: Remove the temporary weather feature

### Acceptance criteria

| # | Criterion | Result | How it was proven |
|---|---|---|---|
| 1 | No code, test, setting or route mentions weather | ✅ Pass | A search of the whole project finds "weather" only in the database migration history: one step created the table, the new one drops it. They must keep their names, or existing databases couldn't upgrade. The app, settings, pages, API and other tests are clean. |
| 2 | The smoke test proves the stack end to end through the catalog | ✅ Pass | Through the website, it now creates a test product, finds it by search, archives it, and checks that it left the shop. It ran twice in a row: the second run reused the same product instead of creating another. |
| 3 | Upgrading an existing database drops the table without errors | ✅ Pass | Your own database upgraded without errors, and the weather table is gone. A test also checks that the step can be undone and redone cleanly. |

**What was built**
- **Removed:**
  - the weather lookup (its page, its code and its 46 tests);
  - its database table;
  - the connection to the outside weather service.

  The system now contains only the store.
- **A better end-to-end check.** Every CI run now proves the real store through the website: create a product, find it, archive it. Before, it looked up the weather in Lisbon.
- **Idempotent, as you asked for writes:** the check creates its test product **once** ("Smoke test product", SKU `SMOKE-TEST`), then reuses it on every run, so your database doesn't fill up with test products.

**Why it was built**
The weather demo did its job on day one: it proved the containers, database, API and website work together. Now the store proves that. Keeping the demo would mean dead code, and an outside service that could make our checks fail for reasons that have nothing to do with the store.

**Main goal**
A smaller, cleaner system that contains only the store, with an end-to-end check that tests the store itself.

**Human testable or background?**
**Mostly background.** You can see it in two places.

**What to test**
1. Open **http://localhost:3000/weather**. → "Page not found".
2. In **Admin**, set Status to **All**. → One archived **"Smoke test product"** (category "Smoke tests"), made by the automatic checks. Its **History** shows the actor "Smoke test". It stays archived, so the shop never shows it.

### Failure cases and retries

All 5 rows in [tasks/ECOM-009.md](tasks/ECOM-009.md) pass:
- running the check again reuses its product;
- an archived test product is restored, found and archived again;
- your database upgraded cleanly;
- the step can be undone;
- the old weather address simply says "Page not found".

**Tests:** the CI container is green: all checks, 34 tooling, 467 backend (39 weather tests removed, 1 added) and 87 frontend tests (7 removed), and the new store smoke test.

**Status:** ECOM-009 is ready for your review, not committed. That completes Phase 2 (the catalog screens). Next is **ECOM-010**: the CSV import, which reads the sample file, classifies every row and applies the import rules.

---

## #022 — 2026-11-21 — ECOM-009 committed; pause for an external code review

### User

> commit and wait. Codex will do a code review in our changes so we can go for the next half of tasks

### Assistant

**ECOM-009 is committed** on `feature/ECOM-009-remove-weather`. I've stopped here and won't start ECOM-010 until you say so.

**What the reviewer will find**
- **One branch per ticket,** each built on the previous one. `feature/ECOM-009-remove-weather` holds everything from ECOM-000 to ECOM-009; nothing is merged into `main`.
- **Each ticket in `tasks/`** has its acceptance criteria, its failure and retry table, a verification table with how each criterion was proven, and a business view. ECOM-007 and ECOM-008 also have your test evidence.
- **`docs/JOURNAL.md`** holds every decision (D-001 to D-088), including the bugs and how they were fixed (D-080, D-081, D-084). `docs/PROMPT_HISTORY.md` holds every prompt and reply, #001 to #022.
- **`python testing/run.py all`** (or `docker compose run --rm ci`) runs every check:
  - lint, types and layer rules;
  - the no-comments and raw-HTML checks;
  - 34 tooling, 467 backend and 87 frontend tests, with coverage gates;
  - the smoke test through the website.

  It was all green on the last run.

**Status:** waiting for the code review. When you share the findings, I'll file each one and fix it before the second half of the tasks (ECOM-010 onwards).
