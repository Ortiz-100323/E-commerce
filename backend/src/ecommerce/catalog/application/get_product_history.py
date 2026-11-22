from uuid import UUID

from ecommerce.catalog.application.audit import IMPORT_ROW_ENTITY, PRODUCT_ENTITY, import_row_id
from ecommerce.catalog.application.unit_of_work import CatalogUnitOfWorkFactory
from ecommerce.catalog.domain.errors import ProductNotFound
from ecommerce.catalog.domain.product import ProductId
from ecommerce.shared_kernel.application.audit import AuditEntry


def import_rows_of(entries: list[AuditEntry]) -> list[str]:
    found: list[str] = []
    for entry in entries:
        batch_id, line = entry.context.get("batch_id"), entry.context.get("line")
        if isinstance(batch_id, str) and isinstance(line, int):
            row_id = import_row_id(UUID(batch_id), line)
            if row_id not in found:
                found.append(row_id)
    return found


class GetProductHistory:
    def __init__(self, unit_of_work: CatalogUnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, product_id: UUID) -> list[AuditEntry]:
        async with self._unit_of_work() as work:
            if await work.products.get(ProductId(product_id)) is None:
                raise ProductNotFound(product_id)
            entries = await work.audit_log.entries_for(PRODUCT_ENTITY, str(product_id))
            resolutions = [
                entry
                for row_id in import_rows_of(entries)
                for entry in await work.audit_log.entries_for(IMPORT_ROW_ENTITY, row_id)
            ]
        return sorted([*resolutions, *entries], key=lambda entry: entry.occurred_at)
