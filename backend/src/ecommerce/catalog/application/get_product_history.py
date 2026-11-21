from uuid import UUID

from ecommerce.catalog.application.audit import PRODUCT_ENTITY
from ecommerce.catalog.application.unit_of_work import CatalogUnitOfWorkFactory
from ecommerce.catalog.domain.errors import ProductNotFound
from ecommerce.catalog.domain.product import ProductId
from ecommerce.shared_kernel.application.audit import AuditEntry


class GetProductHistory:
    def __init__(self, unit_of_work: CatalogUnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, product_id: UUID) -> list[AuditEntry]:
        async with self._unit_of_work() as work:
            if await work.products.get(ProductId(product_id)) is None:
                raise ProductNotFound(product_id)
            return await work.audit_log.entries_for(PRODUCT_ENTITY, str(product_id))
