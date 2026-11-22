from collections.abc import Iterable

from ecommerce.ordering.domain.events import OrderEvent, OrderPaid, OrderPaymentFailed
from ecommerce.ordering.domain.value_objects import OrderStatus
from ecommerce.shared_kernel.application.audit import AuditEntry, JsonObject
from ecommerce.shared_kernel.domain.actor import Actor

ORDER_ENTITY = "order"
SHOP_ACTOR = Actor("Shop checkout")
CHECKOUT_CONTEXT: JsonObject = {"source": "checkout"}


def describe(event: OrderEvent) -> tuple[str, JsonObject]:
    match event:
        case OrderPaid():
            return "order.paid", {
                "status": OrderStatus.PAID.value,
                "total": event.total,
                "lines": [
                    {"sku": sku, "quantity": quantity, "unit_price": price}
                    for sku, quantity, price in event.lines
                ],
                "card_last4": event.card_last4,
                "payment_reference": event.payment_reference,
            }
        case OrderPaymentFailed():
            return "order.payment_failed", {
                "status": OrderStatus.PAYMENT_FAILED.value,
                "total": event.total,
                "decline_reason": event.reason,
                "card_last4": event.card_last4,
            }
    raise TypeError(f"No audit description for {type(event).__name__}.")


def order_audit_entries(events: Iterable[OrderEvent], actor: Actor) -> list[AuditEntry]:
    entries = []
    for event in events:
        name, after = describe(event)
        entries.append(
            AuditEntry(
                occurred_at=event.occurred_at,
                actor=actor.name,
                event=name,
                entity=ORDER_ENTITY,
                entity_id=str(event.order_id),
                sku=None,
                before=None,
                after=after,
                context=CHECKOUT_CONTEXT,
            )
        )
    return entries
