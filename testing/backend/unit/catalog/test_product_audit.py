from datetime import UTC, datetime
from uuid import UUID

import pytest

from ecommerce.catalog.application.audit import PRODUCT_ENTITY, audit_entries
from ecommerce.catalog.domain.events import (
    FieldChange,
    ProductArchived,
    ProductChanged,
    ProductCreated,
    ProductEvent,
    ProductRestored,
    StockDecreased,
)
from ecommerce.shared_kernel.application.audit import AuditEntry
from ecommerce.shared_kernel.domain.actor import Actor

PRODUCT_ID = UUID("00000000-0000-4000-8000-000000000001")
AT = datetime(2026, 11, 21, 14, 2, 11, tzinfo=UTC)
ANTONIO = Actor("Antonio")
BASE = {"product_id": PRODUCT_ID, "sku": "RS-001", "occurred_at": AT}


def only_entry(event: ProductEvent) -> AuditEntry:
    entries = audit_entries([event], ANTONIO)
    assert len(entries) == 1
    entry = entries[0]
    assert (entry.occurred_at, entry.actor, entry.entity, entry.entity_id, entry.sku) == (
        AT,
        "Antonio",
        PRODUCT_ENTITY,
        str(PRODUCT_ID),
        "RS-001",
    )
    return entry


def test_a_created_product_records_its_full_snapshot_as_after() -> None:
    snapshot = {"sku": "RS-001", "name": "Running Shoes", "stock": 10, "tags": ("GIFT",)}

    entry = only_entry(ProductCreated(**BASE, snapshot=snapshot))

    assert entry.event == "product.created"
    assert entry.before is None
    assert entry.after == {"sku": "RS-001", "name": "Running Shoes", "stock": 10, "tags": ["GIFT"]}
    assert entry.context == {}


def test_a_change_records_only_the_changed_fields_before_and_after() -> None:
    changes = {
        "price": FieldChange("129.99", "119.99"),
        "tags": FieldChange((), ("GIFT",)),
    }

    entry = only_entry(ProductChanged(**BASE, changes=changes))

    assert entry.event == "product.changed"
    assert entry.before == {"price": "129.99", "tags": []}
    assert entry.after == {"price": "119.99", "tags": ["GIFT"]}


@pytest.mark.parametrize(
    ("event", "name", "before", "after"),
    [
        (ProductArchived(**BASE), "product.archived", "ACTIVE", "ARCHIVED"),
        (ProductRestored(**BASE), "product.restored", "ARCHIVED", "ACTIVE"),
    ],
)
def test_archive_and_restore_record_the_status_change(
    event: ProductEvent, name: str, before: str, after: str
) -> None:
    entry = only_entry(event)

    assert entry.event == name
    assert entry.before == {"status": before}
    assert entry.after == {"status": after}


def test_a_stock_decrease_records_the_stock_and_the_order() -> None:
    event = StockDecreased(
        **BASE, quantity=2, stock_before=5, stock_after=3, order_reference="ORDER-1"
    )

    entry = only_entry(event)

    assert entry.event == "product.stock_decreased"
    assert entry.before == {"stock": 5}
    assert entry.after == {"stock": 3}
    assert entry.context == {"quantity": 2, "order_reference": "ORDER-1"}


def test_entries_keep_the_order_of_the_events() -> None:
    events = [ProductArchived(**BASE), ProductRestored(**BASE)]

    entries = audit_entries(events, ANTONIO)

    assert [entry.event for entry in entries] == ["product.archived", "product.restored"]


def test_an_unknown_event_is_a_programming_error() -> None:
    with pytest.raises(TypeError):
        audit_entries([ProductEvent(**BASE)], ANTONIO)
