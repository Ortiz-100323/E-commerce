from typing import Protocol

from ecommerce.ordering.domain.order import Order, OrderId


class OrderRepository(Protocol):
    async def add(self, order: Order) -> None: ...

    async def get(self, order_id: OrderId) -> Order | None: ...
