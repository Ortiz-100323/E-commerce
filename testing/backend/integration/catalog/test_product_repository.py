from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ecommerce.catalog.domain.errors import (
    DuplicateSku,
    InsufficientStock,
    ProductAlreadyExists,
    ProductNotFound,
    ProductNotSellable,
    VersionConflict,
)
from ecommerce.catalog.domain.product import INITIAL_VERSION, Product, ProductId
from ecommerce.catalog.domain.value_objects import MAX_PRICE, MAX_STOCK, MAX_WEIGHT_KG, Sku
from ecommerce.catalog.infrastructure.unit_of_work import SqlAlchemyCatalogUnitOfWork
from ecommerce.shared_kernel.domain.actor import Actor
from ecommerce.shared_kernel.infrastructure.database import create_session_factory

CREATED_AT = datetime(2026, 11, 21, 10, 0, 0, 123456, tzinfo=UTC)
LATER = CREATED_AT + timedelta(hours=1)
TESTER = Actor("Tester")


def product_id(number: int) -> ProductId:
    return ProductId(UUID(f"00000000-0000-4000-8000-{number:012d}"))


def make_product(number: int = 1, **overrides: Any) -> Product:
    values: dict[str, Any] = {
        "product_id": product_id(number),
        "sku": f"rs-{number:03d}",
        "name": "Running Shoes",
        "description": "Lightweight shoes.",
        "category": "Sports",
        "price": "89.99",
        "stock": 10,
        "weight_kg": "0.800",
        "gift": False,
        "at": CREATED_AT,
    }
    values.update(overrides)
    product = Product.create(**values)
    product.pull_events()
    return product


@pytest.fixture
def sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


def unit_of_work(sessions: async_sessionmaker[AsyncSession]) -> SqlAlchemyCatalogUnitOfWork:
    return SqlAlchemyCatalogUnitOfWork(sessions, TESTER)


async def store(sessions: async_sessionmaker[AsyncSession], *products: Product) -> None:
    async with unit_of_work(sessions) as work:
        for product in products:
            await work.products.add(product)
        await work.commit()


async def load(sessions: async_sessionmaker[AsyncSession], number: int) -> Product:
    async with unit_of_work(sessions) as work:
        found = await work.products.get(product_id(number))
    assert found is not None
    return found


def state(product: Product) -> tuple[object, ...]:
    return (
        product.id,
        product.snapshot(),
        product.version,
        product.created_at,
        product.updated_at,
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"price": "0", "gift": True, "weight_kg": "0", "stock": 0},
        {"price": "10.50", "gift": True, "description": ""},
        {"price": str(MAX_PRICE), "stock": MAX_STOCK, "weight_kg": str(MAX_WEIGHT_KG)},
        {"price": "0.01", "weight_kg": "0.001"},
        {
            "name": "Smart Watch™ — Pro",
            "description": "Line one\nLine two",
            "category": "Électronique",
        },
        {"name": "Robert'); DROP TABLE products;--"},
    ],
)
async def test_a_product_round_trips_with_every_field_intact(
    sessions: async_sessionmaker[AsyncSession], overrides: dict[str, Any]
) -> None:
    product = make_product(**overrides)

    await store(sessions, product)
    loaded = await load(sessions, 1)

    assert state(loaded) == state(product)
    assert str(loaded.price.amount) == str(product.price.amount)
    assert str(loaded.weight.kg) == str(product.weight.kg)
    assert loaded.pull_events() == []


async def test_an_archived_product_round_trips(sessions: async_sessionmaker[AsyncSession]) -> None:
    product = make_product()
    product.archive(at=LATER)
    await store(sessions, product)

    assert state(await load(sessions, 1)) == state(product)


