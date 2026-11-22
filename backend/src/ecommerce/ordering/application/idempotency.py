from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class KeyRecord:
    fingerprint: str
    order_id: UUID
    response_status: int


class IdempotencyStore(Protocol):
    async def claim(
        self, key: UUID, fingerprint: str, *, now: datetime, expires_at: datetime
    ) -> KeyRecord | None: ...

    async def record(self, key: UUID, *, order_id: UUID, response_status: int) -> None: ...
