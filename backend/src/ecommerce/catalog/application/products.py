from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from ecommerce.catalog.application.unit_of_work import CatalogUnitOfWork, CatalogUnitOfWorkFactory
from ecommerce.catalog.domain.errors import ProductNotFound, VersionConflict
from ecommerce.catalog.domain.product import Product, ProductId, new_product_id
from ecommerce.catalog.domain.value_objects import ProductTag
from ecommerce.shared_kernel.application.ports import Clock
from ecommerce.shared_kernel.domain.actor import Actor

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


@dataclass(frozen=True, kw_only=True)
class ProductView:
    id: UUID
    sku: str
    name: str
    description: str
    category: str
    price: Decimal
    currency: str
    stock: int
    weight_kg: Decimal
    gift: bool
    tags: tuple[str, ...]
    status: str
    is_sellable: bool
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, product: Product) -> "ProductView":
        return cls(
            id=product.id,
            sku=product.sku.value,
            name=product.name.value,
            description=product.description.value,
            category=product.category.value,
            price=product.price.amount,
            currency=product.price.money.currency,
            stock=product.stock.value,
            weight_kg=product.weight.kg,
            gift=product.is_gift,
            tags=tuple(sorted(tag.value for tag in product.tags)),
            status=product.status.value,
            is_sellable=product.is_sellable,
            version=product.version,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )


@dataclass(frozen=True, kw_only=True)
class ProductFields:
    name: str
    description: str
    category: str
    price: Decimal
    stock: int
    weight_kg: Decimal
    gift: bool


@dataclass(frozen=True, kw_only=True)
class NewProduct(ProductFields):
    sku: str


class StatusFilter(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    ALL = "ALL"


class ProductSort(StrEnum):
    NAME = "name"
    NAME_DESC = "-name"
    PRICE = "price"
    PRICE_DESC = "-price"
    CREATED_AT = "created_at"
    CREATED_AT_DESC = "-created_at"


@dataclass(frozen=True, kw_only=True)
class ProductQuery:
    q: str | None = None
    category: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    in_stock: bool | None = None
    tag: ProductTag | None = None
    status: StatusFilter = StatusFilter.ACTIVE
    sort: ProductSort = ProductSort.NAME
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, kw_only=True)
class ProductPage:
    items: Sequence[ProductView]
    total: int
    page: int
    page_size: int


class ProductQueries(Protocol):
    async def search(self, query: ProductQuery) -> tuple[list[ProductView], int]: ...

    async def categories(self) -> list[str]: ...


async def existing(work: CatalogUnitOfWork, product_id: UUID) -> Product:
    product = await work.products.get(ProductId(product_id))
    if product is None:
        raise ProductNotFound(product_id)
    return product


class CreateProduct:
    def __init__(self, catalog: CatalogUnitOfWorkFactory, clock: Clock) -> None:
        self._catalog = catalog
        self._clock = clock

    async def execute(self, new: NewProduct, actor: Actor) -> ProductView:
        product = Product.create(
            product_id=new_product_id(),
            sku=new.sku,
            name=new.name,
            description=new.description,
            category=new.category,
            price=new.price,
            stock=new.stock,
            weight_kg=new.weight_kg,
            gift=new.gift,
            at=self._clock.now(),
        )
        async with self._catalog(actor) as work:
            await work.products.add(product)
            await work.commit()
        return ProductView.of(product)


class UpdateProduct:
    def __init__(self, catalog: CatalogUnitOfWorkFactory, clock: Clock) -> None:
        self._catalog = catalog
        self._clock = clock

    async def execute(
        self, product_id: UUID, version: int, fields: ProductFields, actor: Actor
    ) -> ProductView:
        async with self._catalog(actor) as work:
            product = await existing(work, product_id)
            product.revise(
                name=fields.name,
                description=fields.description,
                category=fields.category,
                price=fields.price,
                stock=fields.stock,
                weight_kg=fields.weight_kg,
                gift=fields.gift,
                at=self._clock.now(),
            )
            if product.version != version:
                if product.has_pending_events:
                    raise VersionConflict(
                        product.id, expected_version=version, current_version=product.version
                    )
                return ProductView.of(product)
            await work.products.save(product)
            await work.commit()
        return ProductView.of(product)


class ArchiveProduct:
    def __init__(self, catalog: CatalogUnitOfWorkFactory, clock: Clock) -> None:
        self._catalog = catalog
        self._clock = clock

    async def execute(self, product_id: UUID, actor: Actor) -> ProductView:
        async with self._catalog(actor) as work:
            product = await existing(work, product_id)
            product.archive(at=self._clock.now())
            await work.products.save(product)
            await work.commit()
        return ProductView.of(product)


class RestoreProduct:
    def __init__(self, catalog: CatalogUnitOfWorkFactory, clock: Clock) -> None:
        self._catalog = catalog
        self._clock = clock

    async def execute(self, product_id: UUID, actor: Actor) -> ProductView:
        async with self._catalog(actor) as work:
            product = await existing(work, product_id)
            product.restore(at=self._clock.now())
            await work.products.save(product)
            await work.commit()
        return ProductView.of(product)


class GetProduct:
    def __init__(self, catalog: CatalogUnitOfWorkFactory) -> None:
        self._catalog = catalog

    async def execute(self, product_id: UUID) -> ProductView:
        async with self._catalog() as work:
            return ProductView.of(await existing(work, product_id))


class SearchProducts:
    def __init__(self, queries: ProductQueries) -> None:
        self._queries = queries

    async def execute(self, query: ProductQuery) -> ProductPage:
        items, total = await self._queries.search(query)
        return ProductPage(items=items, total=total, page=query.page, page_size=query.page_size)


class ListCategories:
    def __init__(self, queries: ProductQueries) -> None:
        self._queries = queries

    async def execute(self) -> list[str]:
        return await self._queries.categories()
