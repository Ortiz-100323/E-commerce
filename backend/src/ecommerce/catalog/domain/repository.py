from typing import Protocol

from ecommerce.catalog.domain.product import Product, ProductId
from ecommerce.catalog.domain.value_objects import Sku


class ProductRepository(Protocol):
    async def add(self, product: Product) -> None: ...

    async def get(self, product_id: ProductId) -> Product | None: ...

    async def get_by_sku(self, sku: Sku) -> Product | None: ...

    async def save(self, product: Product) -> None: ...
