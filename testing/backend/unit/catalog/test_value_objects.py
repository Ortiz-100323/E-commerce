from decimal import Decimal
from typing import Any

import pytest

from ecommerce.catalog.domain.value_objects import (
    MAX_PRICE,
    MAX_STOCK,
    MAX_WEIGHT_KG,
    SKU_PATTERN,
    Category,
    Description,
    Price,
    ProductName,
    ProductTag,
    Sku,
    StockQuantity,
    Weight,
)
from ecommerce.shared_kernel.domain.errors import DomainValidationError, ValidationIssue

FLOAT_VALUE: Any = 1.5
BOOL_VALUE: Any = True


def only_issue(error: DomainValidationError) -> ValidationIssue:
    assert len(error.issues) == 1
    return error.issues[0]


def test_sku_is_trimmed_and_upper_cased() -> None:
    assert Sku("  wm-042 ").value == "WM-042"


@pytest.mark.parametrize("value", ["A", "AB-12", "X1-Y2-Z3", "123", "A" * 64])
def test_sku_accepts_letters_digits_and_single_hyphens(value: str) -> None:
    assert Sku(value).value == value


@pytest.mark.parametrize("value", ["", "   "])
def test_sku_is_required(value: str) -> None:
    with pytest.raises(DomainValidationError) as raised:
        Sku(value)
    issue = only_issue(raised.value)
    assert (issue.field, issue.code) == ("sku", "required")


def test_sku_is_at_most_64_characters() -> None:
    with pytest.raises(DomainValidationError) as raised:
        Sku("A" * 65)
    issue = only_issue(raised.value)
    assert (issue.field, issue.code, issue.params) == ("sku", "too_long", {"max_length": 64})


@pytest.mark.parametrize("value", ["AB--1", "-AB", "AB-", "AB 1", "AB_1", "ÉCLAIR", "A/B"])
def test_sku_rejects_other_formats(value: str) -> None:
    with pytest.raises(DomainValidationError) as raised:
        Sku(value)
    issue = only_issue(raised.value)
    assert (issue.field, issue.code) == ("sku", "invalid_sku_format")
    assert issue.params == {"pattern": SKU_PATTERN}


def test_product_name_is_trimmed() -> None:
    assert ProductName("  Running Shoes ").value == "Running Shoes"


def test_product_name_keeps_sql_looking_text_as_plain_text() -> None:
    value = "Robert'); DROP TABLE products;--"
    assert ProductName(value).value == value


@pytest.mark.parametrize("value", ["", " \t "])
def test_product_name_is_required(value: str) -> None:
    with pytest.raises(DomainValidationError) as raised:
        ProductName(value)
    issue = only_issue(raised.value)
    assert (issue.field, issue.code) == ("name", "required")


def test_product_name_is_at_most_200_characters() -> None:
    assert len(ProductName("N" * 200).value) == 200
    with pytest.raises(DomainValidationError) as raised:
        ProductName("N" * 201)
    issue = only_issue(raised.value)
    assert (issue.code, issue.params) == ("too_long", {"max_length": 200})


@pytest.mark.parametrize("value", ["<script>alert('xss')</script>", "a < b", "b > a"])
def test_product_name_rejects_markup(value: str) -> None:
    with pytest.raises(DomainValidationError) as raised:
        ProductName(value)
    issue = only_issue(raised.value)
    assert (issue.field, issue.code) == ("name", "markup_not_allowed")


@pytest.mark.parametrize("value", ["Line\nbreak", "Tab\tname", "Bell\x07"])
def test_product_name_rejects_control_characters(value: str) -> None:
    with pytest.raises(DomainValidationError) as raised:
        ProductName(value)
    issue = only_issue(raised.value)
    assert (issue.field, issue.code) == ("name", "control_characters_not_allowed")


def test_product_name_reports_markup_and_control_characters_together() -> None:
    with pytest.raises(DomainValidationError) as raised:
        ProductName("<b>\x07")
    assert [issue.code for issue in raised.value.issues] == [
        "markup_not_allowed",
        "control_characters_not_allowed",
    ]


def test_product_name_keeps_unicode() -> None:
    assert ProductName("Smart Watch™ — Pro").value == "Smart Watch™ — Pro"


def test_description_is_trimmed_and_may_be_empty() -> None:
    assert Description("  ").value == ""
    assert Description(" Soft cotton. ").value == "Soft cotton."


def test_description_allows_newlines() -> None:
    assert Description("Line one\nLine two").value == "Line one\nLine two"


def test_description_is_at_most_2000_characters() -> None:
    assert len(Description("d" * 2000).value) == 2000
    with pytest.raises(DomainValidationError) as raised:
        Description("d" * 2001)
    issue = only_issue(raised.value)
    assert (issue.field, issue.code, issue.params) == (
        "description",
        "too_long",
        {"max_length": 2000},
    )


@pytest.mark.parametrize("value", ["Tab\there", "Return\rhere", "Null\x00here"])
def test_description_rejects_control_characters_other_than_newline(value: str) -> None:
    with pytest.raises(DomainValidationError) as raised:
        Description(value)
    issue = only_issue(raised.value)
    assert (issue.field, issue.code) == ("description", "control_characters_not_allowed")


def test_category_is_trimmed() -> None:
    assert Category("  Electronics ").value == "Electronics"


def test_category_is_compared_case_insensitively_and_keeps_its_spelling() -> None:
    assert Category("Electronics") == Category("ELECTRONICS")
    assert hash(Category("Electronics")) == hash(Category("electronics"))
    assert Category("electronics").value == "electronics"
    assert Category("Electronics") != Category("Books")
    assert Category("Electronics") != "Electronics"


