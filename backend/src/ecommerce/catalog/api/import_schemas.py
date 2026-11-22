from datetime import datetime
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ecommerce.catalog.application.importing import ImportPreview, ImportState, RowChange
from ecommerce.catalog.domain.importing.batch import ImportRow, Resolution, RowAction
from ecommerce.catalog.domain.importing.classification import ClassifiedRow, RowOutcome
from ecommerce.shared_kernel.domain.errors import ValidationIssue

MAX_VALUE_LENGTH = 10_000


class IssueResponse(BaseModel):
    field: str
    code: str
    severity: str = Field(examples=["warning", "review", "error"])
    message: str
    params: dict[str, Any]

    @classmethod
    def of(cls, issue: ValidationIssue) -> Self:
        return cls(
            field=issue.field,
            code=issue.code,
            severity=issue.severity.value,
            message=issue.message,
            params=dict(issue.params),
        )


class ChangeResponse(BaseModel):
    before: str
    after: str


class ImportRowResponse(BaseModel):
    line: int
    outcome: str = Field(examples=["create"])
    sku: str | None
    name: str | None
    issues: list[IssueResponse]
    changes: dict[str, ChangeResponse]
    needs_confirmation: bool
    superseded_by: int | None
    target_product_id: UUID | None
    values: dict[str, str]
    raw: str

    @classmethod
    def of(cls, row: ClassifiedRow) -> Self:
        name = row.product.get("name")
        return cls(
            line=row.line,
            outcome=row.outcome.value,
            sku=row.sku or (row.values.get("sku", "").strip() or None),
            name=name if isinstance(name, str) else (row.values.get("name", "").strip() or None),
            issues=[IssueResponse.of(found) for found in row.issues],
            changes={
                column: ChangeResponse(before=change.before, after=change.after)
                for column, change in row.changes.items()
            },
            needs_confirmation=row.needs_confirmation,
            superseded_by=row.superseded_by,
            target_product_id=row.target.product_id if row.target else None,
            values=dict(row.values),
            raw=row.raw,
        )


class ImportPreviewResponse(BaseModel):
    sha256: str
    size_bytes: int
    rows: int
    summary: dict[str, int] = Field(
        examples=[
            {
                "create": 84,
                "update": 0,
                "unchanged": 0,
                "needs_review": 6,
                "rejected": 2,
                "superseded": 3,
                "blank": 2,
            }
        ]
    )
    warnings: int
    file_warnings: list[IssueResponse]
    items: list[ImportRowResponse]

    @classmethod
    def of(cls, preview: ImportPreview) -> Self:
        classification = preview.classification
        return cls(
            sha256=preview.file.sha256,
            size_bytes=preview.file.size_bytes,
            rows=len(classification.rows),
            summary=classification.counts,
            warnings=len(classification.warnings) + len(preview.file.warnings),
            file_warnings=[IssueResponse.of(found) for found in preview.file.warnings],
            items=[ImportRowResponse.of(row) for row in classification.rows],
        )


class ResolutionResponse(BaseModel):
    action: str = Field(examples=["correct"])
    actor: str
    at: datetime
    before: dict[str, Any]
    after: dict[str, Any]
    original_issues: list[str]

    @classmethod
    def of(cls, resolution: Resolution) -> Self:
        return cls(
            action=resolution.action.value,
            actor=resolution.actor,
            at=resolution.at,
            before={
                key: list(value) if isinstance(value, tuple) else value
                for key, value in resolution.before.items()
            },
            after={
                key: list(value) if isinstance(value, tuple) else value
                for key, value in resolution.after.items()
            },
            original_issues=list(resolution.original_issues),
        )


