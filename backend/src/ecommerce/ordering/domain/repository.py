from typing import Protocol
from uuid import UUID

from ecommerce.ordering.domain.order import Order, OrderId


class OrderRepository(Protocol):
    async def add(self, order: Order) -> None: ...

    async def get(self, order_id: OrderId) -> Order | None: ...

    async def for_buyer(
        self, buyer_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[Order], int]: ...
