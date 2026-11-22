from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import httpx
from identity_fakes import (
    ANTONIO_TOKEN,
    BEA_TOKEN,
    MARIA_TOKEN,
    TEST_PASSWORD,
    seeded_accounts,
    seeded_sessions,
)
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.catalog.domain.importing.policies import ImportPolicies
from ecommerce.catalog.infrastructure.product_queries import SqlAlchemyProductQueries
from ecommerce.catalog.infrastructure.unit_of_work import SqlAlchemyCatalogUnitOfWorkFactory
from ecommerce.identity.infrastructure.security import ScryptPasswordHasher
from ecommerce.identity.infrastructure.tables import account_sessions, accounts
from ecommerce.identity.infrastructure.unit_of_work import SqlAlchemyIdentityUnitOfWorkFactory
from ecommerce.integration.catalog_sales import CatalogSales
from ecommerce.main import API_PREFIX, create_app
from ecommerce.ordering.application.ports import PaymentGateway
from ecommerce.ordering.infrastructure.payment_gateway import FakePaymentGateway
from ecommerce.ordering.infrastructure.transient import DatabaseTransientErrors
from ecommerce.ordering.infrastructure.unit_of_work import SqlAlchemyOrderingUnitOfWorkFactory
from ecommerce.shared_kernel.api.access import SESSION_COOKIE
from ecommerce.shared_kernel.application.ports import Clock, SystemClock
from ecommerce.shared_kernel.infrastructure.database import create_session_factory
from fakes import dependencies_factory

PRODUCTS = f"{API_PREFIX}/products"
ORDERS = f"{API_PREFIX}/orders"
QUOTE = f"{API_PREFIX}/orders/quote"
CATEGORIES = f"{API_PREFIX}/categories"
IMPORT_PREVIEW = f"{API_PREFIX}/imports/preview"
IMPORTS = f"{API_PREFIX}/imports"
SESSION = f"{API_PREFIX}/session"
ADMIN_ACCOUNTS = f"{API_PREFIX}/admin/accounts"
ACCOUNTS = f"{API_PREFIX}/accounts"
MY_ORDERS = f"{API_PREFIX}/me/orders"


def cookie(token: str) -> dict[str, str]:
    return {"Cookie": f"{SESSION_COOKIE}={token}"}


ANTONIO = cookie(ANTONIO_TOKEN)
MARIA = cookie(MARIA_TOKEN)
BEA = cookie(BEA_TOKEN)
TEST_HASHER = ScryptPasswordHasher(n=2**10, r=8, p=1)
TEST_PASSWORD_HASH = TEST_HASHER.hash(TEST_PASSWORD)


async def seed_test_accounts(engine: AsyncEngine, at: datetime) -> None:
    async with engine.begin() as connection:
        await connection.execute(delete(account_sessions))
        await connection.execute(delete(accounts))
        await connection.execute(
            insert(accounts),
            [
                {
                    "id": account.id,
                    "email": account.email.value,
                    "name": account.name.value,
                    "role": account.role.value,
                    "password_hash": TEST_PASSWORD_HASH,
                    "active": True,
                    "created_at": account.created_at,
                }
                for account in seeded_accounts(TEST_PASSWORD_HASH)
            ],
        )
        await connection.execute(
            insert(account_sessions),
            [
                {
                    "id": session.session_id,
                    "account_id": session.account_id,
                    "token_hash": session.token_hash,
                    "created_at": session.created_at,
                    "last_seen_at": session.last_seen_at,
                    "expires_at": session.expires_at,
                }
                for session in seeded_sessions(at)
            ],
        )


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
    session_clock: Clock | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    sessions = create_session_factory(engine)
    sessions_clock = session_clock or SystemClock()
    await seed_test_accounts(engine, sessions_clock.now())
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
        identity=SqlAlchemyIdentityUnitOfWorkFactory(sessions),
        hasher=TEST_HASHER,
        session_clock=sessions_clock,
    )
    app = create_app(factory)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
