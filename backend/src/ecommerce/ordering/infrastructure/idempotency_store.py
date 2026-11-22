from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ecommerce.ordering.application.idempotency import KeyRecord
from ecommerce.ordering.infrastructure.tables import idempotency_keys

CHECKOUT_ENDPOINT = "POST /orders"


class SqlAlchemyIdempotencyStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim(
        self, key: UUID, fingerprint: str, *, now: datetime, expires_at: datetime
    ) -> KeyRecord | None:
        claimed = await self._session.scalar(
            insert(idempotency_keys)
            .values(
                key=key,
                endpoint=CHECKOUT_ENDPOINT,
                request_fingerprint=fingerprint,
                created_at=now,
                expires_at=expires_at,
            )
            .on_conflict_do_nothing(index_elements=[idempotency_keys.c.key])
            .returning(idempotency_keys.c.key)
        )
        if claimed is not None:
            return None
        renewed = await self._session.scalar(
            update(idempotency_keys)
            .where(idempotency_keys.c.key == key, idempotency_keys.c.expires_at <= now)
            .values(
                request_fingerprint=fingerprint,
                order_id=None,
                response_status=None,
                created_at=now,
                expires_at=expires_at,
            )
            .returning(idempotency_keys.c.key)
        )
        if renewed is not None:
            return None
        row = (
            (
                await self._session.execute(
                    select(idempotency_keys).where(idempotency_keys.c.key == key)
                )
            )
            .mappings()
            .one()
        )
        return KeyRecord(
            fingerprint=row["request_fingerprint"],
            order_id=row["order_id"],
            response_status=row["response_status"],
        )

    async def record(self, key: UUID, *, order_id: UUID, response_status: int) -> None:
        await self._session.execute(
            update(idempotency_keys)
            .where(idempotency_keys.c.key == key)
            .values(order_id=order_id, response_status=response_status)
        )
