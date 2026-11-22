from collections.abc import Collection
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ecommerce.catalog.application.audit import audit_entries
from ecommerce.catalog.domain.product import Product, ProductStatus
from ecommerce.catalog.domain.value_objects import Sku
from ecommerce.catalog.infrastructure.product_repository import SqlAlchemyProductRepository
from ecommerce.ordering.application.ports import SaleProduct
from ecommerce.shared_kernel.application.audit import AuditEntry, JsonObject
from ecommerce.shared_kernel.domain.actor import Actor
from ecommerce.shared_kernel.domain.errors import DomainValidationError

CHECKOUT_SOURCE = "checkout"


def sale_product(product: Product) -> SaleProduct:
    return SaleProduct(
        product_id=product.id,
        sku=product.sku.value,
        name=product.name.value,
        price=product.price.amount,
        stock=product.stock.value,
        gift=product.is_gift,
        active=product.status is ProductStatus.ACTIVE,
    )


class CatalogSales:
    def __init__(self, session: AsyncSession) -> None:
        self._products = SqlAlchemyProductRepository(session)
        self._locked: dict[str, Product] = {}
        self._contexts: dict[UUID, JsonObject] = {}

    async def products_for_sale(self, skus: Collection[str]) -> dict[str, SaleProduct]:
        found = {}
        for raw in sorted(skus):
            try:
                sku = Sku(raw)
            except DomainValidationError:
                continue
            product = await self._products.get_by_sku(sku)
            if product is not None:
                found[product.sku.value] = sale_product(product)
        return found

    async def lock_for_sale(self, skus: Collection[str]) -> dict[str, SaleProduct]:
        locked = await self._products.lock_by_skus(skus)
        self._locked.update(locked)
        return {sku: sale_product(product) for sku, product in locked.items()}

    async def decrease_stock(
        self, sku: str, quantity: int, *, order_reference: str, at: datetime
    ) -> None:
        product = self._locked[sku]
        product.decrease_stock(quantity, order_reference=order_reference, at=at)
        await self._products.save(product)
        self._contexts[product.id] = {"source": CHECKOUT_SOURCE}

    def take_audit_entries(self, actor: Actor) -> list[AuditEntry]:
        entries = audit_entries(self._products.take_stored_events(), actor, self._contexts)
        self._contexts = {}
        return entries

    def forget(self) -> None:
        self._products.forget_stored_events()
        self._contexts = {}
