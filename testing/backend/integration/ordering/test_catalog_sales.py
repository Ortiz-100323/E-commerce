from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ecommerce.catalog.domain.product import Product, new_product_id
from ecommerce.catalog.infrastructure.unit_of_work import SqlAlchemyCatalogUnitOfWorkFactory
from ecommerce.integration.catalog_sales import CatalogSales
from ecommerce.ordering.application.audit import SHOP_ACTOR
from ecommerce.shared_kernel.domain.actor import Actor
from ecommerce.shared_kernel.infrastructure.audit import append_entries
from ecommerce.shared_kernel.infrastructure.database import create_session_factory

AT = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
ORDER = "00000000-0000-4000-8000-0000000000aa"


@pytest.fixture
def sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


async def create(
    sessions: async_sessionmaker[AsyncSession],
    sku: str,
    price: str = "89.99",
    stock: int = 10,
    *,
    archived: bool = False,
) -> Product:
    product = Product.create(
        product_id=new_product_id(),
        sku=sku,
        name=f"Product {sku}",
        description="",
        category="Misc",
        price=Decimal(price),
        stock=stock,
        weight_kg=Decimal("0.5"),
        gift=Decimal(price) == 0,
        at=AT,
    )
    if archived:
        product.archive(at=AT)
    async with SqlAlchemyCatalogUnitOfWorkFactory(sessions)(Actor("Antonio")) as work:
        await work.products.add(product)
        await work.commit()
    return product


async def test_locked_products_are_offered_as_sale_snapshots(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    shoes = await create(sessions, "RS-001")
    gift = await create(sessions, "GF-002", "0.00", 3)
    await create(sessions, "MB-001", archived=True)

    async with sessions() as session:
        found = await CatalogSales(session).lock_for_sale(["RS-001", "MB-001", "GF-002", "ZZ-9"])

    assert sorted(found) == ["GF-002", "MB-001", "RS-001"]
    assert found["RS-001"].product_id == shoes.id
    assert (found["RS-001"].price, found["RS-001"].stock, found["RS-001"].active) == (
        Decimal("89.99"),
        10,
        True,
    )
    assert (found["GF-002"].gift, found["GF-002"].product_id) == (True, gift.id)
    assert found["MB-001"].active is False


async def test_decreasing_stock_saves_the_product_and_audits_the_order(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    shoes = await create(sessions, "RS-001")

    async with sessions() as session:
        sales = CatalogSales(session)
        await sales.lock_for_sale(["RS-001"])
        await sales.decrease_stock("RS-001", 3, order_reference=ORDER, at=AT)
        entries = sales.take_audit_entries(SHOP_ACTOR)
        await append_entries(session, entries)
        await session.commit()

    async with SqlAlchemyCatalogUnitOfWorkFactory(sessions)() as work:
        stored = await work.products.get(shoes.id)
        history = await work.audit_log.entries_for("product", str(shoes.id))

    assert stored is not None
    assert (stored.stock.value, stored.version) == (7, 2)
    assert [entry.event for entry in entries] == ["product.stock_decreased"]
    decreased = history[-1]
    assert decreased.event == "product.stock_decreased"
    assert decreased.actor == "Shop checkout"
    assert decreased.before == {"stock": 10}
    assert decreased.after == {"stock": 7}
    assert decreased.context["order_reference"] == ORDER
    assert decreased.context["source"] == "checkout"
    assert sales.take_audit_entries(SHOP_ACTOR) == []


async def test_stock_can_only_be_decreased_for_a_locked_product(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await create(sessions, "RS-001")

    async with sessions() as session:
        with pytest.raises(KeyError):
            await CatalogSales(session).decrease_stock("RS-001", 1, order_reference=ORDER, at=AT)
