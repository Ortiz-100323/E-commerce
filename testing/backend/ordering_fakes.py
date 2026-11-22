from collections.abc import Collection
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal
from types import TracebackType
from typing import Self
from uuid import UUID

from ecommerce.ordering.application.idempotency import KeyRecord
from ecommerce.ordering.application.ports import PaymentResult, SaleProduct
from ecommerce.ordering.domain.order import Order, OrderId
from ecommerce.ordering.domain.payment import PaymentCard
from ecommerce.shared_kernel.domain.money import Money

DECLINED_CARD = "4000000000000002"


def sale_product(
    sku: str,
    price: str = "89.99",
    stock: int = 10,
    *,
    product_id: UUID | None = None,
    active: bool = True,
) -> SaleProduct:
    return SaleProduct(
        product_id=product_id or UUID(int=abs(hash(sku)) % (2**64)),
        sku=sku,
        name=f"Product {sku}",
        price=Decimal(price),
        stock=stock,
        gift=Decimal(price) == 0,
        active=active,
    )


@dataclass
class Charge:
    amount: Money
    last4: str
    reference: str


@dataclass
class RecordingPaymentGateway:
    charges: list[Charge] = field(default_factory=list)
    fail_if_called: bool = False

    async def charge(self, amount: Money, card: PaymentCard, reference: str) -> PaymentResult:
        if self.fail_if_called:
            raise AssertionError("The payment gateway must not be called.")
        self.charges.append(Charge(amount, card.last4, reference))
        if card.number == DECLINED_CARD:
            return PaymentResult(approved=False, reference="", decline_reason="card_declined")
        return PaymentResult(approved=True, reference=f"fake_{len(self.charges)}")


class InMemoryOrderingState:
    def __init__(self, *products: SaleProduct) -> None:
        self.products = {product.sku: product for product in products}
        self.orders: dict[OrderId, Order] = {}
        self.keys: dict[UUID, tuple[KeyRecord, datetime]] = {}
        self.locked: list[list[str]] = []
        self.decreases: list[tuple[str, int, str]] = []
        self.commits = 0
        self.failures: list[Exception] = []

    def __call__(self) -> "InMemoryOrderingUnitOfWork":
        return InMemoryOrderingUnitOfWork(self)


class InMemoryOrders:
    def __init__(self, work: "InMemoryOrderingUnitOfWork") -> None:
        self._work = work

    async def add(self, order: Order) -> None:
        self._work.staged_orders[order.id] = order

    async def get(self, order_id: OrderId) -> Order | None:
        return self._work.staged_orders.get(order_id) or self._work.state.orders.get(order_id)

    async def for_buyer(
        self, buyer_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[Order], int]:
        mine = sorted(
            (order for order in self._work.state.orders.values() if order.buyer_id == buyer_id),
            key=lambda order: (order.created_at, str(order.id)),
            reverse=True,
        )
        return mine[offset : offset + limit], len(mine)


class InMemoryCatalogGateway:
    def __init__(self, work: "InMemoryOrderingUnitOfWork") -> None:
        self._work = work

    async def products_for_sale(self, skus: Collection[str]) -> dict[str, SaleProduct]:
        products = self._work.state.products
        return {sku: products[sku] for sku in sorted(skus) if sku in products}

    async def lock_for_sale(self, skus: Collection[str]) -> dict[str, SaleProduct]:
        state = self._work.state
        if state.failures:
            raise state.failures.pop(0)
        ordered = sorted(skus)
        state.locked.append(ordered)
        return {sku: state.products[sku] for sku in ordered if sku in state.products}

    async def decrease_stock(
        self, sku: str, quantity: int, *, order_reference: str, at: datetime
    ) -> None:
        self._work.staged_decreases.append((sku, quantity, order_reference))


class InMemoryIdempotency:
    def __init__(self, work: "InMemoryOrderingUnitOfWork") -> None:
        self._work = work

    async def claim(
        self, key: UUID, fingerprint: str, *, now: datetime, expires_at: datetime
    ) -> KeyRecord | None:
        found = self._work.state.keys.get(key)
        if found is not None and found[1] > now:
            return found[0]
        self._work.staged_claim = (key, fingerprint, expires_at)
        return None

    async def record(self, key: UUID, *, order_id: UUID, response_status: int) -> None:
        claim = self._work.staged_claim
        assert claim is not None and claim[0] == key
        self._work.staged_record = (
            key,
            KeyRecord(fingerprint=claim[1], order_id=order_id, response_status=response_status),
            claim[2],
        )


class InMemoryOrderingUnitOfWork:
    def __init__(self, state: InMemoryOrderingState) -> None:
        self.state = state
        self.staged_orders: dict[OrderId, Order] = {}
        self.staged_decreases: list[tuple[str, int, str]] = []
        self.staged_claim: tuple[UUID, str, datetime] | None = None
        self.staged_record: tuple[UUID, KeyRecord, datetime] | None = None
        self.orders = InMemoryOrders(self)
        self.catalog = InMemoryCatalogGateway(self)
        self.idempotency = InMemoryIdempotency(self)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.rollback()

    async def commit(self) -> None:
        state = self.state
        state.orders.update(self.staged_orders)
        for sku, quantity, reference in self.staged_decreases:
            product = state.products[sku]
            state.products[sku] = replace(product, stock=product.stock - quantity)
            state.decreases.append((sku, quantity, reference))
        if self.staged_record is not None:
            key, record, expires_at = self.staged_record
            state.keys[key] = (record, expires_at)
        state.commits += 1
        await self.rollback()

    async def rollback(self) -> None:
        self.staged_orders = {}
        self.staged_decreases = []
        self.staged_claim = None
        self.staged_record = None


class MovableClock:
    def __init__(self, start: datetime) -> None:
        self.current = start

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


class FlakyErrors:
    def __init__(self, transient: type[Exception]) -> None:
        self._transient = transient

    def is_transient(self, error: Exception) -> bool:
        return isinstance(error, self._transient)


class NoTransientErrors:
    def is_transient(self, error: Exception) -> bool:
        return False
