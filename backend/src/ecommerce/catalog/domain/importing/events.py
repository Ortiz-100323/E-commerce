from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

type ResolutionValue = str | bool | tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class ImportEvent:
    batch_id: UUID
    file_sha256: str
    occurred_at: datetime


@dataclass(frozen=True, kw_only=True)
class ImportStarted(ImportEvent):
    file_name: str
    rows: int
    summary: Mapping[str, int]


@dataclass(frozen=True, kw_only=True)
class ImportRowResolved(ImportEvent):
    line: int
    sku: str | None
    original_issues: tuple[str, ...]
    before: Mapping[str, ResolutionValue]
    after: Mapping[str, ResolutionValue]


@dataclass(frozen=True, kw_only=True)
class ImportRowConfirmed(ImportRowResolved):
    pass


@dataclass(frozen=True, kw_only=True)
class ImportRowCorrected(ImportRowResolved):
    pass


@dataclass(frozen=True, kw_only=True)
class ImportRowSkipped(ImportRowResolved):
    pass


@dataclass(frozen=True, kw_only=True)
class ImportCommitted(ImportEvent):
    created: int
    updated: int
    skipped: int


@dataclass(frozen=True, kw_only=True)
class ImportDiscarded(ImportEvent):
    pass
