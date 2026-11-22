from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

AuditValue = str | int | tuple[str, ...] | None


@dataclass(frozen=True)
class FieldChange:
    before: AuditValue
    after: AuditValue


@dataclass(frozen=True, kw_only=True)
class ProductEvent:
    product_id: UUID
    sku: str
    occurred_at: datetime


@dataclass(frozen=True, kw_only=True)
class ProductCreated(ProductEvent):
    snapshot: Mapping[str, AuditValue]


@dataclass(frozen=True, kw_only=True)
class ProductChanged(ProductEvent):
    changes: Mapping[str, FieldChange]


@dataclass(frozen=True, kw_only=True)
class ProductArchived(ProductEvent):
    pass


@dataclass(frozen=True, kw_only=True)
class ProductRestored(ProductEvent):
    pass


@dataclass(frozen=True, kw_only=True)
class StockDecreased(ProductEvent):
    quantity: int
    stock_before: int
    stock_after: int
    order_reference: str
