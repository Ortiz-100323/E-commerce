from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

type LineSnapshot = tuple[str, int, str]


@dataclass(frozen=True, kw_only=True)
class OrderEvent:
    order_id: UUID
    occurred_at: datetime
    total: str
    card_last4: str | None


@dataclass(frozen=True, kw_only=True)
class OrderPaid(OrderEvent):
    lines: tuple[LineSnapshot, ...]
    payment_reference: str | None


@dataclass(frozen=True, kw_only=True)
class OrderPaymentFailed(OrderEvent):
    reason: str
