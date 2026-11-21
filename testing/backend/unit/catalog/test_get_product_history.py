from datetime import UTC, datetime
from uuid import UUID

import pytest

from ecommerce.catalog.application.get_product_history import GetProductHistory
from ecommerce.catalog.domain.errors import ProductNotFound
from ecommerce.catalog.domain.product import Product, ProductId
from ecommerce.shared_kernel.application.audit import AuditEntry
from fakes import InMemoryCatalog

PRODUCT_ID = ProductId(UUID("00000000-0000-4000-8000-000000000001"))
OTHER_ID = UUID("00000000-0000-4000-8000-000000000002")
AT = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)


def entry(entity_id: UUID, event: str) -> AuditEntry:
    return AuditEntry(
        occurred_at=AT,
        actor="Antonio",
        event=event,
        entity="product",
        entity_id=str(entity_id),
        sku="RS-001",
        before=None,
        after={},
    )


def stored_catalog() -> InMemoryCatalog:
    catalog = InMemoryCatalog()
    catalog.products.items[PRODUCT_ID] = Product.create(
        product_id=PRODUCT_ID,
        sku="RS-001",
        name="Running Shoes",
        description="",
        category="Sports",
        price="89.99",
        stock=10,
        weight_kg="0.8",
        gift=False,
        at=AT,
    )
    return catalog


async def test_returns_the_products_entries_in_the_order_they_were_written() -> None:
    catalog = stored_catalog()
    catalog.audit_log.entries = [
        entry(PRODUCT_ID, "product.created"),
        entry(OTHER_ID, "product.created"),
        entry(PRODUCT_ID, "product.changed"),
    ]

    entries = await GetProductHistory(catalog).execute(PRODUCT_ID)

    assert [item.event for item in entries] == ["product.created", "product.changed"]


async def test_reads_without_an_actor() -> None:
    catalog = stored_catalog()

    await GetProductHistory(catalog).execute(PRODUCT_ID)

    assert [work.actor for work in catalog.opened] == [None]


async def test_an_unknown_product_is_not_found() -> None:
    with pytest.raises(ProductNotFound) as raised:
        await GetProductHistory(InMemoryCatalog()).execute(OTHER_ID)

    assert raised.value.product_id == OTHER_ID
