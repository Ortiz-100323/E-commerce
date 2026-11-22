from collections.abc import Mapping
from typing import Any

from ecommerce.catalog.domain.errors import DuplicateSku, ProductAlreadyExists, VersionConflict
from ecommerce.catalog.domain.importing.errors import (
    ImportNotCommittable,
    ImportNotPending,
    ImportRowNotResolvable,
    ImportStaleRows,
)
from ecommerce.shared_kernel.api.problem_details import ProblemMapping, ProblemType

VERSION_CONFLICT = ProblemType(
    "version-conflict", 409, "The product was changed by someone else. Reload it and try again."
)
DUPLICATE_SKU = ProblemType("duplicate-sku", 409, "This SKU is already taken.")
PRODUCT_ALREADY_EXISTS = ProblemType("product-already-exists", 409, "This product already exists.")


def version_conflict_detail(error: Exception) -> str:
    assert isinstance(error, VersionConflict)
    return (
        f"You edited version {error.expected_version}, "
        f"but the product is now at version {error.current_version}."
    )


def version_conflict_extra(error: Exception) -> Mapping[str, Any]:
    assert isinstance(error, VersionConflict)
    return {"current_version": error.current_version}


def duplicate_sku_detail(error: Exception) -> str:
    assert isinstance(error, DuplicateSku)
    return f"SKU {error.sku} is already taken."


def duplicate_sku_extra(error: Exception) -> Mapping[str, Any]:
    assert isinstance(error, DuplicateSku)
    return {"sku": error.sku}


CATALOG_PROBLEMS: Mapping[type[Exception], ProblemMapping] = {
    VersionConflict: ProblemMapping(
        VERSION_CONFLICT, detail=version_conflict_detail, extra=version_conflict_extra
    ),
    DuplicateSku: ProblemMapping(
        DUPLICATE_SKU, detail=duplicate_sku_detail, extra=duplicate_sku_extra
    ),
    ProductAlreadyExists: ProblemMapping(PRODUCT_ALREADY_EXISTS),
}


IMPORT_NOT_PENDING = ProblemType(
    "import-not-pending", 409, "This import was already committed, discarded or has expired."
)
IMPORT_ROW_NOT_RESOLVABLE = ProblemType(
    "import-row-not-resolvable", 409, "This row cannot be resolved that way."
)
IMPORT_NOT_COMMITTABLE = ProblemType(
    "import-not-committable", 409, "Some rows still need a decision before the import."
)
IMPORT_STALE_ROWS = ProblemType(
    "import-stale-rows", 409, "Some products changed after the file was checked."
)


def import_not_pending_extra(error: Exception) -> Mapping[str, Any]:
    assert isinstance(error, ImportNotPending)
    return {"import_status": error.status}


def row_not_resolvable_detail(error: Exception) -> str:
    assert isinstance(error, ImportRowNotResolvable)
    return f"Line {error.line} is {error.outcome}, so it cannot be resolved with {error.action}."


def row_not_resolvable_extra(error: Exception) -> Mapping[str, Any]:
    assert isinstance(error, ImportRowNotResolvable)
    return {"line": error.line, "outcome": error.outcome, "action": error.action}


def not_committable_detail(error: Exception) -> str:
    assert isinstance(error, ImportNotCommittable)
    lines = ", ".join(str(line) for line in error.pending_lines)
    return f"Resolve or skip these lines first: {lines}."


def not_committable_extra(error: Exception) -> Mapping[str, Any]:
    assert isinstance(error, ImportNotCommittable)
    return {"pending_lines": list(error.pending_lines)}


def stale_rows_detail(error: Exception) -> str:
    assert isinstance(error, ImportStaleRows)
    lines = ", ".join(str(line) for line in error.lines)
    return (
        f"The products on lines {lines} changed after the file was checked. "
        "Nothing was imported. Review those lines again, then import."
    )


def stale_rows_extra(error: Exception) -> Mapping[str, Any]:
    assert isinstance(error, ImportStaleRows)
    return {"lines": list(error.lines)}


IMPORT_PROBLEMS: Mapping[type[Exception], ProblemMapping] = {
    ImportNotPending: ProblemMapping(IMPORT_NOT_PENDING, extra=import_not_pending_extra),
    ImportRowNotResolvable: ProblemMapping(
        IMPORT_ROW_NOT_RESOLVABLE, detail=row_not_resolvable_detail, extra=row_not_resolvable_extra
    ),
    ImportNotCommittable: ProblemMapping(
        IMPORT_NOT_COMMITTABLE, detail=not_committable_detail, extra=not_committable_extra
    ),
    ImportStaleRows: ProblemMapping(
        IMPORT_STALE_ROWS, detail=stale_rows_detail, extra=stale_rows_extra
    ),
}
