# ADR-0014: Business rules are configurable policies, with open questions for the business

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-034, D-035, D-090 |

## Context

Several import rules are business choices, not engineering facts. Examples: are zero prices gifts, does stock mean "on hand" or "received", which duplicate row wins. The business may want a different rule later.

## Decision

- **Each import rule is a domain strategy,** chosen from settings with the `IMPORT_` prefix:
  - zero price;
  - empty field;
  - zero weight;
  - existing SKU;
  - duplicate SKU in the file;
  - currency symbol;
  - SKU identity and its similarity threshold;
  - the maximum number of rows.
- **Every variant has its own unit tests.** The settings are validated when the backend starts, so a typo stops it with the setting's name instead of silently using a default.
- **The open business questions are kept as CQ-01 to CQ-10** in [the architecture document](../TECHNICAL_ARCHITECTURE.md), each with the default built in the meantime. The README lists them.

## Alternatives discarded

- **Hard-coded rules:** any change from the business would mean code, tests and a redeploy.
- **A rules engine:** overkill for a handful of rules.

## Consequences

- Changing a rule is a configuration change.
- The defaults are safe: anything unclear goes to a person for review.
