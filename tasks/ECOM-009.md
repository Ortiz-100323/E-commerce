# ECOM-009: Remove the temporary weather feature

| Field | Value |
|---|---|
| Type | Technical task |
| Phase | 2 |
| Status | **Done** |
| Depends on | ECOM-007, ECOM-008 |
| Journal | D-052, D-072, D-088, D-089 |

## Context

The weather feature from ECOM-000 only existed to prove the stack. Once the catalog works end to end, it has served its purpose.

## Scope

- Delete the `weather` bounded context, its router, its tests and its frontend page.
- Add an Alembic migration that drops `weather_searches`.
- Point `smoke_test.py` at the catalog: create a product through the proxy, then find it by search.
- Remove the outbound Open-Meteo dependency and its settings.

## Acceptance criteria

1. No code, test, setting or route mentions weather.
2. The smoke test proves the stack end to end through the catalog.
3. Upgrading an existing database drops the table without errors.

## Failure cases and retries (D-072)

| Situation | What happens | Result |
|---|---|---|
| The smoke test runs again (its product already exists) | The create answers 409 `duplicate-sku`, which the test expects; it reuses the product | Pass (run twice in a row) |
| The smoke product is archived from a previous run | It is restored, found by search, and archived again | Pass |
| A database at 0004 with weather searches in it | Upgrading to 0005 drops the table and its index | Pass (the live database: 0004 → 0005) |
| A downgrade to 0004 | The table is recreated exactly as 0001 made it | Pass |
| The old `/weather` address | "Page not found", like any unknown address | Pass |

## Verification (2026-11-21)

| # | Acceptance criterion | Result | How it was proven |
|---|---|---|---|
| 1 | No code, test, setting or route mentions weather | **Pass** | A search of the whole repository (outside `docs/` and `tasks/`, which keep the history) finds "weather" only in the migration history (0001 creates the table, 0005 drops it) and the migration tests that check it. The app, settings, routes, frontend, smoke test and the other tests are clean. The API has no weather endpoint left (the contract test counts exactly 7 endpoints that take input, all products). |
| 2 | The smoke test proves the stack end to end through the catalog | **Pass** | Through nginx on http://frontend, it checks the page and its cache headers and the health check. Then it creates (or reuses) `SMOKE-TEST`, restores it, finds it by search, archives it and checks it left the shop. It passed twice in a row; the live database holds one `SMOKE-TEST`, with history created → archived → restored → archived. |
| 3 | Upgrading an existing database drops the table without errors | **Pass** | Your live database upgraded from 0004 to 0005 on restart; `weather_searches` no longer exists. A migration test downgrades to 0004 (table back) and upgrades again (table gone), and the schema-drift test still finds no differences. |

### Code review round 1 (2026-11-21)

**Fixed:** on a duplicate `SMOKE-TEST` SKU, the smoke check previously trusted the SKU alone, then restored and archived that product. A merchant product using the same SKU could therefore be changed by the check. The check now verifies its stable name, description and category before any mutation; otherwise it stops with a collision message. Two tooling tests prove that its own product is accepted and a merchant product is refused.

**Also in this ticket:**
- `httpx` moved to the development dependencies, since production code makes no outbound calls any more.
- The 7 problem-details tests that used the weather endpoint now use test-only routes.
- `upstream-unavailable` stays, for the real payment provider later.
- The README describes the current state.
- Architecture revision 17.

**Totals:** 39 backend tests and 7 frontend tests were removed with the feature, and 1 migration test was added. The 17 problem-details cases are all kept. The `ci` container passes:
- all static checks, with 4 import contracts;
- 34 tooling tests;
- 467 backend tests at 100% domain and application coverage;
- 87 frontend tests at 96% coverage;
- the new catalog smoke test.

## Test plan

- The full suite and the new smoke test pass in the `ci` container.

## Business view

- **What was built:** nothing new for shoppers or admins. The temporary weather lookup, used to prove the system worked on day one, is gone, along with its database table and its connection to an outside weather service. The automatic end-to-end check now proves the real store instead: it creates, finds and archives a test product through the website.
- **Why:** the store does what the weather demo proved. Keeping the demo would mean dead code, an outside service that could fail our checks, and a confusing page.
- **Main goal:** a smaller, cleaner system that only contains the store, with an end-to-end check that tests the store itself.
- **Human testable or background:** **mostly background.** You can see it in two places.
- **What to test:** http://localhost:3000/weather now says "Page not found". In Admin, **Status: All** shows one archived "Smoke test product" (category "Smoke tests"), created by the automatic checks; its History shows "Smoke test" as the actor.

## Definition of done

- Acceptance criteria pass.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
