from collections.abc import Collection
from dataclasses import dataclass
from typing import Protocol

from ecommerce.catalog.domain.importing.classification import (
    Classification,
    ExistingProduct,
    SourceRow,
    candidate_skus,
    classify,
)
from ecommerce.catalog.domain.importing.policies import ImportPolicies
from ecommerce.shared_kernel.domain.errors import ParamValue, ValidationIssue

MAX_FILE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True, kw_only=True)
class ImportFile:
    sha256: str
    size_bytes: int
    header: tuple[str, ...]
    rows: tuple[SourceRow, ...]
    warnings: tuple[ValidationIssue, ...]


class ImportFileRejected(Exception):
    def __init__(self, code: str, message: str, **params: ParamValue) -> None:
        self.code = code
        self.message = message
        self.params = params
        super().__init__(message)


class ImportFileReader(Protocol):
    def read(self, content: bytes, media_type: str | None, max_rows: int) -> ImportFile: ...


class ExistingProducts(Protocol):
    async def existing_by_skus(self, skus: Collection[str]) -> dict[str, ExistingProduct]: ...


@dataclass(frozen=True, kw_only=True)
class ImportPreview:
    file: ImportFile
    classification: Classification


class PreviewImport:
    def __init__(
        self, reader: ImportFileReader, products: ExistingProducts, policies: ImportPolicies
    ) -> None:
        self._reader = reader
        self._products = products
        self._policies = policies

    async def execute(self, content: bytes, media_type: str | None) -> ImportPreview:
        imported = self._reader.read(content, media_type, self._policies.max_rows)
        skus = candidate_skus(imported.header, imported.rows)
        existing = await self._products.existing_by_skus(skus) if skus else {}
        classification = classify(imported.header, imported.rows, existing, self._policies)
        return ImportPreview(file=imported, classification=classification)
