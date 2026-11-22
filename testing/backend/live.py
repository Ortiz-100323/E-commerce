from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.catalog.domain.importing.policies import ImportPolicies
from ecommerce.catalog.infrastructure.product_queries import SqlAlchemyProductQueries
from ecommerce.catalog.infrastructure.unit_of_work import SqlAlchemyCatalogUnitOfWorkFactory
from ecommerce.integration.catalog_sales import CatalogSales
from ecommerce.main import API_PREFIX, create_app
from ecommerce.ordering.application.ports import PaymentGateway
from ecommerce.ordering.infrastructure.payment_gateway import FakePaymentGateway
from ecommerce.ordering.infrastructure.transient import DatabaseTransientErrors
from ecommerce.ordering.infrastructure.unit_of_work import SqlAlchemyOrderingUnitOfWorkFactory
from ecommerce.shared_kernel.api.actor import ACTOR_HEADER
from ecommerce.shared_kernel.application.ports import Clock
from ecommerce.shared_kernel.infrastructure.database import create_session_factory
from fakes import dependencies_factory

PRODUCTS = f"{API_PREFIX}/products"
ORDERS = f"{API_PREFIX}/orders"
CATEGORIES = f"{API_PREFIX}/categories"
IMPORT_PREVIEW = f"{API_PREFIX}/imports/preview"
IMPORTS = f"{API_PREFIX}/imports"
ANTONIO = {ACTOR_HEADER: "Antonio"}
MARIA = {ACTOR_HEADER: "Maria"}


def product_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "sku": "RS-001",
        "name": "Running Shoes",
        "description": "Lightweight shoes.",
        "category": "Sports",
        "price": "89.99",
        "stock": 10,
        "weight_kg": "0.8",
        "gift": False,
    }
    body.update(overrides)
    return {key: value for key, value in body.items() if value is not None}


def update_body(version: int, **overrides: Any) -> dict[str, Any]:
    body = product_body(**overrides)
    body.pop("sku", None)
    return {**body, "version": version}


@asynccontextmanager
async def live_api(
    engine: AsyncEngine,
    clock: Clock | None = None,
    policies: ImportPolicies | None = None,
    payments: PaymentGateway | None = None,
    lock_timeout_ms: int = 5000,
) -> AsyncIterator[httpx.AsyncClient]:
    sessions = create_session_factory(engine)
    factory = dependencies_factory(
        catalog=SqlAlchemyCatalogUnitOfWorkFactory(sessions),
        queries=SqlAlchemyProductQueries(engine),
        clock=clock,
        existing=SqlAlchemyProductQueries(engine),
        policies=policies,
        ordering=SqlAlchemyOrderingUnitOfWorkFactory(
            sessions, CatalogSales, lock_timeout_ms=lock_timeout_ms
        ),
        payments=payments or FakePaymentGateway(),
        transient=DatabaseTransientErrors(),
    )
    app = create_app(factory)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
