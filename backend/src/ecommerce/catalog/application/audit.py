from collections.abc import Iterable, Mapping

from ecommerce.catalog.domain.events import (
    AuditValue,
    ProductArchived,
    ProductChanged,
    ProductCreated,
    ProductEvent,
    ProductRestored,
    StockDecreased,
)
from ecommerce.catalog.domain.product import ProductStatus
from ecommerce.shared_kernel.application.audit import AuditEntry, JsonObject, JsonValue
from ecommerce.shared_kernel.domain.actor import Actor

PRODUCT_ENTITY = "product"
ACTIVE: JsonObject = {"status": ProductStatus.ACTIVE.value}
ARCHIVED: JsonObject = {"status": ProductStatus.ARCHIVED.value}

type Description = tuple[str, JsonObject | None, JsonObject | None, JsonObject]


def audit_entries(events: Iterable[ProductEvent], actor: Actor) -> list[AuditEntry]:
    return [audit_entry(event, actor) for event in events]


def audit_entry(event: ProductEvent, actor: Actor) -> AuditEntry:
    name, before, after, context = describe(event)
    return AuditEntry(
        occurred_at=event.occurred_at,
        actor=actor.name,
        event=name,
        entity=PRODUCT_ENTITY,
        entity_id=str(event.product_id),
        sku=event.sku,
        before=before,
        after=after,
        context=context,
    )


def describe(event: ProductEvent) -> Description:
    match event:
        case ProductCreated(snapshot=snapshot):
            return "product.created", None, json_object(snapshot), {}
        case ProductChanged(changes=changes):
            before = {name: change.before for name, change in changes.items()}
            after = {name: change.after for name, change in changes.items()}
            return "product.changed", json_object(before), json_object(after), {}
        case ProductArchived():
            return "product.archived", ACTIVE, ARCHIVED, {}
        case ProductRestored():
            return "product.restored", ARCHIVED, ACTIVE, {}
        case StockDecreased():
            context: JsonObject = {
                "quantity": event.quantity,
                "order_reference": event.order_reference,
            }
            return (
                "product.stock_decreased",
                {"stock": event.stock_before},
                {"stock": event.stock_after},
                context,
            )
    raise TypeError(f"No audit description for {type(event).__name__}.")


def json_object(values: Mapping[str, AuditValue]) -> JsonObject:
    return {name: json_value(value) for name, value in values.items()}


def json_value(value: AuditValue) -> JsonValue:
    if isinstance(value, tuple):
        return list(value)
    return value
