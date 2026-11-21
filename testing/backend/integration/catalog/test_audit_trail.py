from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ecommerce.catalog.domain.errors import DuplicateSku, ProductAlreadyExists, VersionConflict
from ecommerce.catalog.domain.product import INITIAL_VERSION, Product, ProductId
from ecommerce.catalog.infrastructure.unit_of_work import (
    SqlAlchemyCatalogUnitOfWork,
    SqlAlchemyCatalogUnitOfWorkFactory,
)
from ecommerce.shared_kernel.application.audit import ActorRequired, AuditEntry
from ecommerce.shared_kernel.domain.actor import Actor
from ecommerce.shared_kernel.infrastructure.database import create_session_factory

CREATED_AT = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)
LATER = CREATED_AT + timedelta(hours=1)
LATEST = CREATED_AT + timedelta(hours=2)
ANTONIO = Actor("Antonio")
MARIA = Actor("Maria")


def product_id(number: int) -> ProductId:
    return ProductId(UUID(f"00000000-0000-4000-8000-{number:012d}"))


def new_product(number: int = 1, **overrides: Any) -> Product:
    values: dict[str, Any] = {
        "product_id": product_id(number),
        "sku": f"RS-{number:03d}",
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
    return Product.create(**values)


@pytest.fixture
def catalog(engine: AsyncEngine) -> SqlAlchemyCatalogUnitOfWorkFactory:
    return SqlAlchemyCatalogUnitOfWorkFactory(create_session_factory(engine))


@pytest.fixture
def sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


async def create(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory, *products: Product, actor: Actor = ANTONIO
) -> None:
    async with catalog(actor) as work:
        for product in products:
            await work.products.add(product)
        await work.commit()


async def load(catalog: SqlAlchemyCatalogUnitOfWorkFactory, number: int = 1) -> Product:
    async with catalog() as work:
        found = await work.products.get(product_id(number))
    assert found is not None
    return found


async def save(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory, product: Product, actor: Actor = MARIA
) -> None:
    async with catalog(actor) as work:
        await work.products.save(product)
        await work.commit()


async def history(catalog: SqlAlchemyCatalogUnitOfWorkFactory, number: int = 1) -> list[AuditEntry]:
    async with catalog() as work:
        return await work.audit_log.entries_for("product", str(product_id(number)))


async def entry_count(engine: AsyncEngine) -> int:
    async with engine.connect() as connection:
        count = await connection.scalar(text("SELECT count(*) FROM audit_log"))
    assert isinstance(count, int)
    return count


async def test_creating_a_product_writes_one_entry_with_the_full_product(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory,
) -> None:
    await create(catalog, new_product())

    [entry] = await history(catalog)

    assert (entry.event, entry.actor, entry.occurred_at, entry.sku) == (
        "product.created",
        "Antonio",
        CREATED_AT,
        "RS-001",
    )
    assert entry.before is None
    assert entry.after == {
        "sku": "RS-001",
        "name": "Running Shoes",
        "description": "Lightweight shoes.",
        "category": "Sports",
        "price": "89.99",
        "stock": 10,
        "weight_kg": "0.800",
        "tags": [],
        "status": "ACTIVE",
    }


async def test_a_change_writes_one_entry_with_before_after_actor_and_time(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory,
) -> None:
    await create(catalog, new_product())
    product = await load(catalog)
    product.revise(name="Trail Shoes", price="0", gift=True, at=LATER)

    await save(catalog, product)

    created, changed = await history(catalog)
    assert created.event == "product.created"
    assert (changed.event, changed.actor, changed.occurred_at) == (
        "product.changed",
        "Maria",
        LATER,
    )
    assert changed.before == {"name": "Running Shoes", "price": "89.99", "tags": []}
    assert changed.after == {"name": "Trail Shoes", "price": "0.00", "tags": ["GIFT"]}


async def test_archive_restore_and_a_sale_each_write_one_entry_in_order(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory,
) -> None:
    await create(catalog, new_product())
    product = await load(catalog)

    product.archive(at=LATER)
    await save(catalog, product)
    product.restore(at=LATER)
    await save(catalog, product)
    product.decrease_stock(3, order_reference="ORDER-1", at=LATEST)
    await save(catalog, product)

    entries = await history(catalog)
    assert [(entry.event, entry.before, entry.after) for entry in entries[1:]] == [
        ("product.archived", {"status": "ACTIVE"}, {"status": "ARCHIVED"}),
        ("product.restored", {"status": "ARCHIVED"}, {"status": "ACTIVE"}),
        ("product.stock_decreased", {"stock": 10}, {"stock": 7}),
    ]
    assert entries[-1].context == {"quantity": 3, "order_reference": "ORDER-1"}


async def test_the_history_holds_only_that_products_entries_oldest_first(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory,
) -> None:
    await create(catalog, new_product(1), new_product(2))
    first = await load(catalog, 1)
    first.rename("Trail Shoes", at=LATER)
    await save(catalog, first)

    assert [entry.event for entry in await history(catalog, 1)] == [
        "product.created",
        "product.changed",
    ]
    assert [entry.sku for entry in await history(catalog, 2)] == ["RS-002"]


async def test_work_that_is_not_committed_leaves_neither_the_change_nor_its_entry(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory, engine: AsyncEngine
) -> None:
    async with catalog(ANTONIO) as work:
        await work.products.add(new_product())

    async with catalog() as work:
        assert await work.products.get(product_id(1)) is None
    assert await entry_count(engine) == 0


async def test_an_error_inside_the_unit_of_work_rolls_back_the_change_and_its_entry(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory, engine: AsyncEngine
) -> None:
    await create(catalog, new_product())
    product = await load(catalog)
    product.rename("Trail Shoes", at=LATER)

    with pytest.raises(LookupError):
        async with catalog(MARIA) as work:
            await work.products.save(product)
            raise LookupError("something failed after the save")

    assert (await load(catalog)).name.value == "Running Shoes"
    assert await entry_count(engine) == 1


async def test_a_rollback_discards_the_entries_waiting_to_be_written(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory, engine: AsyncEngine
) -> None:
    async with catalog(ANTONIO) as work:
        await work.products.add(new_product(1))
        await work.rollback()
        await work.products.add(new_product(2))
        await work.commit()

    assert [entry.sku for entry in await history(catalog, 2)] == ["RS-002"]
    assert await entry_count(engine) == 1


@pytest.fixture
async def failing_audit_writes(engine: AsyncEngine) -> AsyncIterator[None]:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "CREATE FUNCTION fail_audit_write() RETURNS trigger LANGUAGE plpgsql AS "
                "$$ BEGIN RAISE EXCEPTION 'audit write failed'; END $$"
            )
        )
        await connection.execute(
            text(
                "CREATE TRIGGER fail_audit_write BEFORE INSERT ON audit_log "
                "FOR EACH ROW EXECUTE FUNCTION fail_audit_write()"
            )
        )
    yield
    async with engine.begin() as connection:
        await connection.execute(text("DROP TRIGGER fail_audit_write ON audit_log"))
        await connection.execute(text("DROP FUNCTION fail_audit_write()"))


