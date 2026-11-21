from decimal import Decimal
from typing import Any

import pytest

from ecommerce.shared_kernel.api.validation import (
    FALLBACK_CODE,
    PYDANTIC_CODES,
    field_error_from_issue,
    field_error_from_pydantic,
    split_location,
)
from ecommerce.shared_kernel.domain.errors import ValidationIssue


@pytest.mark.parametrize(
    ("loc", "expected"),
    [
        (("body", "price"), ("body", "price")),
        (("body", "lines", 0, "quantity"), ("body", "lines[0].quantity")),
        (("body", "lines", 2), ("body", "lines[2]")),
        (("query", "page_size"), ("query", "page_size")),
        (("header", "idempotency-key"), ("header", "idempotency-key")),
        (("body",), ("body", "")),
        ((), ("body", "")),
    ],
)
def test_location_is_split_into_location_and_field(
    loc: tuple[str | int, ...], expected: tuple[str, str]
) -> None:
    assert split_location(loc) == expected


@pytest.mark.parametrize(
    ("pydantic_type", "code"),
    [
        ("missing", "required"),
        ("string_too_long", "too_long"),
        ("int_parsing", "not_an_integer"),
        ("decimal_parsing", "not_a_number"),
        ("decimal_max_places", "too_many_decimal_places"),
        ("greater_than_equal", "too_small"),
        ("extra_forbidden", "unknown_field"),
    ],
)
def test_architecture_table_of_codes_is_mapped(pydantic_type: str, code: str) -> None:
    assert PYDANTIC_CODES[pydantic_type] == code


def pydantic_error(**overrides: Any) -> dict[str, Any]:
    error: dict[str, Any] = {
        "type": "string_too_long",
        "loc": ("body", "name"),
        "msg": "String should have at most 200 characters",
        "input": "x" * 201,
        "ctx": {"max_length": 200},
        "url": "https://errors.pydantic.dev/2/v/string_too_long",
    }
    error.update(overrides)
    return error


def test_pydantic_error_is_converted_without_echoing_the_input() -> None:
    converted = field_error_from_pydantic(pydantic_error())

    assert converted.as_dict() == {
        "location": "body",
        "field": "name",
        "code": "too_long",
        "message": "String should have at most 200 characters",
        "params": {"max_length": 200},
    }
    assert "x" * 201 not in str(converted.as_dict())


def test_unmapped_pydantic_type_falls_back_to_a_generic_code() -> None:
    assert field_error_from_pydantic(pydantic_error(type="brand_new")).code == FALLBACK_CODE


def test_params_keep_only_plain_values_and_drop_error_objects() -> None:
    ctx = {"ge": Decimal("0"), "error": ValueError("4242424242424242"), "flag": True}

    converted = field_error_from_pydantic(pydantic_error(type="greater_than_equal", ctx=ctx))

    assert converted.params == {"ge": "0", "flag": True}


def test_domain_issue_becomes_a_body_field_error() -> None:
    issue = ValidationIssue("sku", "invalid_sku_format", "Bad SKU.", params={"pattern": "^A$"})

    assert field_error_from_issue(issue).as_dict() == {
        "location": "body",
        "field": "sku",
        "code": "invalid_sku_format",
        "message": "Bad SKU.",
        "params": {"pattern": "^A$"},
    }
