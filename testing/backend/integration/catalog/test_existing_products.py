from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.catalog.domain.importing.classification import ExistingProduct
from ecommerce.catalog.domain.product import Product, ProductId
from ecommerce.catalog.infrastructure.product_queries import SqlAlchemyProductQueries
from ecommerce.catalog.infrastructure.unit_of_work import SqlAlchemyCatalogUnitOfWork
from ecommerce.shared_kernel.domain.actor import Actor
from ecommerce.shared_kernel.infrastructure.database import create_session_factory

AT = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)


def product(number: int, **overrides: Any) -> Product:
    values: dict[str, Any] = {
        "product_id": ProductId(UUID(f"00000000-0000-4000-8000-{number:012d}")),
        "sku": f"RS-{number:03d}",
        "name": "Running Shoes",
        "description": "Light",
        "category": "Footwear",
        "price": "89.99",
        "stock": 10,
        "weight_kg": "0.35",
        "gift": False,
        "at": AT,
    }
    values.update(overrides)
    return Product.create(**values)


async def test_existing_products_are_found_by_sku_with_gift_and_archive_flags(
    engine: AsyncEngine,
) -> None:
    archived = product(2, sku="GC-001", name="Gift Card", price="0", gift=True)
    archived.archive(at=AT)
    async with SqlAlchemyCatalogUnitOfWork(create_session_factory(engine), Actor("Tester")) as work:
        await work.products.add(product(1))
        await work.products.add(archived)
        await work.commit()

    found = await SqlAlchemyProductQueries(engine).existing_by_skus({"RS-001", "GC-001", "NOPE-1"})

    assert found == {
        "RS-001": ExistingProduct(
            product_id=UUID("00000000-0000-4000-8000-000000000001"),
            version=1,
            sku="RS-001",
            name="Running Shoes",
            description="Light",
            category="Footwear",
            price=Decimal("89.99"),
            stock=10,
            weight_kg=Decimal("0.350"),
            gift=False,
            archived=False,
        ),
        "GC-001": ExistingProduct(
            product_id=UUID("00000000-0000-4000-8000-000000000002"),
            version=1,
            sku="GC-001",
            name="Gift Card",
            description="Light",
            category="Footwear",
            price=Decimal("0.00"),
            stock=10,
            weight_kg=Decimal("0.350"),
            gift=True,
            archived=True,
        ),
    }


async def test_no_skus_find_nothing(engine: AsyncEngine) -> None:
    assert await SqlAlchemyProductQueries(engine).existing_by_skus(set()) == {}
