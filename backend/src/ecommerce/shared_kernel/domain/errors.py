import dataclasses
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

ParamValue = str | int | float | bool


class Severity(StrEnum):
    ERROR = "error"
    REVIEW = "review"
    WARNING = "warning"


@dataclass(frozen=True, eq=True)
class ValidationIssue:
    field: str
    code: str
    message: str
    severity: Severity = Severity.ERROR
    params: Mapping[str, ParamValue] = dataclasses.field(default_factory=dict, hash=False)


class DomainError(Exception):
    pass


class DomainValidationError(DomainError):
    def __init__(self, issues: Iterable[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        if not self.issues:
            raise ValueError("A validation error needs at least one issue.")
        super().__init__(f"{len(self.issues)} validation issue(s)")


class NotFoundError(DomainError):
    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail
        super().__init__(detail or "Not found.")
