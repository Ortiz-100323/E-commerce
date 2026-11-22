from datetime import datetime
from typing import Protocol

from ecommerce.catalog.domain.importing.batch import ImportBatch, ImportBatchId


class ImportBatchRepository(Protocol):
    async def add(self, batch: ImportBatch) -> None: ...

    async def get(
        self, batch_id: ImportBatchId, *, for_update: bool = False
    ) -> ImportBatch | None: ...

    async def save(self, batch: ImportBatch) -> None: ...

    async def pending_with_sha256(self, sha256: str, now: datetime) -> list[ImportBatchId]: ...
