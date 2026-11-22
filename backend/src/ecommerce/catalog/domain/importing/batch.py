from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import NewType, Self
from uuid import UUID

from ecommerce.catalog.domain.importing.classification import (
    Change,
    Classification,
    ClassifiedRow,
    ExistingProduct,
    RowOutcome,
    evaluate_row,
)
from ecommerce.catalog.domain.importing.errors import (
    ImportNotCommittable,
    ImportNotPending,
    ImportRowNotFound,
    ImportRowNotResolvable,
    InvalidCorrection,
)
from ecommerce.catalog.domain.importing.events import (
    ImportCommitted,
    ImportDiscarded,
    ImportEvent,
    ImportRowConfirmed,
    ImportRowCorrected,
    ImportRowResolved,
    ImportRowSkipped,
    ImportStarted,
    ResolutionValue,
)
from ecommerce.catalog.domain.importing.fields import COLUMNS, error, warning
from ecommerce.catalog.domain.importing.policies import ImportPolicies
from ecommerce.shared_kernel.domain.errors import Severity, ValidationIssue

ImportBatchId = NewType("ImportBatchId", UUID)

BATCH_LIFETIME = timedelta(hours=24)
CONFIRMABLE = frozenset({"zero_price", "zero_weight"})
KEPT_WARNINGS = frozenset({"duplicate_sku_in_file"})
ACTIVE_OUTCOMES = frozenset(
    {RowOutcome.CREATE, RowOutcome.UPDATE, RowOutcome.UNCHANGED, RowOutcome.NEEDS_REVIEW}
)


class BatchStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    COMMITTED = "COMMITTED"
    DISCARDED = "DISCARDED"
    EXPIRED = "EXPIRED"


class Decision(StrEnum):
    CONFIRMED = "confirmed"
    SKIPPED = "skipped"


class RowAction(StrEnum):
    CONFIRM = "confirm"
    CORRECT = "correct"
    SKIP = "skip"


@dataclass(frozen=True, kw_only=True)
class Resolution:
    action: RowAction
    actor: str
    at: datetime
    before: Mapping[str, ResolutionValue]
    after: Mapping[str, ResolutionValue]
    original_issues: tuple[str, ...]


@dataclass(kw_only=True)
class ImportRow:
    line: int
    raw: str
    raw_values: Mapping[str, str]
    values: dict[str, str]
    original_outcome: RowOutcome
    outcome: RowOutcome
    issues: tuple[ValidationIssue, ...]
    product: dict[str, object]
    changes: dict[str, Change]
    target_product_id: UUID | None
    target_version: int | None
    needs_confirmation: bool
    superseded_by: int | None
    decision: Decision | None = None
    confirmed: frozenset[str] = frozenset()
    history: list[Resolution] = field(default_factory=list)

    @classmethod
    def of(cls, row: ClassifiedRow) -> Self:
        return cls(
            line=row.line,
            raw=row.raw,
            raw_values=dict(row.values),
            values=dict(row.values),
            original_outcome=row.outcome,
            outcome=row.outcome,
            issues=row.issues,
            product=dict(row.product),
            changes=dict(row.changes),
            target_product_id=row.target.product_id if row.target else None,
            target_version=row.target.version if row.target else None,
            needs_confirmation=row.needs_confirmation,
            superseded_by=row.superseded_by,
        )

    @property
    def sku(self) -> str | None:
        sku = self.product.get("sku")
        return sku if isinstance(sku, str) else None

    @property
    def editable(self) -> bool:
        return self.original_outcome is RowOutcome.NEEDS_REVIEW

    @property
    def review_codes(self) -> frozenset[str]:
        return frozenset(found.code for found in self.issues if found.severity is Severity.REVIEW)

    @property
    def is_pending(self) -> bool:
        if self.outcome is RowOutcome.NEEDS_REVIEW:
            return self.decision is not Decision.SKIPPED
        return (
            self.outcome is RowOutcome.UPDATE and self.needs_confirmation and self.decision is None
        )

    @property
    def applies(self) -> bool:
        if self.decision is Decision.SKIPPED:
            return False
        if self.outcome is RowOutcome.CREATE:
            return True
        return self.outcome is RowOutcome.UPDATE and (
            not self.needs_confirmation or self.decision is Decision.CONFIRMED
        )

    @property
    def actions(self) -> tuple[RowAction, ...]:
        allowed: list[RowAction] = []
        codes = self.review_codes
        if (self.outcome is RowOutcome.NEEDS_REVIEW and codes and codes <= CONFIRMABLE) or (
            self.outcome is RowOutcome.UPDATE and self.needs_confirmation
        ):
            allowed.append(RowAction.CONFIRM)
        if self.editable:
            allowed.append(RowAction.CORRECT)
        if self.editable or self.outcome in (RowOutcome.NEEDS_REVIEW, RowOutcome.UPDATE):
            allowed.append(RowAction.SKIP)
        return tuple(allowed)

    def state(self) -> dict[str, ResolutionValue]:
        return {
            "outcome": self.outcome.value,
            "decision": self.decision.value if self.decision else "none",
            "gift": self.product.get("gift") is True,
            **self.values,
        }

    def take(self, classified: ClassifiedRow) -> None:
        kept = tuple(
            found
            for found in self.issues
            if found.code in KEPT_WARNINGS and classified.sku == self.sku
        )
        self.values = dict(classified.values)
        self.outcome = classified.outcome
        self.issues = classified.issues + kept
        self.product = dict(classified.product)
        self.changes = dict(classified.changes)
        self.target_product_id = classified.target.product_id if classified.target else None
        self.target_version = classified.target.version if classified.target else None
        self.needs_confirmation = classified.needs_confirmation


