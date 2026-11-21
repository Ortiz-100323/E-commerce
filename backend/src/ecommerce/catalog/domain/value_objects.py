import re
import unicodedata
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Self

from ecommerce.catalog.domain.errors import InvalidProduct
from ecommerce.shared_kernel.domain.errors import DomainValidationError, ValidationIssue
from ecommerce.shared_kernel.domain.money import Money

SKU_PATTERN = r"^[A-Z0-9]+(-[A-Z0-9]+)*$"
MAX_SKU_LENGTH = 64
MAX_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000
MAX_CATEGORY_LENGTH = 80
MAX_PRICE = Decimal("9999999999.99")
MAX_STOCK = 2_147_483_647
MAX_WEIGHT_KG = Decimal("9999999.999")
WEIGHT_DECIMAL_PLACES = 3
GRAM = Decimal("0.001")

_SKU_REGEX = re.compile(SKU_PATTERN)


def issue(field: str, code: str, message: str, **params: str | int) -> ValidationIssue:
    return ValidationIssue(field, code, message, params=params)


def reject(field: str, code: str, message: str, **params: str | int) -> InvalidProduct:
    return InvalidProduct([issue(field, code, message, **params)])


def has_control_characters(value: str, allowed: str = "") -> bool:
    return any(unicodedata.category(char) == "Cc" and char not in allowed for char in value)


def required_text(field: str, value: str, max_length: int) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise reject(field, "required", "This field is required.")
    if len(trimmed) > max_length:
        raise reject(
            field, "too_long", f"Use at most {max_length} characters.", max_length=max_length
        )
    return trimmed


@dataclass(frozen=True)
class Sku:
    value: str

    def __post_init__(self) -> None:
        normalised = required_text("sku", self.value, MAX_SKU_LENGTH).upper()
        if not _SKU_REGEX.fullmatch(normalised):
            raise reject(
                "sku",
                "invalid_sku_format",
                "Use letters, digits and single hyphens only.",
                pattern=SKU_PATTERN,
            )
        object.__setattr__(self, "value", normalised)


@dataclass(frozen=True)
class ProductName:
    value: str

    def __post_init__(self) -> None:
        trimmed = required_text("name", self.value, MAX_NAME_LENGTH)
        issues = []
        if "<" in trimmed or ">" in trimmed:
            issues.append(issue("name", "markup_not_allowed", "Remove the < and > characters."))
        if has_control_characters(trimmed):
            issues.append(
                issue("name", "control_characters_not_allowed", "Remove line breaks and tabs.")
            )
        if issues:
            raise InvalidProduct(issues)
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Description:
    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if len(trimmed) > MAX_DESCRIPTION_LENGTH:
            raise reject(
                "description",
                "too_long",
                f"Use at most {MAX_DESCRIPTION_LENGTH} characters.",
                max_length=MAX_DESCRIPTION_LENGTH,
            )
        if has_control_characters(trimmed, allowed="\n"):
            raise reject(
                "description",
                "control_characters_not_allowed",
                "Only line breaks are allowed; remove tabs and other control characters.",
            )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True, eq=False)
class Category:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", required_text("category", self.value, MAX_CATEGORY_LENGTH)
        )

    @property
    def key(self) -> str:
        return self.value.casefold()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Category) and self.key == other.key

    def __hash__(self) -> int:
        return hash(self.key)


@dataclass(frozen=True)
class Price:
    money: Money

    def __post_init__(self) -> None:
        if self.money.amount < 0:
            raise reject("price", "too_small", "The price cannot be negative.", min=0)
        if self.money.amount > MAX_PRICE:
            raise reject(
                "price", "too_large", f"The price cannot exceed {MAX_PRICE}.", max=str(MAX_PRICE)
            )

    @classmethod
    def of(cls, value: Decimal | int | str) -> Self:
        try:
            money = Money.of(value)
        except DomainValidationError as error:
            raise InvalidProduct(replace(found, field="price") for found in error.issues) from error
        return cls(money)

    @property
    def amount(self) -> Decimal:
        return self.money.amount

    @property
    def is_zero(self) -> bool:
        return self.money.is_zero


@dataclass(frozen=True)
class StockQuantity:
    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError("Stock must be a whole number.")
        if self.value < 0:
            raise reject("stock", "too_small", "Stock cannot be negative.", min=0)
        if self.value > MAX_STOCK:
            raise reject("stock", "too_large", f"Stock cannot exceed {MAX_STOCK}.", max=MAX_STOCK)

    @property
    def is_empty(self) -> bool:
        return self.value == 0


@dataclass(frozen=True)
class Weight:
    kg: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.kg, Decimal):
            raise TypeError("Weight must be Decimal, never float.")
        if not self.kg.is_finite():
            raise reject("weight_kg", "not_a_number", "The weight must be a number.")
        if self.kg < 0:
            raise reject("weight_kg", "too_small", "The weight cannot be negative.", min=0)
        if self.kg > MAX_WEIGHT_KG:
            raise reject(
                "weight_kg",
                "too_large",
                f"The weight cannot exceed {MAX_WEIGHT_KG} kg.",
                max=str(MAX_WEIGHT_KG),
            )
        rounded = self.kg.quantize(GRAM)
        if rounded != self.kg:
            raise reject(
                "weight_kg",
                "too_many_decimal_places",
                f"Use at most {WEIGHT_DECIMAL_PLACES} decimal places.",
                max_decimal_places=WEIGHT_DECIMAL_PLACES,
            )
        object.__setattr__(self, "kg", rounded)

    @classmethod
    def of(cls, value: Decimal | int | str) -> Self:
        if isinstance(value, bool) or not isinstance(value, Decimal | int | str):
            raise TypeError("Weight must be Decimal, int or str, never float.")
        try:
            kg = value if isinstance(value, Decimal) else Decimal(value)
        except InvalidOperation as error:
            raise reject("weight_kg", "not_a_number", "The weight must be a number.") from error
        return cls(kg)


class ProductTag(StrEnum):
    GIFT = "GIFT"
