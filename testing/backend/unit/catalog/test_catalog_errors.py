from uuid import UUID

from ecommerce.catalog.domain.errors import (
    DuplicateSku,
    ProductAlreadyExists,
    ProductNotFound,
    VersionConflict,
)
from ecommerce.shared_kernel.domain.errors import DomainError, NotFoundError

PRODUCT_ID = UUID("00000000-0000-4000-8000-000000000001")


def test_duplicate_sku_carries_the_sku() -> None:
    error = DuplicateSku("RS-001")
    assert isinstance(error, DomainError)
    assert error.sku == "RS-001"
    assert "RS-001" in str(error)


def test_product_already_exists_carries_the_product_id() -> None:
    error = ProductAlreadyExists(PRODUCT_ID)
    assert isinstance(error, DomainError)
    assert error.product_id == PRODUCT_ID
    assert str(PRODUCT_ID) in str(error)


def test_version_conflict_carries_both_versions() -> None:
    error = VersionConflict(PRODUCT_ID, expected_version=1, current_version=3)
    assert isinstance(error, DomainError)
    assert (error.product_id, error.expected_version, error.current_version) == (PRODUCT_ID, 1, 3)


def test_product_not_found_is_a_not_found_error_with_a_detail() -> None:
    error = ProductNotFound(PRODUCT_ID)
    assert isinstance(error, NotFoundError)
    assert error.product_id == PRODUCT_ID
    assert error.detail == "Product not found."
