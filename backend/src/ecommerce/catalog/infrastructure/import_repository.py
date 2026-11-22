from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import RowMapping, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ecommerce.catalog.domain.importing.batch import (
    BATCH_LIFETIME,
    BatchStatus,
    Decision,
    ImportBatch,
    ImportBatchId,
    ImportRow,
    Resolution,
    RowAction,
)
from ecommerce.catalog.domain.importing.classification import Change, RowOutcome
from ecommerce.catalog.domain.importing.events import ImportEvent, ResolutionValue
from ecommerce.catalog.infrastructure.import_tables import import_batch_rows, import_batches
from ecommerce.shared_kernel.domain.errors import Severity, ValidationIssue

DECIMAL_FIELDS = ("price", "weight_kg")


def issue_to_json(issue: ValidationIssue) -> dict[str, Any]:
    return {
        "field": issue.field,
        "code": issue.code,
        "severity": issue.severity.value,
        "message": issue.message,
        "params": dict(issue.params),
    }


def issue_from_json(data: Mapping[str, Any]) -> ValidationIssue:
    return ValidationIssue(
        data["field"], data["code"], data["message"], Severity(data["severity"]), data["params"]
    )


def product_to_json(product: Mapping[str, object]) -> dict[str, Any]:
    return {
        key: str(value) if isinstance(value, Decimal) else value for key, value in product.items()
    }


def product_from_json(data: Mapping[str, Any]) -> dict[str, object]:
    return {key: Decimal(value) if key in DECIMAL_FIELDS else value for key, value in data.items()}


def state_to_json(values: Mapping[str, ResolutionValue]) -> dict[str, Any]:
    return {
        key: list(value) if isinstance(value, tuple) else value for key, value in values.items()
    }


def state_from_json(data: Mapping[str, Any]) -> dict[str, ResolutionValue]:
    return {key: tuple(value) if isinstance(value, list) else value for key, value in data.items()}


def resolution_to_json(resolution: Resolution) -> dict[str, Any]:
    return {
        "action": resolution.action.value,
        "actor": resolution.actor,
        "at": resolution.at.isoformat(),
        "before": state_to_json(resolution.before),
        "after": state_to_json(resolution.after),
        "original_issues": list(resolution.original_issues),
    }


def resolution_from_json(data: Mapping[str, Any]) -> Resolution:
    return Resolution(
        action=RowAction(data["action"]),
        actor=data["actor"],
        at=datetime.fromisoformat(data["at"]),
        before=state_from_json(data["before"]),
        after=state_from_json(data["after"]),
        original_issues=tuple(data["original_issues"]),
    )


def changeable_row_columns(row: ImportRow) -> dict[str, Any]:
    return {
        "current_values": dict(row.values),
        "outcome": row.outcome.value,
        "issues": [issue_to_json(found) for found in row.issues],
        "product": product_to_json(row.product),
        "changes": {
            column: {"before": change.before, "after": change.after}
            for column, change in row.changes.items()
        },
        "target_product_id": row.target_product_id,
        "target_version": row.target_version,
        "needs_confirmation": row.needs_confirmation,
        "decision": row.decision.value if row.decision else None,
        "confirmed": sorted(row.confirmed),
        "history": [resolution_to_json(resolution) for resolution in row.history],
    }


def row_to_columns(batch_id: ImportBatchId, row: ImportRow) -> dict[str, Any]:
    return {
        "batch_id": batch_id,
        "line": row.line,
        "raw": row.raw,
        "raw_values": dict(row.raw_values),
        "original_outcome": row.original_outcome.value,
        "superseded_by": row.superseded_by,
        **changeable_row_columns(row),
    }


