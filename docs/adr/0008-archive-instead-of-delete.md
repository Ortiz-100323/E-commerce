# ADR-0008: Deleting a product archives it

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-013, D-068, D-087 |

## Context

Orders must keep describing what was bought, and the audit history must stay readable, even after a product is removed from the shop.

## Decision

- **`DELETE /products/{id}` archives the product.** It can be restored, and its SKU stays reserved.
- **Archived products:**
  - are hidden from the shop's lists;
  - can't be bought (`product-not-sellable`, reason `archived`);
  - can still be edited by an admin before restoring.
- **Old links still work.** An archived product's page says "This product is no longer available".
- **Order lines snapshot** the SKU, name and unit price at the time of purchase.
- **An import can restore an archived product,** after confirmation.
- Archiving asks for confirmation; restoring doesn't.

## Alternatives discarded

- **A hard delete with `ON DELETE SET NULL` on order lines:** the orders lose the product's context.
- **A 404 for archived product pages:** a shared link would look broken instead of explaining.

## Consequences

- Nothing is ever physically deleted from the catalog.
- Product lists default to `status=ACTIVE`, so archived products can't appear in the shop by accident.
