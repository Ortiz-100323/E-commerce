from typing import Protocol

from ecommerce.ordering.application.idempotency import IdempotencyStore
from ecommerce.ordering.application.ports import CatalogGateway
from ecommerce.ordering.domain.repository import OrderRepository
from ecommerce.shared_kernel.application.unit_of_work import UnitOfWork


class OrderingUnitOfWork(UnitOfWork, Protocol):
    @property
    def orders(self) -> OrderRepository: ...

    @property
    def catalog(self) -> CatalogGateway: ...

    @property
    def idempotency(self) -> IdempotencyStore: ...


class OrderingUnitOfWorkFactory(Protocol):
    def __call__(self) -> OrderingUnitOfWork: ...
