from typing import Protocol
from uuid import UUID

from ecommerce.catalog.domain.importing.repository import ImportBatchRepository
from ecommerce.catalog.domain.repository import ProductRepository
from ecommerce.shared_kernel.application.audit import AuditLog, JsonObject
from ecommerce.shared_kernel.application.unit_of_work import UnitOfWork
from ecommerce.shared_kernel.domain.actor import Actor


class CatalogUnitOfWork(UnitOfWork, Protocol):
    @property
    def products(self) -> ProductRepository: ...

    @property
    def imports(self) -> ImportBatchRepository: ...

    @property
    def audit_log(self) -> AuditLog: ...

    def annotate(self, product_id: UUID, context: JsonObject) -> None: ...


class CatalogUnitOfWorkFactory(Protocol):
    def __call__(self, actor: Actor | None = None) -> CatalogUnitOfWork: ...
