import pytest

from ecommerce.shared_kernel.domain.errors import (
    DomainValidationError,
    IssueCollector,
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


def test_issue_collector_returns_the_built_value_when_valid() -> None:
    collector = IssueCollector()

    assert collector.attempt(int, "5") == 5
    assert collector.issues == []


def test_issue_collector_keeps_every_issue_instead_of_raising() -> None:
    collector = IssueCollector()
    first = ValidationIssue("name", "required", "Type a name.")
    second = ValidationIssue("sku", "too_long", "Too long.")

    def reject(issue: ValidationIssue) -> str:
        raise DomainValidationError([issue])

    assert collector.attempt(reject, first) is None
    assert collector.attempt(reject, second) is None
    collector.add(ValidationIssue("price", "too_small", "Too small."))

    assert [issue.field for issue in collector.issues] == ["name", "sku", "price"]


def test_issue_collector_does_not_hide_programming_errors() -> None:
    with pytest.raises(TypeError):
        IssueCollector().attempt(int, None)
