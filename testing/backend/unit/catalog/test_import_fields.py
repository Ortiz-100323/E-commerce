from decimal import Decimal

import pytest

from ecommerce.catalog.domain.importing.fields import COLUMNS, parse_fields
from ecommerce.catalog.domain.importing.policies import (
    CurrencySymbolPolicy,
    EmptyFieldPolicy,
    ImportPolicies,
    ZeroPricePolicy,
    ZeroWeightPolicy,
)
from ecommerce.catalog.domain.value_objects import MAX_PRICE, MAX_STOCK
from ecommerce.shared_kernel.domain.errors import Severity

GOOD = {
    "name": "Running Shoes",
    "sku": "RS-001",
    "description": "Lightweight shoes",
    "category": "Footwear",
    "price": "89.99",
    "stock": "150",
    "weight_kg": "0.35",
}
DEFAULTS = ImportPolicies()


def issues_of(
    policies: ImportPolicies = DEFAULTS, **overrides: str
) -> list[tuple[str, str, Severity]]:
    parsed = parse_fields({**GOOD, **overrides}, policies)
    return [(found.field, found.code, found.severity) for found in parsed.issues]


def test_a_clean_row_parses_into_typed_values_without_issues() -> None:
    parsed = parse_fields(GOOD, DEFAULTS)

    assert parsed.issues == []
    assert parsed.is_complete
    assert parsed.values == {
        "name": "Running Shoes",
        "sku": "RS-001",
        "description": "Lightweight shoes",
        "category": "Footwear",
        "price": Decimal("89.99"),
        "stock": 150,
        "weight_kg": Decimal("0.350"),
        "gift": False,
    }


def test_surrounding_whitespace_and_line_endings_are_handled_silently() -> None:
    parsed = parse_fields(
        {**GOOD, "name": "  Running Shoes  ", "price": " 89.99 ", "description": "a\r\nb"},
        DEFAULTS,
    )

    assert parsed.issues == []
    assert (parsed.values["name"], parsed.values["description"]) == ("Running Shoes", "a\nb")


@pytest.mark.parametrize(
    ("overrides", "column", "code", "stored"),
    [
        ({"price": "$29.99"}, "price", "currency_symbol_stripped", Decimal("29.99")),
        ({"sku": "rs-001"}, "sku", "sku_normalized", "RS-001"),
        ({"stock": "12.0"}, "stock", "integer_normalized", 12),
    ],
)
def test_lossless_fixes_are_warnings_and_the_value_is_kept(
    overrides: dict[str, str], column: str, code: str, stored: object
) -> None:
    parsed = parse_fields({**GOOD, **overrides}, DEFAULTS)

    assert [(found.field, found.code, found.severity) for found in parsed.issues] == [
        (column, code, Severity.WARNING)
    ]
    assert parsed.values[column] == stored


@pytest.mark.parametrize("column", ["name", "sku", "category", "price", "stock", "weight_kg"])
@pytest.mark.parametrize("value", ["", "   "])
def test_an_empty_required_field_is_held_for_review(column: str, value: str) -> None:
    assert issues_of(**{column: value}) == [(column, "empty_required_field", Severity.REVIEW)]


def test_an_empty_description_is_fine() -> None:
    assert issues_of(description="") == []


@pytest.mark.parametrize("price", ["0", "0.00", "free", "FREE", "$0"])
def test_a_zero_price_is_held_for_review_with_a_gift_suggestion(price: str) -> None:
    parsed = parse_fields({**GOOD, "price": price}, DEFAULTS)
    review = [found for found in parsed.issues if found.severity is Severity.REVIEW]

    assert [(found.field, found.code) for found in review] == [("price", "zero_price")]
    assert review[0].params == {"suggestion": "gift"}
    assert parsed.values["gift"] is False


def test_a_zero_weight_is_held_for_review() -> None:
    assert issues_of(weight_kg="0") == [("weight_kg", "zero_weight", Severity.REVIEW)]