def to_row(data: RowMapping) -> ImportRow:
    return ImportRow(
        line=data["line"],
        raw=data["raw"],
        raw_values=dict(data["raw_values"]),
        values=dict(data["current_values"]),
        original_outcome=RowOutcome(data["original_outcome"]),
        outcome=RowOutcome(data["outcome"]),
        issues=tuple(issue_from_json(found) for found in data["issues"]),
        product=product_from_json(data["product"]),
        changes={
            column: Change(change["before"], change["after"])
            for column, change in data["changes"].items()
        },
        target_product_id=data["target_product_id"],
        target_version=data["target_version"],
        needs_confirmation=data["needs_confirmation"],
        superseded_by=data["superseded_by"],
        decision=Decision(data["decision"]) if data["decision"] else None,
        confirmed=frozenset(data["confirmed"]),
        history=[resolution_from_json(resolution) for resolution in data["history"]],
    )


def to_batch(head: RowMapping, rows: Sequence[RowMapping]) -> ImportBatch:
    return ImportBatch(
        batch_id=ImportBatchId(head["id"]),
        file_name=head["file_name"],
        sha256=head["file_sha256"],
        size_bytes=head["size_bytes"],
        uploaded_by=head["uploaded_by"],
        uploaded_at=head["uploaded_at"],
        status=BatchStatus(head["status"]),
        rows=[to_row(row) for row in rows],
        file_warnings=[issue_from_json(found) for found in head["file_warnings"]],
        finished_at=head["finished_at"],
        result=head["result"],
    )


class SqlAlchemyImportBatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._stored_events: list[ImportEvent] = []

    def take_stored_events(self) -> list[ImportEvent]:
        events, self._stored_events = self._stored_events, []
        return events

    def forget_stored_events(self) -> None:
        self._stored_events = []

    async def add(self, batch: ImportBatch) -> None:
        await self._session.execute(
            insert(import_batches).values(
                id=batch.id,
                file_name=batch.file_name,
                file_sha256=batch.sha256,
                size_bytes=batch.size_bytes,
                status=batch.status.value,
                uploaded_by=batch.uploaded_by,
                uploaded_at=batch.uploaded_at,
                finished_at=batch.finished_at,
                file_warnings=[issue_to_json(found) for found in batch.file_warnings],
                result=dict(batch.result),
            )
        )
        rows = [row_to_columns(batch.id, row) for row in batch.rows]
        if rows:
            await self._session.execute(insert(import_batch_rows), rows)
        batch.take_changed_lines()
        self._stored_events.extend(batch.pull_events())

    async def get(self, batch_id: ImportBatchId, *, for_update: bool = False) -> ImportBatch | None:
        statement = select(import_batches).where(import_batches.c.id == batch_id)
        if for_update:
            statement = statement.with_for_update()
        head = (await self._session.execute(statement)).mappings().first()
        if head is None:
            return None
        rows = (
            (
                await self._session.execute(
                    select(import_batch_rows)
                    .where(import_batch_rows.c.batch_id == batch_id)
                    .order_by(import_batch_rows.c.line)
                )
            )
            .mappings()
            .all()
        )
        return to_batch(head, rows)

    async def save(self, batch: ImportBatch) -> None:
        await self._session.execute(
            update(import_batches)
            .where(import_batches.c.id == batch.id)
            .values(
                status=batch.status.value,
                finished_at=batch.finished_at,
                result=dict(batch.result),
            )
        )
        for line in batch.take_changed_lines():
            await self._session.execute(
                update(import_batch_rows)
                .where(
                    import_batch_rows.c.batch_id == batch.id,
                    import_batch_rows.c.line == line,
                )
                .values(changeable_row_columns(batch.row(line)))
            )
        self._stored_events.extend(batch.pull_events())

    async def pending_with_sha256(self, sha256: str, now: datetime) -> list[ImportBatchId]:
        statement = (
            select(import_batches.c.id)
            .where(
                import_batches.c.file_sha256 == sha256,
                import_batches.c.status == BatchStatus.PENDING_REVIEW.value,
                import_batches.c.uploaded_at > now - BATCH_LIFETIME,
            )
            .order_by(import_batches.c.uploaded_at)
        )
        found = (await self._session.execute(statement)).scalars().all()
        return [ImportBatchId(batch_id) for batch_id in found]
