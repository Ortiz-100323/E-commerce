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
