from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from ecommerce.shared_kernel.domain.errors import DomainError, NotFoundError


class OrderNotFound(NotFoundError):
    def __init__(self, order_id: UUID) -> None:
        self.order_id = order_id
        super().__init__(f"Order {order_id} was not found.")


class OrderAlreadySettled(DomainError):
    def __init__(self, order_id: UUID, status: str) -> None:
        self.order_id = order_id
        self.status = status
        super().__init__(f"Order {order_id} is already {status}.")


@dataclass(frozen=True)
class UnsellableItem:
    sku: str
    reason: str


@dataclass(frozen=True)
class ShortItem:
    sku: str
    requested: int
    available: int


class ProductsNotSellable(DomainError):
    def __init__(self, items: Iterable[UnsellableItem]) -> None:
        self.items = tuple(sorted(items, key=lambda item: item.sku))
        super().__init__(", ".join(f"{item.sku}: {item.reason}" for item in self.items))


class NotEnoughStock(DomainError):
    def __init__(self, items: Iterable[ShortItem]) -> None:
        self.items = tuple(sorted(items, key=lambda item: item.sku))
        super().__init__(
            ", ".join(
                f"{item.sku}: requested {item.requested}, available {item.available}"
                for item in self.items
            )
        )