@pytest.mark.parametrize("value", ["", "  "])
def test_category_is_required(value: str) -> None:
    with pytest.raises(DomainValidationError) as raised:
        Category(value)
    issue = only_issue(raised.value)
    assert (issue.field, issue.code) == ("category", "required")


def test_category_is_at_most_80_characters() -> None:
    assert len(Category("c" * 80).value) == 80
    with pytest.raises(DomainValidationError) as raised:
        Category("c" * 81)
    issue = only_issue(raised.value)
    assert (issue.code, issue.params) == ("too_long", {"max_length": 80})


@pytest.mark.parametrize(("value", "expected"), [("29.99", "29.99"), (5, "5.00"), ("0", "0.00")])
def test_price_accepts_zero_and_positive_amounts(value: str | int, expected: str) -> None:
    price = Price.of(value)
    assert str(price.amount) == expected
    assert price.money.currency == "USD"


def test_price_knows_when_it_is_zero() -> None:
    assert Price.of("0.00").is_zero
    assert not Price.of("0.01").is_zero


def test_price_rejects_negative_amounts() -> None:
    with pytest.raises(DomainValidationError) as raised:
        Price.of("-1")
    issue = only_issue(raised.value)
    assert (issue.field, issue.code, issue.params) == ("price", "too_small", {"min": 0})


def test_price_has_a_maximum_that_fits_the_database_column() -> None:
    assert Price.of(MAX_PRICE).amount == MAX_PRICE
    with pytest.raises(DomainValidationError) as raised:
        Price.of(MAX_PRICE + Decimal("0.01"))
    issue = only_issue(raised.value)
    assert (issue.field, issue.code, issue.params) == (
        "price",
        "too_large",
        {"max": str(MAX_PRICE)},
    )


@pytest.mark.parametrize(
    ("value", "code"),
    [("9.999", "too_many_decimal_places"), ("abc", "not_a_number"), ("NaN", "not_a_number")],
)
def test_price_reports_money_errors_on_the_price_field(value: str, code: str) -> None:
    with pytest.raises(DomainValidationError) as raised:
        Price.of(value)
    issue = only_issue(raised.value)
    assert (issue.field, issue.code) == ("price", code)


def test_price_rejects_floats() -> None:
    with pytest.raises(TypeError):
        Price.of(FLOAT_VALUE)


@pytest.mark.parametrize("value", [0, 1, 99999, MAX_STOCK])
def test_stock_accepts_whole_numbers_from_zero(value: int) -> None:
    assert StockQuantity(value).value == value


def test_stock_rejects_negative_numbers() -> None:
    with pytest.raises(DomainValidationError) as raised:
        StockQuantity(-5)
    issue = only_issue(raised.value)
    assert (issue.field, issue.code, issue.params) == ("stock", "too_small", {"min": 0})


def test_stock_has_a_maximum_that_fits_the_database_column() -> None:
    with pytest.raises(DomainValidationError) as raised:
        StockQuantity(MAX_STOCK + 1)
    issue = only_issue(raised.value)
    assert (issue.field, issue.code, issue.params) == ("stock", "too_large", {"max": MAX_STOCK})


@pytest.mark.parametrize("value", [FLOAT_VALUE, BOOL_VALUE, "5"])
def test_stock_rejects_values_that_are_not_whole_numbers(value: Any) -> None:
    with pytest.raises(TypeError):
        StockQuantity(value)


def test_stock_knows_when_it_is_empty() -> None:
    assert StockQuantity(0).is_empty
    assert not StockQuantity(1).is_empty


@pytest.mark.parametrize(
    ("value", "expected"), [("1.25", "1.250"), (2, "2.000"), ("0", "0.000"), ("0.001", "0.001")]
)
def test_weight_keeps_three_decimal_places(value: str | int, expected: str) -> None:
    assert str(Weight.of(value).kg) == expected


def test_weight_rejects_negative_values() -> None:
    with pytest.raises(DomainValidationError) as raised:
        Weight.of("-0.5")
    issue = only_issue(raised.value)
    assert (issue.field, issue.code, issue.params) == ("weight_kg", "too_small", {"min": 0})


def test_weight_rejects_more_than_three_decimal_places() -> None:
    with pytest.raises(DomainValidationError) as raised:
        Weight.of("1.2345")
    issue = only_issue(raised.value)
    assert (issue.field, issue.code, issue.params) == (
        "weight_kg",
        "too_many_decimal_places",
        {"max_decimal_places": 3},
    )


def test_weight_has_a_maximum_that_fits_the_database_column() -> None:
    assert Weight.of(MAX_WEIGHT_KG).kg == MAX_WEIGHT_KG
    with pytest.raises(DomainValidationError) as raised:
        Weight.of(MAX_WEIGHT_KG + Decimal("0.001"))
    issue = only_issue(raised.value)
    assert (issue.code, issue.params) == ("too_large", {"max": str(MAX_WEIGHT_KG)})


@pytest.mark.parametrize("value", ["heavy", "NaN", "Infinity", ""])
def test_weight_rejects_values_that_are_not_numbers(value: str) -> None:
    with pytest.raises(DomainValidationError) as raised:
        Weight.of(value)
    issue = only_issue(raised.value)
    assert (issue.field, issue.code) == ("weight_kg", "not_a_number")


@pytest.mark.parametrize("value", [FLOAT_VALUE, BOOL_VALUE])
def test_weight_rejects_floats_and_booleans(value: Any) -> None:
    with pytest.raises(TypeError):
        Weight.of(value)
    with pytest.raises(TypeError):
        Weight(value)


def test_product_tag_has_only_gift() -> None:
    assert [tag.value for tag in ProductTag] == ["GIFT"]
