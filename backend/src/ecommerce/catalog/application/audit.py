from collections.abc import Iterable, Mapping
from uuid import UUID

from ecommerce.catalog.domain.events import (
    AuditValue,
    ProductArchived,
    ProductChanged,
    ProductCreated,
    ProductEvent,
    ProductRestored,
    StockDecreased,
)
from ecommerce.catalog.domain.importing.batch import BatchStatus
from ecommerce.catalog.domain.importing.events import (
    ImportCommitted,
    ImportDiscarded,
    ImportEvent,
    ImportRowConfirmed,
    ImportRowCorrected,
    ImportRowResolved,
    ImportRowSkipped,
    ImportStarted,
    ResolutionValue,
)
from ecommerce.catalog.domain.product import ProductStatus
from ecommerce.shared_kernel.application.audit import AuditEntry, JsonObject, JsonValue
from ecommerce.shared_kernel.domain.actor import Actor

PRODUCT_ENTITY = "product"
IMPORT_BATCH_ENTITY = "import_batch"
IMPORT_ROW_ENTITY = "import_row"
ACTIVE: JsonObject = {"status": ProductStatus.ACTIVE.value}
ARCHIVED: JsonObject = {"status": ProductStatus.ARCHIVED.value}
PENDING: JsonObject = {"status": BatchStatus.PENDING_REVIEW.value}

ROW_EVENTS: dict[type[ImportRowResolved], str] = {
    ImportRowConfirmed: "import.row.confirmed",
    ImportRowCorrected: "import.row.corrected",
    ImportRowSkipped: "import.row.skipped",
}

type Description = tuple[str, JsonObject | None, JsonObject | None, JsonObject]


def import_row_id(batch_id: UUID, line: int) -> str:
    return f"{batch_id}:{line}"


def audit_entries(
    events: Iterable[ProductEvent],
    actor: Actor,
    contexts: Mapping[UUID, JsonObject] | None = None,
) -> list[AuditEntry]:
    known = contexts or {}
    return [audit_entry(event, actor, known.get(event.product_id, {})) for event in events]


def audit_entry(event: ProductEvent, actor: Actor, extra: JsonObject | None = None) -> AuditEntry:
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
        context={**context, **(extra or {})},
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


def import_audit_entries(events: Iterable[ImportEvent], actor: Actor) -> list[AuditEntry]:
    return [import_audit_entry(event, actor) for event in events]


def import_audit_entry(event: ImportEvent, actor: Actor) -> AuditEntry:
    if isinstance(event, ImportRowResolved):
        return AuditEntry(
            occurred_at=event.occurred_at,
            actor=actor.name,
            event=ROW_EVENTS[type(event)],
            entity=IMPORT_ROW_ENTITY,
            entity_id=import_row_id(event.batch_id, event.line),
            sku=event.sku,
            before=resolution_object(event.before),
            after=resolution_object(event.after),
            context={
                "batch_id": str(event.batch_id),
                "line": event.line,
                "file_sha256": event.file_sha256,
                "original_issues": list(event.original_issues),
            },
        )
    name, before, after, context = describe_import(event)
    return AuditEntry(
        occurred_at=event.occurred_at,
        actor=actor.name,
        event=name,
        entity=IMPORT_BATCH_ENTITY,
        entity_id=str(event.batch_id),
        sku=None,
        before=before,
        after=after,
        context={"file_sha256": event.file_sha256, **context},
    )


def describe_import(event: ImportEvent) -> Description:
    match event:
        case ImportStarted():
            return (
                "import.started",
                None,
                PENDING,
                {"file_name": event.file_name, "rows": event.rows, "summary": dict(event.summary)},
            )
        case ImportCommitted():
            return (
                "import.committed",
                PENDING,
                {"status": BatchStatus.COMMITTED.value},
                {"created": event.created, "updated": event.updated, "skipped": event.skipped},
            )
        case ImportDiscarded():
            return "import.discarded", PENDING, {"status": BatchStatus.DISCARDED.value}, {}
    raise TypeError(f"No audit description for {type(event).__name__}.")


def json_object(values: Mapping[str, AuditValue]) -> JsonObject:
    return {name: json_value(value) for name, value in values.items()}


def resolution_object(values: Mapping[str, ResolutionValue]) -> JsonObject:
    return {name: json_value(value) for name, value in values.items()}


def json_value(value: AuditValue | ResolutionValue) -> JsonValue:
    if isinstance(value, tuple):
        return list(value)
    return value
