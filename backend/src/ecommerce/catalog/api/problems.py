from collections.abc import Mapping
from typing import Any

from ecommerce.catalog.domain.errors import DuplicateSku, ProductAlreadyExists, VersionConflict
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
