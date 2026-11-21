from typing import Protocol

from ecommerce.catalog.domain.repository import ProductRepository
from ecommerce.shared_kernel.application.unit_of_work import UnitOfWork


class CatalogUnitOfWork(UnitOfWork, Protocol):
    @property
    def products(self) -> ProductRepository: ...