def changed_between(
    before: Mapping[str, ResolutionValue], after: Mapping[str, ResolutionValue]
) -> tuple[dict[str, ResolutionValue], dict[str, ResolutionValue]]:
    keys = [key for key in after if key == "outcome" or before.get(key) != after[key]]
    return {key: before[key] for key in keys}, {key: after[key] for key in keys}


EVENTS: dict[RowAction, type[ImportRowResolved]] = {
    RowAction.CONFIRM: ImportRowConfirmed,
    RowAction.CORRECT: ImportRowCorrected,
    RowAction.SKIP: ImportRowSkipped,
}


class ImportBatch:
    def __init__(
        self,
        *,
        batch_id: ImportBatchId,
        file_name: str,
        sha256: str,
        size_bytes: int,
        uploaded_by: str,
        uploaded_at: datetime,
        status: BatchStatus,
        rows: Sequence[ImportRow],
        file_warnings: Sequence[ValidationIssue],
        finished_at: datetime | None,
        result: Mapping[str, int],
    ) -> None:
        self._id = batch_id
        self._file_name = file_name
        self._sha256 = sha256
        self._size_bytes = size_bytes
        self._uploaded_by = uploaded_by
        self._uploaded_at = uploaded_at
        self._status = status
        self._rows = {row.line: row for row in rows}
        self._file_warnings = tuple(file_warnings)
        self._finished_at = finished_at
        self._result = dict(result)
        self._events: list[ImportEvent] = []
        self._changed_lines: set[int] = set()

    @classmethod
    def start(
        cls,
        *,
        batch_id: ImportBatchId,
        file_name: str,
        sha256: str,
        size_bytes: int,
        classification: Classification,
        file_warnings: Sequence[ValidationIssue],
        actor: str,
        at: datetime,
    ) -> Self:
        batch = cls(
            batch_id=batch_id,
            file_name=file_name,
            sha256=sha256,
            size_bytes=size_bytes,
            uploaded_by=actor,
            uploaded_at=at,
            status=BatchStatus.PENDING_REVIEW,
            rows=[ImportRow.of(row) for row in classification.rows],
            file_warnings=file_warnings,
            finished_at=None,
            result={},
        )
        batch._events.append(
            ImportStarted(
                batch_id=batch_id,
                file_sha256=sha256,
                occurred_at=at,
                file_name=file_name,
                rows=len(batch._rows),
                summary=batch.counts,
            )
        )
        return batch

    @property
    def id(self) -> ImportBatchId:
        return self._id

    @property
    def file_name(self) -> str:
        return self._file_name

    @property
    def sha256(self) -> str:
        return self._sha256

    @property
    def size_bytes(self) -> int:
        return self._size_bytes

    @property
    def uploaded_by(self) -> str:
        return self._uploaded_by

    @property
    def uploaded_at(self) -> datetime:
        return self._uploaded_at

    @property
    def expires_at(self) -> datetime:
        return self._uploaded_at + BATCH_LIFETIME

    @property
    def status(self) -> BatchStatus:
        return self._status

    @property
    def finished_at(self) -> datetime | None:
        return self._finished_at

    @property
    def result(self) -> Mapping[str, int]:
        return dict(self._result)

    @property
    def file_warnings(self) -> tuple[ValidationIssue, ...]:
        return self._file_warnings

    @property
    def rows(self) -> tuple[ImportRow, ...]:
        return tuple(self._rows[line] for line in sorted(self._rows))

    @property
    def counts(self) -> dict[str, int]:
        counts = {outcome.value: 0 for outcome in RowOutcome}
        for row in self._rows.values():
            counts[row.outcome.value] += 1
        return counts

    @property
    def warnings(self) -> list[tuple[int, ValidationIssue]]:
        return [
            (row.line, found)
            for row in self.rows
            for found in row.issues
            if found.severity is Severity.WARNING
        ]

    @property
    def pending_lines(self) -> list[int]:
        return [row.line for row in self.rows if row.is_pending]

    def status_at(self, now: datetime) -> BatchStatus:
        if self._status is BatchStatus.PENDING_REVIEW and now >= self.expires_at:
            return BatchStatus.EXPIRED
        return self._status

    def is_committable(self, now: datetime) -> bool:
        return self.status_at(now) is BatchStatus.PENDING_REVIEW and not self.pending_lines

    def expire_if_due(self, now: datetime) -> bool:
        if self.status_at(now) is BatchStatus.EXPIRED and self._status is not BatchStatus.EXPIRED:
            self._status = BatchStatus.EXPIRED
            self._finished_at = self.expires_at
            return True
        return False

    def ensure_pending(self, now: datetime) -> None:
        status = self.status_at(now)
        if status is not BatchStatus.PENDING_REVIEW:
            raise ImportNotPending(self._id, status.value)

    def row(self, line: int) -> ImportRow:
        found = self._rows.get(line)
        if found is None:
            raise ImportRowNotFound(self._id, line)
        return found

    def confirm(
        self,
        line: int,
        existing: Mapping[str, ExistingProduct],
        policies: ImportPolicies,
        *,
        actor: str,
        at: datetime,
    ) -> None:
        self.ensure_pending(at)
        row = self.row(line)
        if row.editable and row.outcome in (RowOutcome.CREATE, RowOutcome.UNCHANGED):
            if row.confirmed:
                return
        self._allow(row, RowAction.CONFIRM)
        if row.outcome is RowOutcome.UPDATE:
            if row.decision is Decision.CONFIRMED:
                return

            def confirm_update() -> None:
                row.decision = Decision.CONFIRMED

            self._resolve(row, RowAction.CONFIRM, confirm_update, actor=actor, at=at)
            return
        confirmed = row.confirmed | row.review_codes
        classified = evaluate_row(row.line, row.raw, row.values, confirmed, existing, policies)

        def confirm_review() -> None:
            row.confirmed = confirmed
            row.take(classified)
            row.decision = None

        self._resolve(row, RowAction.CONFIRM, confirm_review, actor=actor, at=at)

    def correct(
        self,
        line: int,
        values: Mapping[str, str],
        existing: Mapping[str, ExistingProduct],
        policies: ImportPolicies,
        *,
        actor: str,
        at: datetime,
    ) -> None:
        self.ensure_pending(at)
        row = self.row(line)
        self._allow(row, RowAction.CORRECT)
        unknown = sorted(set(values) - set(COLUMNS))
        if unknown:
            raise InvalidCorrection(
                [
                    error(column, "unknown_field", "This column is not imported.")
                    for column in unknown
                ]
            )
        merged = {**row.values, **values}
        classified = evaluate_row(row.line, row.raw, merged, row.confirmed, existing, policies)
        problems = [found for found in classified.issues if found.severity is Severity.ERROR]
        clash = self._row_with_sku(classified.sku, line)
        if clash is not None:
            problems.append(
                error(
                    "sku",
                    "duplicate_sku_in_file",
                    f"SKU {classified.sku} is already used by line {clash} of this file.",
                    line=clash,
                )
            )
        if problems:
            raise InvalidCorrection(problems)
        if merged == row.values and row.decision is not Decision.SKIPPED:
            return

        def apply_correction() -> None:
            row.take(classified)
            row.decision = None

        self._resolve(row, RowAction.CORRECT, apply_correction, actor=actor, at=at)

    def skip(self, line: int, *, actor: str, at: datetime) -> None:
        self.ensure_pending(at)
        row = self.row(line)
        self._allow(row, RowAction.SKIP)
        if row.decision is Decision.SKIPPED:
            return

        def skip_row() -> None:
            row.decision = Decision.SKIPPED

        self._resolve(row, RowAction.SKIP, skip_row, actor=actor, at=at)

    def ensure_committable(self, now: datetime) -> None:
        self.ensure_pending(now)
        pending = self.pending_lines
        if pending:
            raise ImportNotCommittable(pending)

    def rows_to_apply(self) -> list[ImportRow]:
        return [row for row in self.rows if row.applies]

    def recheck(
        self, current: Mapping[int, ExistingProduct | None], policies: ImportPolicies
    ) -> None:
        for line, product in current.items():
            row = self.row(line)
            existing = {product.sku: product} if product is not None else {}
            row.take(evaluate_row(row.line, row.raw, row.values, row.confirmed, existing, policies))
            row.decision = None
            row.issues += (
                warning(
                    "sku",
                    "changed_since_preview",
                    "The catalog changed after this file was checked. Review this row again.",
                ),
            )
            self._changed_lines.add(line)

    def mark_committed(self, *, created: int, updated: int, at: datetime) -> None:
        self.ensure_committable(at)
        skipped = sum(1 for row in self._rows.values() if row.decision is Decision.SKIPPED)
        self._status = BatchStatus.COMMITTED
        self._finished_at = at
        self._result = {"created": created, "updated": updated, "skipped": skipped}
        self._events.append(
            ImportCommitted(
                batch_id=self._id,
                file_sha256=self._sha256,
                occurred_at=at,
                created=created,
                updated=updated,
                skipped=skipped,
            )
        )

    def discard(self, at: datetime) -> None:
        if self._status is BatchStatus.DISCARDED:
            return
        self.ensure_pending(at)
        self._status = BatchStatus.DISCARDED
        self._finished_at = at
        self._events.append(
            ImportDiscarded(batch_id=self._id, file_sha256=self._sha256, occurred_at=at)
        )

    @property
    def has_pending_events(self) -> bool:
        return bool(self._events)

    def pull_events(self) -> list[ImportEvent]:
        events, self._events = self._events, []
        return events

    def take_changed_lines(self) -> list[int]:
        lines, self._changed_lines = sorted(self._changed_lines), set()
        return lines

    def _allow(self, row: ImportRow, action: RowAction) -> None:
        if action not in row.actions:
            raise ImportRowNotResolvable(row.line, row.outcome.value, action.value)

    def _row_with_sku(self, sku: str | None, line: int) -> int | None:
        if sku is None:
            return None
        return next(
            (
                other.line
                for other in self.rows
                if other.line != line and other.sku == sku and other.outcome in ACTIVE_OUTCOMES
            ),
            None,
        )

    def _resolve(
        self,
        row: ImportRow,
        action: RowAction,
        change: Callable[[], None],
        *,
        actor: str,
        at: datetime,
    ) -> None:
        original = tuple(found.code for found in row.issues if found.severity is Severity.REVIEW)
        sku = row.sku
        state = row.state()
        change()
        before, after = changed_between(state, row.state())
        row.history.append(
            Resolution(
                action=action,
                actor=actor,
                at=at,
                before=before,
                after=after,
                original_issues=original,
            )
        )
        self._changed_lines.add(row.line)
        self._events.append(
            EVENTS[action](
                batch_id=self._id,
                file_sha256=self._sha256,
                occurred_at=at,
                line=row.line,
                sku=row.sku or sku,
                original_issues=original,
                before=before,
                after=after,
            )
        )
