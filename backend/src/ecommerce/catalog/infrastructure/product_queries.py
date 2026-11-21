from collections.abc import Collection
from typing import Any

from sqlalchemy import ColumnElement, any_, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.catalog.application.products import (
    ProductQuery,
    ProductSort,
    ProductView,
    StatusFilter,
)
from ecommerce.catalog.domain.importing.classification import ExistingProduct
from ecommerce.catalog.domain.product import ProductStatus
from ecommerce.catalog.domain.value_objects import ProductTag
from ecommerce.catalog.infrastructure.orm import products
from ecommerce.catalog.infrastructure.product_repository import to_product

LIKE_ESCAPE = "\\"

SORTS: dict[ProductSort, tuple[Any, ...]] = {
    ProductSort.NAME: (func.lower(products.c.name).asc(),),
    ProductSort.NAME_DESC: (func.lower(products.c.name).desc(),),
    ProductSort.PRICE: (products.c.price.asc(),),
    ProductSort.PRICE_DESC: (products.c.price.desc(),),
    ProductSort.CREATED_AT: (products.c.created_at.asc(),),
    ProductSort.CREATED_AT_DESC: (products.c.created_at.desc(),),
}


def escape_like(text: str) -> str:
    return (
        text.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", f"{LIKE_ESCAPE}%")
        .replace("_", f"{LIKE_ESCAPE}_")
    )


def conditions(query: ProductQuery) -> list[ColumnElement[bool]]:
    found: list[ColumnElement[bool]] = []
    text = (query.q or "").strip()
    if text:
        pattern = f"%{escape_like(text)}%"
        found.append(
            or_(
                products.c.name.ilike(pattern, escape=LIKE_ESCAPE),
                products.c.sku.ilike(pattern, escape=LIKE_ESCAPE),
                products.c.description.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    category = (query.category or "").strip()
    if category:
        found.append(func.lower(products.c.category) == category.lower())
    if query.min_price is not None:
        found.append(products.c.price >= query.min_price)
    if query.max_price is not None:
        found.append(products.c.price <= query.max_price)
    if query.in_stock is True:
        found.append(products.c.stock > 0)
    if query.in_stock is False:
        found.append(products.c.stock == 0)
    if query.tag is not None:
        found.append(literal(query.tag.value) == any_(products.c.tags))
    if query.status is not StatusFilter.ALL:
        found.append(products.c.status == query.status.value)
    return found


class SqlAlchemyProductQueries:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def search(self, query: ProductQuery) -> tuple[list[ProductView], int]:
        where = conditions(query)
        page = (
            select(products)
            .where(*where)
            .order_by(*SORTS[query.sort], products.c.id)
            .offset(query.offset)
            .limit(query.page_size)
        )
        count = select(func.count()).select_from(products).where(*where)
        async with self._engine.connect() as connection:
            rows = (await connection.execute(page)).mappings().all()
            total = (await connection.execute(count)).scalar_one()
        return [ProductView.of(to_product(row)) for row in rows], total

    async def categories(self) -> list[str]:
        key = func.lower(products.c.category)
        statement = (
            select(func.min(products.c.category))
            .where(products.c.status == ProductStatus.ACTIVE.value)
            .group_by(key)
            .order_by(key)
        )
        async with self._engine.connect() as connection:
            return list((await connection.execute(statement)).scalars().all())

    async def existing_by_skus(self, skus: Collection[str]) -> dict[str, ExistingProduct]:
        statement = select(products).where(products.c.sku.in_(sorted(skus)))
        async with self._engine.connect() as connection:
            rows = (await connection.execute(statement)).mappings().all()
        return {
            row["sku"]: ExistingProduct(
                product_id=row["id"],
                version=row["version"],
                sku=row["sku"],
                name=row["name"],
                description=row["description"],
                category=row["category"],
                price=row["price"],
                stock=row["stock"],
                weight_kg=row["weight_kg"],
                gift=ProductTag.GIFT.value in row["tags"],
                archived=row["status"] == ProductStatus.ARCHIVED.value,
            )
            for row in rows
        }
