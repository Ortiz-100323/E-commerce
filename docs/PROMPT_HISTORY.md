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