async def test_when_the_entry_cannot_be_written_the_change_is_not_stored(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory, failing_audit_writes: None
) -> None:
    with pytest.raises(DBAPIError, match="audit write failed"):
        await create(catalog, new_product())

    async with catalog() as work:
        assert await work.products.get(product_id(1)) is None


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_log SET actor = 'Mallory'",
        "DELETE FROM audit_log",
        "UPDATE audit_log SET actor = 'Mallory' WHERE id = -1",
        "DELETE FROM audit_log WHERE id = -1",
    ],
)
async def test_entries_can_never_be_updated_or_deleted(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory, engine: AsyncEngine, statement: str
) -> None:
    await create(catalog, new_product())

    with pytest.raises(DBAPIError, match="audit_log is append-only"):
        async with engine.begin() as connection:
            await connection.execute(text(statement))

    [entry] = await history(catalog)
    assert entry.actor == "Antonio"


async def test_committing_changes_without_an_actor_stores_nothing(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory, engine: AsyncEngine
) -> None:
    with pytest.raises(ActorRequired):
        async with catalog() as work:
            await work.products.add(new_product())
            await work.commit()

    async with catalog() as work:
        assert await work.products.get(product_id(1)) is None
    assert await entry_count(engine) == 0


async def test_a_read_only_unit_of_work_needs_no_actor(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory,
) -> None:
    await create(catalog, new_product())

    async with catalog() as work:
        assert await work.products.get(product_id(1)) is not None
        await work.commit()


