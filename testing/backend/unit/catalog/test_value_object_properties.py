import re
import string
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ecommerce.catalog.domain.value_objects import (
    MAX_PRICE,
    MAX_SKU_LENGTH,
    MAX_STOCK,
    SKU_PATTERN,
    Price,
    Sku,
    StockQuantity,
)
from ecommerce.shared_kernel.domain.errors import DomainValidationError

SKU_CHARACTERS = string.ascii_letters + string.digits
SKU_BREAKERS = ["--", "_", " ", "/", ".", "é", "#", "<"]
LARGEST_CENTS = int(MAX_PRICE * 100)

segments = st.text(alphabet=SKU_CHARACTERS, min_size=1, max_size=8)
valid_skus = (
    st.lists(segments, min_size=1, max_size=8)
    .map("-".join)
    .filter(lambda sku: len(sku) <= MAX_SKU_LENGTH)
)
padding = st.sampled_from(["", " ", "  ", "\t", " \t "])
cents = st.integers(min_value=0, max_value=LARGEST_CENTS)


def amount(value_in_cents: int) -> Decimal:
    return Decimal(value_in_cents) / 100


@given(sku=valid_skus, before=padding, after=padding)
def test_sku_normalisation_is_trim_and_upper_case(sku: str, before: str, after: str) -> None:
    normalised = Sku(f"{before}{sku}{after}")
    assert normalised.value == sku.upper()
    assert re.fullmatch(SKU_PATTERN, normalised.value)
    assert Sku(normalised.value) == normalised


@given(
    sku=valid_skus.filter(lambda sku: len(sku) <= 50),
    breaker=st.sampled_from(SKU_BREAKERS),
    position=st.integers(min_value=1, max_value=50),
)
def test_sku_rejects_anything_outside_the_pattern(sku: str, breaker: str, position: int) -> None:
    index = min(position, len(sku))
    with pytest.raises(DomainValidationError) as raised:
        Sku(f"{sku[:index]}{breaker}{sku[index:]}X")
    assert [issue.code for issue in raised.value.issues] == ["invalid_sku_format"]


@given(value=cents)
def test_any_amount_in_cents_from_zero_to_the_maximum_is_a_price(value: int) -> None:
    price = Price.of(str(amount(value)))
    assert price.amount == amount(value)
    assert Price.of(str(price.amount)) == price


@given(value=cents)
def test_any_negative_amount_is_rejected(value: int) -> None:
    with pytest.raises(DomainValidationError) as raised:
        Price.of(-amount(value + 1))
    assert [issue.code for issue in raised.value.issues] == ["too_small"]


@given(value=cents, extra=st.integers(min_value=1, max_value=9))
def test_any_amount_with_a_third_decimal_place_is_rejected(value: int, extra: int) -> None:
    with pytest.raises(DomainValidationError) as raised:
        Price.of(amount(value) + Decimal(extra) / 1000)
    assert [issue.code for issue in raised.value.issues] == ["too_many_decimal_places"]


@given(value=st.integers(min_value=0, max_value=MAX_STOCK))
def test_any_whole_number_from_zero_to_the_maximum_is_a_stock_quantity(value: int) -> None:
    assert StockQuantity(value).value == value


@given(value=st.integers(max_value=-1))
def test_any_negative_whole_number_is_rejected_as_stock(value: int) -> None:
    with pytest.raises(DomainValidationError):
        StockQuantity(value)


@given(value=st.integers(min_value=MAX_STOCK + 1))
def test_any_number_above_the_maximum_is_rejected_as_stock(value: int) -> None:
    with pytest.raises(DomainValidationError):
        StockQuantity(value)
