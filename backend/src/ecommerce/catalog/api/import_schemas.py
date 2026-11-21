from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, Field

from ecommerce.catalog.application.importing import ImportPreview
from ecommerce.catalog.domain.importing.classification import ClassifiedRow
from ecommerce.shared_kernel.domain.errors import ValidationIssue


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
