# ECOM-009: Remove the temporary weather feature

| Field | Value |
|---|---|
| Type | Technical task |
| Phase | 2 |
| Status | **Backlog** |
| Depends on | ECOM-007, ECOM-008 |
| Journal | D-052 |

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

## Test plan

- The full suite and the new smoke test pass in the `ci` container.

## Definition of done

- Acceptance criteria pass.
- `run.py all` is green in the `ci` container.
- Journal, prompt history and this ticket are updated; the owner has accepted it.