class ImportBatchRowResponse(BaseModel):
    line: int
    outcome: str = Field(examples=["needs_review"])
    original_outcome: str = Field(examples=["needs_review"])
    decision: str | None = Field(examples=["confirmed", "skipped", None])
    pending: bool
    applies: bool
    editable: bool
    actions: list[str] = Field(examples=[["confirm", "correct", "skip"]])
    sku: str | None
    name: str | None
    issues: list[IssueResponse]
    changes: dict[str, ChangeResponse]
    needs_confirmation: bool
    superseded_by: int | None
    target_product_id: UUID | None
    values: dict[str, str]
    raw_values: dict[str, str]
    raw: str
    history: list[ResolutionResponse]

    @classmethod
    def of(cls, row: ImportRow) -> Self:
        name = row.product.get("name")
        return cls(
            line=row.line,
            outcome=row.outcome.value,
            original_outcome=row.original_outcome.value,
            decision=row.decision.value if row.decision else None,
            pending=row.is_pending,
            applies=row.applies,
            editable=row.editable,
            actions=[action.value for action in row.actions],
            sku=row.sku or (row.values.get("sku", "").strip() or None),
            name=name if isinstance(name, str) else (row.values.get("name", "").strip() or None),
            issues=[IssueResponse.of(found) for found in row.issues],
            changes={
                column: ChangeResponse(before=change.before, after=change.after)
                for column, change in row.changes.items()
            },
            needs_confirmation=row.needs_confirmation,
            superseded_by=row.superseded_by,
            target_product_id=row.target_product_id,
            values=dict(row.values),
            raw_values=dict(row.raw_values),
            raw=row.raw,
            history=[ResolutionResponse.of(resolution) for resolution in row.history],
        )


class ImportBatchSummaryResponse(BaseModel):
    id: UUID
    file_name: str
    sha256: str
    size_bytes: int
    status: str = Field(examples=["PENDING_REVIEW", "COMMITTED", "DISCARDED", "EXPIRED"])
    uploaded_by: str
    uploaded_at: datetime
    expires_at: datetime
    finished_at: datetime | None
    rows: int
    summary: dict[str, int]
    pending_lines: list[int]
    committable: bool
    result: dict[str, int] = Field(examples=[{"created": 90, "updated": 0, "skipped": 0}])
    warnings: int
    file_warnings: list[IssueResponse]

    @classmethod
    def fields_of(cls, state: ImportState) -> dict[str, Any]:
        batch = state.batch
        return {
            "id": batch.id,
            "file_name": batch.file_name,
            "sha256": batch.sha256,
            "size_bytes": batch.size_bytes,
            "status": state.status.value,
            "uploaded_by": batch.uploaded_by,
            "uploaded_at": batch.uploaded_at,
            "expires_at": batch.expires_at,
            "finished_at": batch.finished_at,
            "rows": len(batch.rows),
            "summary": batch.counts,
            "pending_lines": batch.pending_lines,
            "committable": state.committable,
            "result": dict(batch.result),
            "warnings": len(batch.warnings) + len(batch.file_warnings),
            "file_warnings": [IssueResponse.of(found) for found in batch.file_warnings],
        }

    @classmethod
    def of(cls, state: ImportState) -> Self:
        return cls(**cls.fields_of(state))


class ImportBatchResponse(ImportBatchSummaryResponse):
    items: list[ImportBatchRowResponse]

    @classmethod
    def of(cls, state: ImportState) -> Self:
        return cls(
            **cls.fields_of(state),
            items=[ImportBatchRowResponse.of(row) for row in state.batch.rows],
        )


class ImportRowChangeResponse(BaseModel):
    batch: ImportBatchSummaryResponse
    row: ImportBatchRowResponse

    @classmethod
    def of(cls, change: RowChange) -> Self:
        return cls(
            batch=ImportBatchSummaryResponse.of(change.state),
            row=ImportBatchRowResponse.of(change.row),
        )


class RowValuesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=MAX_VALUE_LENGTH)
    sku: str | None = Field(default=None, max_length=MAX_VALUE_LENGTH)
    description: str | None = Field(default=None, max_length=MAX_VALUE_LENGTH)
    category: str | None = Field(default=None, max_length=MAX_VALUE_LENGTH)
    price: str | None = Field(default=None, max_length=MAX_VALUE_LENGTH)
    stock: str | None = Field(default=None, max_length=MAX_VALUE_LENGTH)
    weight_kg: str | None = Field(default=None, max_length=MAX_VALUE_LENGTH)

    def provided(self) -> dict[str, str]:
        return {key: value for key, value in self.model_dump().items() if value is not None}


class ResolveRowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: RowAction = Field(examples=["confirm", "correct", "skip"])
    expected_outcome: RowOutcome | None = Field(
        default=None,
        description="The row outcome shown to the reviewer; required with `confirm`.",
    )
    values: RowValuesRequest | None = Field(
        default=None, description="The corrected values; only with the action `correct`."
    )
