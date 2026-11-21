import pytest

from ecommerce.shared_kernel.domain.errors import (
    DomainValidationError,
    NotFoundError,
    Severity,
    ValidationIssue,
)


def test_validation_issue_defaults_to_error_severity_and_no_params() -> None:
    issue = ValidationIssue(field="sku", code="invalid_sku_format", message="Bad SKU.")
    assert issue.severity is Severity.ERROR
    assert issue.params == {}


def test_validation_error_carries_every_issue() -> None:
    issues = [
        ValidationIssue("name", "required", "Type a name."),
        ValidationIssue("price", "too_small", "Too small.", params={"min": 0}),
    ]

    error = DomainValidationError(issues)

    assert error.issues == tuple(issues)
    assert "2" in str(error)


def test_validation_error_needs_at_least_one_issue() -> None:
    with pytest.raises(ValueError):
        DomainValidationError([])


def test_not_found_detail_is_optional() -> None:
    assert NotFoundError().detail is None
    assert NotFoundError("Product not found.").detail == "Product not found."
