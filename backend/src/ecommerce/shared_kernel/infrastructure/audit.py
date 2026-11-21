from collections.abc import Sequence
from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Identity,
    Index,
    RowMapping,
    String,
    Table,
    insert,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from ecommerce.shared_kernel.application.audit import AuditEntry
from ecommerce.shared_kernel.domain.actor import MAX_ACTOR_LENGTH
from ecommerce.shared_kernel.infrastructure.database import metadata

audit_log = Table(
    "audit_log",
    metadata,
    Column("id", BigInteger, Identity(always=True), primary_key=True),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("actor", String(MAX_ACTOR_LENGTH), nullable=False),
    Column("event", String(64), nullable=False),
    Column("entity", String(32), nullable=False),
    Column("entity_id", String(128), nullable=False),
    Column("sku", String(64), nullable=True),
    Column("before", JSONB(none_as_null=True), nullable=True),
    Column("after", JSONB(none_as_null=True), nullable=True),
    Column("context", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Index("ix_audit_log_entity", "entity", "entity_id", "id"),
)


async def append_entries(session: AsyncSession, entries: Sequence[AuditEntry]) -> None:
    if entries:
        await session.execute(insert(audit_log), [to_row(entry) for entry in entries])


class SqlAlchemyAuditLog:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def entries_for(self, entity: str, entity_id: str) -> list[AuditEntry]:
        statement = (
            select(audit_log)
            .where(audit_log.c.entity == entity, audit_log.c.entity_id == entity_id)
            .order_by(audit_log.c.id)
        )
        rows = (await self._session.execute(statement)).mappings().all()
        return [to_entry(row) for row in rows]


def to_row(entry: AuditEntry) -> dict[str, Any]:
    return {
        "occurred_at": entry.occurred_at,
        "actor": entry.actor,
        "event": entry.event,
        "entity": entry.entity,
        "entity_id": entry.entity_id,
        "sku": entry.sku,
        "before": entry.before,
        "after": entry.after,
        "context": dict(entry.context),
    }


def to_entry(row: RowMapping) -> AuditEntry:
    return AuditEntry(
        occurred_at=row["occurred_at"],
        actor=row["actor"],
        event=row["event"],
        entity=row["entity"],
        entity_id=row["entity_id"],
        sku=row["sku"],
        before=row["before"],
        after=row["after"],
        context=row["context"],
    )
