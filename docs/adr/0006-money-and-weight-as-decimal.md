# ADR-0006: Money and weight are exact decimals, end to end

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-009, D-026, D-064, D-068 |

## Context

The CSV has prices like `$89.99` and weights like `0.25`. Floats corrupt money. The first plan stored integer cents and grams, but only because SQLite has no exact decimal type ([ADR-0004](0004-postgresql-only.md)).

## Decision

- **Domain:**
  - `Money` in the shared kernel holds a `Decimal` with 2 decimal places, USD only.
  - Weight is a `Decimal` in kilograms with up to 3 decimal places.
  - A float or a boolean passed in is a programming error (`TypeError`), never user input.
- **Database:**
  - The price is `NUMERIC(12,2)` and the weight `NUMERIC(10,3)`. The order total is `NUMERIC(18,2)`, so the largest valid order fits.
  - CHECK constraints mirror the domain rules: price, stock and weight are never negative, and a gift is free.
- **API:** money travels as a string (`"89.99"`), never as a JSON number.
- **Domain limits match the columns.** A valid domain object can always be saved, rather than failing in the database as a 500.

## Alternatives discarded

- **Integer cents and grams.** Only needed for SQLite; with PostgreSQL they add conversions and no safety.
- **Floats.** Rounding errors in money.
- **Text columns.** No ordering or arithmetic in SQL.

## Consequences

- Rounding is never silent. A value with too many decimals is an error, not a rounded number ([ADR-0012](0012-csv-issue-taxonomy.md)).
- Multi-currency would need a currency column and a migration (business question CQ-06).
