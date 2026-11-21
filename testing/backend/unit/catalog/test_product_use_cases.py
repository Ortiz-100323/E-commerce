from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from ecommerce.catalog.application.products import (
    ArchiveProduct,
    CreateProduct,
    GetProduct,
    ListCategories,
    NewProduct,
    ProductFields,
    ProductQuery,
    ProductSort,
    ProductView,
    RestoreProduct,
    SearchProducts,
    StatusFilter,
    UpdateProduct,
)
from ecommerce.catalog.domain.errors import (
    DuplicateSku,
    InvalidProduct,
    ProductNotFound,
    VersionConflict,
)
from ecommerce.catalog.domain.product import INITIAL_VERSION, Product, ProductId
from ecommerce.catalog.domain.value_objects import ProductTag
from ecommerce.shared_kernel.domain.actor import Actor
from fakes import FakeProductQueries, InMemoryCatalog, SequenceClock

CREATED_AT = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)
LATER = CREATED_AT + timedelta(hours=1)
ANTONIO = Actor("Antonio")
MARIA = Actor("Maria")
UNKNOWN = UUID("00000000-0000-4000-8000-000000000099")


def new_product(**overrides: Any) -> NewProduct:
    values: dict[str, Any] = {
        "sku": "rs-001",
        "name": "Running Shoes",
        "description": "Lightweight shoes.",
        "category": "Sports",
        "price": Decimal("89.99"),
        "stock": 10,
        "weight_kg": Decimal("0.8"),
        "gift": False,
    }
    values.update(overrides)
    return NewProduct(**values)


def fields(**overrides: Any) -> ProductFields:
    values: dict[str, Any] = {
        "name": "Running Shoes",
        "description": "Lightweight shoes.",
        "category": "Sports",
        "price": Decimal("89.99"),
        "stock": 10,
        "weight_kg": Decimal("0.8"),
        "gift": False,
    }
    values.update(overrides)
    return ProductFields(**values)


async def created(catalog: InMemoryCatalog) -> ProductView:
    return await CreateProduct(catalog, SequenceClock(CREATED_AT)).execute(new_product(), ANTONIO)


def events(catalog: InMemoryCatalog) -> list[tuple[str, str]]:
    return [(entry.event, entry.actor) for entry in catalog.audit_log.entries]


async def test_create_stores_the_product_and_returns_its_view() -> None:
    catalog = InMemoryCatalog()

    view = await created(catalog)

    stored = catalog.products.items[ProductId(view.id)]
    assert (view.sku, view.price, view.currency, view.weight_kg) == (
        "RS-001",
        Decimal("89.99"),
        "USD",
        Decimal("0.800"),
    )
    assert (view.version, view.created_at, view.status, view.is_sellable) == (
        INITIAL_VERSION,
        CREATED_AT,
        "ACTIVE",
        True,
    )
    assert view == ProductView.of(stored)
    assert events(catalog) == [("product.created", "Antonio")]
    assert [work.actor for work in catalog.opened] == [ANTONIO]


async def test_create_of_a_free_gift_records_the_gift_tag() -> None:
    catalog = InMemoryCatalog()

    view = await CreateProduct(catalog, SequenceClock(CREATED_AT)).execute(
        new_product(price=Decimal("0"), gift=True), ANTONIO
    )

    assert (view.gift, view.tags) == (True, ("GIFT",))


async def test_create_with_invalid_data_stores_nothing() -> None:
    catalog = InMemoryCatalog()

    with pytest.raises(InvalidProduct) as raised:
        await CreateProduct(catalog, SequenceClock()).execute(
            new_product(sku="bad sku", price=Decimal("0")), ANTONIO
        )

    assert {issue.code for issue in raised.value.issues} == {
        "invalid_sku_format",
        "zero_price_requires_gift",
    }
    assert catalog.products.items == {}
    assert catalog.opened == []


async def test_create_of_a_taken_sku_is_refused() -> None:
    catalog = InMemoryCatalog()
    await created(catalog)

    with pytest.raises(DuplicateSku):
        await created(catalog)

    assert len(catalog.products.items) == 1
    assert events(catalog) == [("product.created", "Antonio")]


async def test_update_replaces_the_details_and_moves_to_the_next_version() -> None:
    catalog = InMemoryCatalog()
    view = await created(catalog)

    updated = await UpdateProduct(catalog, SequenceClock(LATER)).execute(
        view.id,
        INITIAL_VERSION,
        fields(name="Trail Shoes", price=Decimal("0"), gift=True, stock=0),
        MARIA,
    )

    assert (updated.name, updated.price, updated.gift, updated.stock) == (
        "Trail Shoes",
        Decimal("0.00"),
        True,
        0,
    )
    assert (updated.version, updated.updated_at, updated.is_sellable) == (
        INITIAL_VERSION + 1,
        LATER,
        False,
    )
    assert events(catalog) == [("product.created", "Antonio"), ("product.changed", "Maria")]


