from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from ecommerce.ordering.domain.payment import PaymentCard
from ecommerce.shared_kernel.domain.money import Money


@dataclass(frozen=True, kw_only=True)
class SaleProduct:
    product_id: UUID
    sku: str
    name: str
    price: Decimal
    stock: int
    gift: bool
    active: bool


class CatalogGateway(Protocol):
    async def products_for_sale(self, skus: Collection[str]) -> dict[str, SaleProduct]: ...

    async def lock_for_sale(self, skus: Collection[str]) -> dict[str, SaleProduct]: ...

    async def decrease_stock(
        self, sku: str, quantity: int, *, order_reference: str, at: datetime
    ) -> None: ...


@dataclass(frozen=True, kw_only=True)
class PaymentResult:
    approved: bool
    reference: str
    decline_reason: str | None = None


class PaymentGateway(Protocol):
    async def charge(self, amount: Money, card: PaymentCard, reference: str) -> PaymentResult: ...


class TransientErrors(Protocol):
    def is_transient(self, error: Exception) -> bool: ...
