from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.catalog.domain.product import Product, ProductId
from ecommerce.catalog.infrastructure.unit_of_work import SqlAlchemyCatalogUnitOfWorkFactory
from ecommerce.main import API_PREFIX, create_app
from ecommerce.shared_kernel.domain.actor import Actor
from ecommerce.shared_kernel.infrastructure.database import create_session_factory
from fakes import dependencies_factory
from problems import assert_problem

PRODUCT_ID = ProductId(UUID("00000000-0000-4000-8000-000000000001"))
CREATED_AT = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)
LATER = CREATED_AT + timedelta(hours=1)


def history_url(product_id: object) -> str:
    return f"{API_PREFIX}/products/{product_id}/history"


@pytest.fixture
def catalog(engine: AsyncEngine) -> SqlAlchemyCatalogUnitOfWorkFactory:
    return SqlAlchemyCatalogUnitOfWorkFactory(create_session_factory(engine))


@asynccontextmanager
async def api(catalog: SqlAlchemyCatalogUnitOfWorkFactory) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(dependencies_factory(catalog=catalog))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def store_a_changed_product(catalog: SqlAlchemyCatalogUnitOfWorkFactory) -> None:
    async with catalog(Actor("Antonio")) as work:
        await work.products.add(
            Product.create(
                product_id=PRODUCT_ID,
                sku="GK-088",
                name="Gaming Keyboard",
                description="",
                category="Electronics",
                price="129.99",
                stock=45,
                weight_kg="1.1",
                gift=False,
                at=CREATED_AT,
            )
        )
        await work.commit()
    async with catalog(Actor("Maria")) as work:
        product = await work.products.get(PRODUCT_ID)
        assert product is not None
        product.reprice("119.99", at=LATER)
        await work.products.save(product)
        await work.commit()


async def test_the_history_returns_the_products_entries_oldest_first(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory,
) -> None:
    await store_a_changed_product(catalog)

    async with api(catalog) as client:
        response = await client.get(history_url(PRODUCT_ID))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["product_id"] == str(PRODUCT_ID)
    created, changed = body["entries"]
    assert (created["event"], created["actor"], created["before"]) == (
        "product.created",
        "Antonio",
        None,
    )
    assert created["after"]["price"] == "129.99"
    assert changed == {
        "event": "product.changed",
        "occurred_at": "2026-11-21T11:00:00Z",
        "actor": "Maria",
        "sku": "GK-088",
        "before": {"price": "129.99"},
        "after": {"price": "119.99"},
        "context": {},
    }


async def test_the_history_of_an_unknown_product_is_404(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory,
) -> None:
    async with api(catalog) as client:
        response = await client.get(history_url(PRODUCT_ID))

    body = assert_problem(response, 404, "not-found")
    assert body["detail"] == "Product not found."


async def test_the_history_with_an_id_that_is_not_a_uuid_is_422(
    catalog: SqlAlchemyCatalogUnitOfWorkFactory,
) -> None:
    async with api(catalog) as client:
        response = await client.get(history_url("not-a-uuid"))

    body = assert_problem(response, 422, "validation-error")
    [error] = body["errors"]
    assert (error["location"], error["field"], error["code"]) == (
        "path",
        "product_id",
        "not_a_uuid",
    )