async def test_update_that_changes_nothing_keeps_the_version_and_writes_nothing() -> None:
    catalog = InMemoryCatalog()
    view = await created(catalog)

    updated = await UpdateProduct(catalog, SequenceClock(LATER)).execute(
        view.id, INITIAL_VERSION, fields(), MARIA
    )

    assert (updated.version, updated.updated_at) == (INITIAL_VERSION, CREATED_AT)
    assert catalog.products.saves == 0
    assert events(catalog) == [("product.created", "Antonio")]


async def test_update_with_a_stale_version_is_a_conflict_and_changes_nothing() -> None:
    catalog = InMemoryCatalog()
    view = await created(catalog)
    update = UpdateProduct(catalog, SequenceClock(LATER))
    await update.execute(view.id, INITIAL_VERSION, fields(name="Trail Shoes"), MARIA)

    with pytest.raises(VersionConflict) as raised:
        await update.execute(view.id, INITIAL_VERSION, fields(price=Decimal("79.99")), ANTONIO)

    assert (raised.value.expected_version, raised.value.current_version) == (1, 2)
    assert events(catalog) == [("product.created", "Antonio"), ("product.changed", "Maria")]


async def test_a_retried_update_that_is_already_in_place_returns_the_current_product() -> None:
    catalog = InMemoryCatalog()
    view = await created(catalog)
    update = UpdateProduct(catalog, SequenceClock(LATER))
    first = await update.execute(view.id, INITIAL_VERSION, fields(name="Trail Shoes"), MARIA)

    retried = await update.execute(view.id, INITIAL_VERSION, fields(name="Trail Shoes"), MARIA)

    assert retried == first
    assert events(catalog) == [("product.created", "Antonio"), ("product.changed", "Maria")]


async def test_update_with_invalid_data_is_refused_before_the_version_check() -> None:
    catalog = InMemoryCatalog()
    view = await created(catalog)

    with pytest.raises(InvalidProduct):
        await UpdateProduct(catalog, SequenceClock(LATER)).execute(
            view.id, 7, fields(price=Decimal("-1")), MARIA
        )


async def test_archive_and_restore_change_the_status_once() -> None:
    catalog = InMemoryCatalog()
    view = await created(catalog)
    archive = ArchiveProduct(catalog, SequenceClock(LATER))
    restore = RestoreProduct(catalog, SequenceClock(LATER))

    archived = await archive.execute(view.id, MARIA)
    archived_again = await archive.execute(view.id, MARIA)
    restored = await restore.execute(view.id, MARIA)
    restored_again = await restore.execute(view.id, MARIA)

    assert (archived.status, archived.is_sellable, archived.version) == ("ARCHIVED", False, 2)
    assert archived_again == archived
    assert (restored.status, restored.version) == ("ACTIVE", 3)
    assert restored_again == restored
    assert [event for event, _ in events(catalog)] == [
        "product.created",
        "product.archived",
        "product.restored",
    ]


async def test_get_returns_the_product_without_an_actor() -> None:
    catalog = InMemoryCatalog()
    view = await created(catalog)

    assert await GetProduct(catalog).execute(view.id) == view
    assert catalog.opened[-1].actor is None


@pytest.mark.parametrize(
    "use_case",
    [
        lambda catalog: GetProduct(catalog).execute(UNKNOWN),
        lambda catalog: UpdateProduct(catalog, SequenceClock()).execute(
            UNKNOWN, 1, fields(), MARIA
        ),
        lambda catalog: ArchiveProduct(catalog, SequenceClock()).execute(UNKNOWN, MARIA),
        lambda catalog: RestoreProduct(catalog, SequenceClock()).execute(UNKNOWN, MARIA),
    ],
)
async def test_an_unknown_product_is_not_found(use_case: Any) -> None:
    with pytest.raises(ProductNotFound) as raised:
        await use_case(InMemoryCatalog())

    assert raised.value.product_id == UNKNOWN


async def test_search_passes_the_query_on_and_returns_a_page() -> None:
    view = ProductView.of(
        Product.create(
            product_id=ProductId(UNKNOWN),
            sku="RS-001",
            name="Running Shoes",
            description="",
            category="Sports",
            price="89.99",
            stock=10,
            weight_kg="0.8",
            gift=False,
            at=CREATED_AT,
        )
    )
    queries = FakeProductQueries(items=[view])
    query = ProductQuery(
        q="shoes",
        tag=ProductTag.GIFT,
        status=StatusFilter.ALL,
        sort=ProductSort.PRICE_DESC,
        page=3,
        page_size=5,
    )

    page = await SearchProducts(queries).execute(query)

    assert queries.queries == [query]
    assert (list(page.items), page.total, page.page, page.page_size) == ([view], 1, 3, 5)
    assert query.offset == 10


async def test_list_categories_returns_the_names() -> None:
    queries = FakeProductQueries(categories=["Electronics", "Sports"])

    assert await ListCategories(queries).execute() == ["Electronics", "Sports"]
