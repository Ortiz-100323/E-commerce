from decimal import Decimal
from typing import Any

import pytest

from ecommerce.shared_kernel.domain.errors import DomainValidationError
from ecommerce.shared_kernel.domain.money import InvalidMoney, Money

FLOAT_AMOUNT: Any = 29.99


def codes(error: DomainValidationError) -> list[str]:
    return [issue.code for issue in error.issues]


def test_money_keeps_two_decimal_places() -> None:
    assert str(Money(Decimal("29.9")).amount) == "29.90"
    assert Money(Decimal("1.230")).amount == Decimal("1.23")


def test_money_defaults_to_usd() -> None:
    assert Money(Decimal("1")).currency == "USD"


def test_money_rejects_floats() -> None:
    with pytest.raises(TypeError):
        Money(FLOAT_AMOUNT)
    with pytest.raises(TypeError):
        Money.of(FLOAT_AMOUNT)


def test_money_rejects_more_than_two_decimal_places() -> None:
    with pytest.raises(InvalidMoney) as raised:
        Money(Decimal("9.999"))
    assert codes(raised.value) == ["too_many_decimal_places"]
    assert raised.value.issues[0].params == {"max_decimal_places": 2}


def test_money_rejects_other_currencies() -> None:
    with pytest.raises(InvalidMoney) as raised:
        Money(Decimal("10"), "EUR")
    assert codes(raised.value) == ["unsupported_currency"]


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_money_rejects_non_finite_amounts(value: str) -> None:
    with pytest.raises(InvalidMoney) as raised:
        Money(Decimal(value))
    assert codes(raised.value) == ["not_a_number"]


def test_money_rejects_amounts_beyond_decimal_precision() -> None:
    with pytest.raises(InvalidMoney) as raised:
        Money(Decimal("1" * 40))
    assert codes(raised.value) == ["value_out_of_range"]


@pytest.mark.parametrize(
    ("value", "expected"), [("29.99", "29.99"), (5, "5.00"), (Decimal("0.5"), "0.50")]
)
def test_money_of_accepts_strings_integers_and_decimals(
    value: str | int | Decimal, expected: str
) -> None:
    assert str(Money.of(value).amount) == expected


@pytest.mark.parametrize("value", ["abc", "", "1,299.99"])
def test_money_of_rejects_text_that_is_not_a_number(value: str) -> None:
    with pytest.raises(InvalidMoney) as raised:
        Money.of(value)
    assert codes(raised.value) == ["not_a_number"]


def test_money_of_rejects_booleans() -> None:
    with pytest.raises(TypeError):
        Money.of(True)


def test_money_adds_subtracts_and_multiplies_by_a_quantity() -> None:
    price = Money.of("19.99")
    assert price + Money.of("0.01") == Money.of("20.00")
    assert price - Money.of("9.99") == Money.of("10.00")
    assert price * 3 == Money.of("59.97")


def test_money_multiplies_only_by_whole_quantities() -> None:
    with pytest.raises(TypeError):
        Money.of("1.00") * FLOAT_AMOUNT
    with pytest.raises(TypeError):
        Money.of("1.00") * True


def test_money_compares_and_knows_zero() -> None:
    assert Money.zero().is_zero
    assert Money.of("1.00") > Money.of("0.99")
    assert not Money.of("0.01").is_zero


def test_money_reads_as_amount_and_currency() -> None:
    assert str(Money.of("5")) == "5.00 USD"
