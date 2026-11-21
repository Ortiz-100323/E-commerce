from typing import Protocol

from ecommerce.catalog.domain.repository import ProductRepository
from ecommerce.shared_kernel.application.audit import AuditLog
from ecommerce.shared_kernel.application.unit_of_work import UnitOfWork
from ecommerce.shared_kernel.domain.actor import Actor


class CatalogUnitOfWork(UnitOfWork, Protocol):
    @property
    def products(self) -> ProductRepository: ...

    @property
    def audit_log(self) -> AuditLog: ...


class CatalogUnitOfWorkFactory(Protocol):
    def __call__(self, actor: Actor | None = None) -> CatalogUnitOfWork: ...