async def test_get_returns_none_for_an_unknown_product(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with unit_of_work(sessions) as work:
        assert await work.products.get(product_id(99)) is None


async def test_get_by_sku_finds_the_product(sessions: async_sessionmaker[AsyncSession]) -> None:
    await store(sessions, make_product(1), make_product(2))

    async with unit_of_work(sessions) as work:
        found = await work.products.get_by_sku(Sku("rs-002"))
        missing = await work.products.get_by_sku(Sku("NOPE-1"))

    assert found is not None
    assert found.id == product_id(2)
    assert missing is None


async def test_work_that_is_not_committed_is_not_stored(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with unit_of_work(sessions) as work:
        await work.products.add(make_product())

    async with unit_of_work(sessions) as work:
        assert await work.products.get(product_id(1)) is None


async def test_a_second_product_with_the_same_sku_is_rejected(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await store(sessions, make_product(1, sku="RS-001"))

    async with unit_of_work(sessions) as work:
        with pytest.raises(DuplicateSku) as raised:
            await work.products.add(make_product(2, sku="rs-001"))
        await work.products.add(make_product(3, sku="RS-003"))
        await work.commit()

    assert raised.value.sku == "RS-001"
    assert (await load(sessions, 3)).sku == Sku("RS-003")


async def test_save_stores_the_changes_and_moves_to_the_next_version(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await store(sessions, make_product())

    async with unit_of_work(sessions) as work:
        product = await work.products.get(product_id(1))
        assert product is not None
        product.revise(name="Trail Shoes", price="0", gift=True, stock=3, at=LATER)
        await work.products.save(product)
        await work.commit()

    assert product.version == INITIAL_VERSION + 1
    assert state(await load(sessions, 1)) == state(product)


async def test_save_with_a_stale_version_raises_a_version_conflict(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await store(sessions, make_product())
    first = await load(sessions, 1)
    second = await load(sessions, 1)

    async with unit_of_work(sessions) as work:
        first.rename("Trail Shoes", at=LATER)
        await work.products.save(first)
        await work.commit()

    async with unit_of_work(sessions) as work:
        second.reprice("79.99", at=LATER)
        with pytest.raises(VersionConflict) as raised:
            await work.products.save(second)

    assert (raised.value.expected_version, raised.value.current_version) == (1, 2)
    stored = await load(sessions, 1)
    assert stored.name.value == "Trail Shoes"
    assert str(stored.price.amount) == "89.99"
    assert second.version == INITIAL_VERSION


async def test_two_buyers_cannot_both_take_the_last_unit(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await store(sessions, make_product(stock=1))
    first_buyer = await load(sessions, 1)
    second_buyer = await load(sessions, 1)

    async with unit_of_work(sessions) as work:
        first_buyer.decrease_stock(1, order_reference="ORDER-1", at=LATER)
        await work.products.save(first_buyer)
        await work.commit()

    async with unit_of_work(sessions) as work:
        second_buyer.decrease_stock(1, order_reference="ORDER-2", at=LATER)
        with pytest.raises(VersionConflict):
            await work.products.save(second_buyer)

    stored = await load(sessions, 1)
    assert stored.stock.value == 0
    assert stored.version == INITIAL_VERSION + 1


async def test_once_the_stock_reaches_zero_the_next_sale_is_refused(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await store(sessions, make_product(stock=1))

    async with unit_of_work(sessions) as work:
        product = await work.products.get(product_id(1))
        assert product is not None
        product.decrease_stock(1, order_reference="ORDER-1", at=LATER)
        await work.products.save(product)
        await work.commit()

    sold_out = await load(sessions, 1)
    with pytest.raises(InsufficientStock) as raised:
        sold_out.decrease_stock(1, order_reference="ORDER-2", at=LATER)

    assert (raised.value.requested, raised.value.available) == (1, 0)
    assert sold_out.pull_events() == []
    assert (await load(sessions, 1)).stock.value == 0


async def test_a_sale_larger_than_the_stock_leaves_the_stored_stock_unchanged(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await store(sessions, make_product(stock=2))
    product = await load(sessions, 1)

    with pytest.raises(InsufficientStock) as raised:
        product.decrease_stock(3, order_reference="ORDER-1", at=LATER)

    assert (raised.value.requested, raised.value.available) == (3, 2)
    assert product.stock.value == 2
    assert product.pull_events() == []
    assert (await load(sessions, 1)).stock.value == 2


async def test_an_archived_product_cannot_be_sold_and_keeps_its_stock(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    archived = make_product(stock=5)
    archived.archive(at=LATER)
    await store(sessions, archived)

    product = await load(sessions, 1)
    with pytest.raises(ProductNotSellable) as raised:
        product.decrease_stock(1, order_reference="ORDER-1", at=LATER)

    assert raised.value.reason == "archived"
    assert (await load(sessions, 1)).stock.value == 5


async def test_a_retried_create_is_refused_and_never_stores_a_second_product(
    sessions: async_sessionmaker[AsyncSession], engine: AsyncEngine
) -> None:
    await store(sessions, make_product())

    async with unit_of_work(sessions) as work:
        with pytest.raises(ProductAlreadyExists) as raised:
            await work.products.add(make_product())
        await work.products.add(make_product(2))
        await work.commit()

    async with engine.connect() as connection:
        count = await connection.scalar(text("SELECT count(*) FROM products"))

    assert raised.value.product_id == product_id(1)
    assert count == 2


async def test_a_failed_save_can_be_retried_after_reloading(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await store(sessions, make_product())
    stale = await load(sessions, 1)

    async with unit_of_work(sessions) as work:
        winner = await work.products.get(product_id(1))
        assert winner is not None
        winner.rename("Trail Shoes", at=LATER)
        await work.products.save(winner)
        await work.commit()

    async with unit_of_work(sessions) as work:
        stale.reprice("79.99", at=LATER)
        with pytest.raises(VersionConflict):
            await work.products.save(stale)

    async with unit_of_work(sessions) as work:
        fresh = await work.products.get(product_id(1))
        assert fresh is not None
        fresh.reprice("79.99", at=LATER)
        await work.products.save(fresh)
        await work.commit()

    stored = await load(sessions, 1)
    assert (stored.name.value, str(stored.price.amount), stored.version) == (
        "Trail Shoes",
        "79.99",
        INITIAL_VERSION + 2,
    )


async def test_save_of_a_product_that_was_never_stored_raises_not_found(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    never_stored = make_product()
    never_stored.rename("Trail Shoes", at=LATER)

    async with unit_of_work(sessions) as work:
        with pytest.raises(ProductNotFound):
            await work.products.save(never_stored)


async def test_the_repository_is_only_available_inside_the_unit_of_work(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    with pytest.raises(RuntimeError):
        _ = unit_of_work(sessions).products


async def test_the_sql_looking_name_leaves_the_table_intact(
    sessions: async_sessionmaker[AsyncSession], engine: AsyncEngine
) -> None:
    await store(sessions, make_product(name="Robert'); DROP TABLE products;--"))

    async with engine.connect() as connection:
        count = await connection.scalar(text("SELECT count(*) FROM products"))

    assert count == 1
