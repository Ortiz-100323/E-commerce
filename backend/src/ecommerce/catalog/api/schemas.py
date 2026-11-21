from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event: str
    occurred_at: datetime
    actor: str
    sku: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    context: dict[str, Any]


class ProductHistoryResponse(BaseModel):
    product_id: UUID
    entries: list[AuditEntryResponse]
