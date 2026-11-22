from collections.abc import Collection
from typing import Any

from psycopg import errors
from sqlalchemy import RowMapping, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ecommerce.catalog.domain.errors import (
    DuplicateSku,
    ProductAlreadyExists,
    ProductNotFound,
    VersionConflict,
)
from ecommerce.catalog.domain.events import ProductEvent
from ecommerce.catalog.domain.product import Product, ProductDetails, ProductId, ProductStatus
from ecommerce.catalog.domain.value_objects import (
    Category,
    Description,
    Price,
    ProductName,
    ProductTag,
    Sku,
    StockQuantity,
    Weight,
)
from ecommerce.catalog.infrastructure.orm import products
from ecommerce.shared_kernel.domain.money import Money

PRIMARY_KEY = "products_pkey"
SKU_UNIQUE_INDEX = "uq_products_sku"


class SqlAlchemyProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._stored_events: list[ProductEvent] = []

    def take_stored_events(self) -> list[ProductEvent]:
        events, self._stored_events = self._stored_events, []
        return events

    def forget_stored_events(self) -> None:
        self._stored_events = []

    async def add(self, product: Product) -> None:
        row = {
            "id": product.id,
            "sku": product.sku.value,
            "version": product.version,
            "created_at": product.created_at,
            **changeable_columns(product),
        }
        try:
            async with self._session.begin_nested():
                await self._session.execute(insert(products).values(row))
        except IntegrityError as error:
            if is_violation_of(error, PRIMARY_KEY):
                raise ProductAlreadyExists(product.id) from error
            if is_violation_of(error, SKU_UNIQUE_INDEX):
                raise DuplicateSku(product.sku.value) from error
            raise
        self._stored_events.extend(product.pull_events())

    async def get(self, product_id: ProductId) -> Product | None:
        return await self._first(select(products).where(products.c.id == product_id))

    async def get_by_sku(self, sku: Sku) -> Product | None:
        return await self._first(select(products).where(products.c.sku == sku.value))

    async def save(self, product: Product) -> None:
        if not product.has_pending_events:
            return
        statement = (
            update(products)
            .where(products.c.id == product.id, products.c.version == product.version)
            .values(version=products.c.version + 1, **changeable_columns(product))
            .returning(products.c.version)
        )
        if (await self._session.execute(statement)).scalar_one_or_none() is None:
            current = await self._session.scalar(
                select(products.c.version).where(products.c.id == product.id)
            )
            if current is None:
                raise ProductNotFound(product.id)
            raise VersionConflict(
                product.id, expected_version=product.version, current_version=current
            )
        product.bump_version()
        self._stored_events.extend(product.pull_events())

    async def lock_by_skus(self, skus: Collection[str]) -> dict[str, Product]:
        if not skus:
            return {}
        statement = (
            select(products)
            .where(products.c.sku.in_(sorted(skus)))
            .order_by(products.c.sku)
            .with_for_update()
        )
        rows = (await self._session.execute(statement)).mappings().all()
        return {row["sku"]: to_product(row) for row in rows}

    async def _first(self, statement: Any) -> Product | None:
        row = (await self._session.execute(statement)).mappings().first()
        return None if row is None else to_product(row)


def changeable_columns(product: Product) -> dict[str, Any]:
    return {
        "name": product.name.value,
        "description": product.description.value,
        "category": product.category.value,
        "price": product.price.amount,
        "stock": product.stock.value,
        "weight_kg": product.weight.kg,
        "tags": sorted(tag.value for tag in product.tags),
        "status": product.status.value,
        "updated_at": product.updated_at,
    }


def to_product(row: RowMapping) -> Product:
    return Product(
        product_id=ProductId(row["id"]),
        sku=Sku(row["sku"]),
        details=ProductDetails(
            name=ProductName(row["name"]),
            description=Description(row["description"]),
            category=Category(row["category"]),
            price=Price(Money(row["price"])),
            stock=StockQuantity(row["stock"]),
            weight=Weight(row["weight_kg"]),
            tags=frozenset(ProductTag(tag) for tag in row["tags"]),
        ),
        status=ProductStatus(row["status"]),
        version=row["version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def is_violation_of(error: IntegrityError, constraint: str) -> bool:
    return (
        isinstance(error.orig, errors.UniqueViolation)
        and error.orig.diag.constraint_name == constraint
    )