async def test_a_refused_save_writes_no_entry(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory,
) -> None:
    await create(catalog, new_product())
    winner = await load(catalog)
    stale = await load(catalog)
    winner.rename("Trail Shoes", at=LATER)
    await save(catalog, winner)

    stale.reprice("79.99", at=LATER)
    with pytest.raises(VersionConflict):
        await save(catalog, stale, actor=ANTONIO)

    assert [(entry.event, entry.actor) for entry in await history(catalog)] == [
        ("product.created", "Antonio"),
        ("product.changed", "Maria"),
    ]


async def test_a_refused_create_writes_no_entry_and_the_rest_of_the_work_is_kept(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory, engine: AsyncEngine
) -> None:
    await create(catalog, new_product(1))

    async with catalog(MARIA) as work:
        with pytest.raises(ProductAlreadyExists):
            await work.products.add(new_product(1))
        with pytest.raises(DuplicateSku):
            await work.products.add(new_product(2, sku="RS-001"))
        await work.products.add(new_product(3))
        await work.commit()

    assert await entry_count(engine) == 2
    assert [entry.actor for entry in await history(catalog, 3)] == ["Maria"]


async def test_a_change_that_changes_nothing_creates_no_version_and_no_entry(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory,
) -> None:
    await create(catalog, new_product())
    product = await load(catalog)

    product.rename("Running Shoes", at=LATER)
    product.revise(price="89.99", stock=10, at=LATER)
    product.restore(at=LATER)
    await save(catalog, product)

    stored = await load(catalog)
    assert (stored.version, stored.updated_at) == (INITIAL_VERSION, CREATED_AT)
    assert len(await history(catalog)) == 1


async def test_archiving_twice_writes_one_entry(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory,
) -> None:
    await create(catalog, new_product())

    for _ in range(2):
        product = await load(catalog)
        product.archive(at=LATER)
        await save(catalog, product)

    assert [entry.event for entry in await history(catalog)] == [
        "product.created",
        "product.archived",
    ]
    assert (await load(catalog)).version == INITIAL_VERSION + 1


async def test_saving_the_same_product_twice_in_one_unit_of_work_logs_each_change_once(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory,
) -> None:
    await create(catalog, new_product())

    async with catalog(MARIA) as work:
        product = await work.products.get(product_id(1))
        assert product is not None
        product.rename("Trail Shoes", at=LATER)
        await work.products.save(product)
        await work.products.save(product)
        product.reprice("79.99", at=LATER)
        await work.products.save(product)
        await work.commit()

    changes = [entry.after for entry in await history(catalog) if entry.event == "product.changed"]
    assert changes == [{"name": "Trail Shoes"}, {"price": "79.99"}]
    assert (await load(catalog)).version == INITIAL_VERSION + 2


async def test_a_refused_save_retried_after_reloading_writes_exactly_one_entry(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory,
) -> None:
    await create(catalog, new_product())
    stale = await load(catalog)
    winner = await load(catalog)
    winner.rename("Trail Shoes", at=LATER)
    await save(catalog, winner)

    stale.reprice("79.99", at=LATER)
    with pytest.raises(VersionConflict):
        await save(catalog, stale, actor=ANTONIO)
    fresh = await load(catalog)
    fresh.reprice("79.99", at=LATEST)
    await save(catalog, fresh, actor=ANTONIO)

    assert [(entry.actor, entry.after) for entry in (await history(catalog))[1:]] == [
        ("Maria", {"name": "Trail Shoes"}),
        ("Antonio", {"price": "79.99"}),
    ]


async def test_two_buyers_racing_for_the_last_unit_leave_one_sale_entry(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory,
) -> None:
    await create(catalog, new_product(stock=1))
    first_buyer = await load(catalog)
    second_buyer = await load(catalog)

    first_buyer.decrease_stock(1, order_reference="ORDER-1", at=LATER)
    await save(catalog, first_buyer)
    second_buyer.decrease_stock(1, order_reference="ORDER-2", at=LATER)
    with pytest.raises(VersionConflict):
        await save(catalog, second_buyer)

    sales = [entry for entry in await history(catalog) if entry.event == "product.stock_decreased"]
    assert [sale.context["order_reference"] for sale in sales] == ["ORDER-1"]
    assert (await load(catalog)).stock.value == 0


async def test_the_catalog_unit_of_work_is_only_usable_while_open(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    work = SqlAlchemyCatalogUnitOfWork(sessions, ANTONIO)

    with pytest.raises(RuntimeError):
        await work.commit()
    with pytest.raises(RuntimeError):
        await work.rollback()
