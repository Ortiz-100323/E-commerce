# ADR-0015: A product is a gift if and only if its price is zero

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-031, D-068 (partly superseded), D-083 |

## Context

The sample has zero prices and the word `free`. The owner's reading: perhaps it's a gift, so ask a person and tag it. Later, in a browser test, the owner created a $55 product with the Gift box ticked, and decided that a gift with a price makes no sense.

## Decision

- **A product's price is zero if and only if it carries the `GIFT` tag.**
  - In the domain, `zero_price_requires_gift` and `gift_must_be_free` cover both directions.
  - In the database, the CHECK constraint `ck_products_gift_if_and_only_if_free` enforces it.
- **In the import,** a zero price or `free` goes to review. Confirming it makes the product a free gift.
- **In the admin form,** ticking "Free gift" sets the price to 0 and locks the field. A zero price without the tag asks first.
- **At checkout,** an order totalling zero is paid without a card and without calling the payment gateway.
- **Existing data:** migration 0004 removed the tag from paid products, kept their price, and wrote an audit entry for each.

## Alternatives discarded

- **Rejecting zero prices** (the first proposal): the owner overruled it.
- **Allowing zero prices silently:** products could be given away by mistake.
- **Allowing paid gifts:** the owner rejected this after testing it.
- **Fixing old paid gifts by zeroing their price:** it would give away products the owner meant to sell.

## Consequences

- One rule, enforced in the domain, the API, the form and the database.
- Whether gifts can be ordered alone, or with a limit, is an open business question (CQ-01).