@pytest.mark.parametrize(
    ("column", "value", "code"),
    [
        ("price", "abc", "invalid_number"),
        ("price", "1,299.99", "invalid_number"),
        ("price", "12,5", "invalid_number"),
        ("price", "1e3", "invalid_number"),
        ("price", "NaN", "invalid_number"),
        ("price", "Infinity", "invalid_number"),
        ("stock", "ten", "invalid_number"),
        ("weight_kg", "1.2.3", "invalid_number"),
        ("price", "€10", "unsupported_currency"),
        ("price", "USD 10", "unsupported_currency"),
        ("price", "10 EUR", "unsupported_currency"),
        ("price", "£5", "unsupported_currency"),
        ("price", "-1", "negative_value"),
        ("stock", "-5", "negative_value"),
        ("weight_kg", "-0.1", "negative_value"),
        ("price", "9.999", "too_many_decimal_places"),
        ("weight_kg", "0.1234", "too_many_decimal_places"),
        ("stock", "12.5", "not_an_integer"),
        ("price", "10000000000.00", "value_out_of_range"),
        ("stock", str(MAX_STOCK + 1), "value_out_of_range"),
        ("weight_kg", "10000000", "value_out_of_range"),
        ("name", "x" * 201, "value_too_long"),
        ("description", "x" * 2001, "value_too_long"),
        ("category", "x" * 81, "value_too_long"),
        ("sku", "A" * 65, "value_too_long"),
        ("sku", "RS 001", "invalid_sku_format"),
        ("sku", "RS_001", "invalid_sku_format"),
        ("name", "<script>alert('xss')</script>", "markup_in_name"),
        ("name", "Ann\tShoes", "control_characters"),
        ("description", "a\x00b", "control_characters"),
        ("sku", "RS\t001", "control_characters"),
        ("category", "Foot\twear", "control_characters"),
    ],
)
def test_invalid_values_are_errors(column: str, value: str, code: str) -> None:
    assert issues_of(**{column: value}) == [(column, code, Severity.ERROR)]


def test_the_largest_price_and_stock_are_accepted() -> None:
    parsed = parse_fields({**GOOD, "price": str(MAX_PRICE), "stock": str(MAX_STOCK)}, DEFAULTS)

    assert parsed.issues == []


def test_every_issue_in_a_row_is_collected() -> None:
    found = issues_of(category="", stock="-5", name="<b>x</b>", price="$1.999")

    assert found == [
        ("name", "markup_in_name", Severity.ERROR),
        ("category", "empty_required_field", Severity.REVIEW),
        ("price", "currency_symbol_stripped", Severity.WARNING),
        ("price", "too_many_decimal_places", Severity.ERROR),
        ("stock", "negative_value", Severity.ERROR),
    ]


def test_an_sql_looking_name_is_plain_text() -> None:
    parsed = parse_fields({**GOOD, "name": "Robert'); DROP TABLE products;--"}, DEFAULTS)

    assert parsed.issues == []
    assert parsed.values["name"] == "Robert'); DROP TABLE products;--"


def test_a_formula_looking_value_is_stored_as_text() -> None:
    parsed = parse_fields({**GOOD, "name": '=HYPERLINK("http://x")'}, DEFAULTS)

    assert parsed.issues == []


def test_the_columns_are_the_seven_required_by_the_challenge() -> None:
    assert COLUMNS == ("name", "sku", "description", "category", "price", "stock", "weight_kg")


class TestPolicies:
    def test_zero_price_reject_makes_it_an_error(self) -> None:
        policies = ImportPolicies(zero_price=ZeroPricePolicy.REJECT)

        assert issues_of(policies, price="0") == [("price", "zero_price", Severity.ERROR)]

    def test_zero_price_accept_as_gift_imports_it_as_a_gift_with_a_warning(self) -> None:
        policies = ImportPolicies(zero_price=ZeroPricePolicy.ACCEPT_AS_GIFT)
        parsed = parse_fields({**GOOD, "price": "free"}, policies)

        assert [(found.code, found.severity) for found in parsed.issues] == [
            ("zero_price_accepted_as_gift", Severity.WARNING)
        ]
        assert (parsed.values["price"], parsed.values["gift"]) == (Decimal("0.00"), True)

    def test_empty_field_reject_makes_it_an_error(self) -> None:
        policies = ImportPolicies(empty_field=EmptyFieldPolicy.REJECT)

        assert issues_of(policies, name="") == [("name", "empty_required_field", Severity.ERROR)]

    def test_zero_weight_accept_has_no_issue(self) -> None:
        policies = ImportPolicies(zero_weight=ZeroWeightPolicy.ACCEPT)
        parsed = parse_fields({**GOOD, "weight_kg": "0"}, policies)

        assert parsed.issues == []
        assert parsed.values["weight_kg"] == Decimal("0.000")

    def test_zero_weight_reject_makes_it_an_error(self) -> None:
        policies = ImportPolicies(zero_weight=ZeroWeightPolicy.REJECT)

        assert issues_of(policies, weight_kg="0") == [("weight_kg", "zero_weight", Severity.ERROR)]

    def test_currency_symbol_reject_refuses_the_dollar(self) -> None:
        policies = ImportPolicies(currency_symbol=CurrencySymbolPolicy.REJECT)

        assert issues_of(policies, price="$29.99") == [
            ("price", "unsupported_currency", Severity.ERROR)
        ]

    @pytest.mark.parametrize(("threshold", "rows"), [(0, 10), (1.5, 10), (0.5, 0)])
    def test_impossible_settings_are_refused(self, threshold: float, rows: int) -> None:
        with pytest.raises(ValueError):
            ImportPolicies(similarity_threshold=threshold, max_rows=rows)
