from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Self

from ecommerce.shared_kernel.domain.errors import DomainValidationError, ValidationIssue

SUPPORTED_CURRENCY = "USD"
DECIMAL_PLACES = 2
CENT = Decimal("0.01")


class InvalidMoney(DomainValidationError):
    pass


def invalid(code: str, message: str, **params: str | int) -> InvalidMoney:
    return InvalidMoney([ValidationIssue("amount", code, message, params=params)])


@dataclass(frozen=True, order=True)
class Money:
    amount: Decimal
    currency: str = SUPPORTED_CURRENCY

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError("Money amounts must be Decimal, never float.")
        if not self.amount.is_finite():
            raise invalid("not_a_number", "The amount must be a finite number.")
        if self.currency != SUPPORTED_CURRENCY:
            raise invalid(
                "unsupported_currency",
                f"Only {SUPPORTED_CURRENCY} is supported.",
                supported=SUPPORTED_CURRENCY,
            )
        try:
            rounded = self.amount.quantize(CENT)
        except InvalidOperation as error:
            raise invalid("value_out_of_range", "The amount is too large.") from error
        if rounded != self.amount:
            raise invalid(
                "too_many_decimal_places",
                f"Use at most {DECIMAL_PLACES} decimal places.",
                max_decimal_places=DECIMAL_PLACES,
            )
        object.__setattr__(self, "amount", rounded)

    @classmethod
    def of(cls, value: Decimal | int | str, currency: str = SUPPORTED_CURRENCY) -> Self:
        if isinstance(value, bool) or not isinstance(value, Decimal | int | str):
            raise TypeError("Money amounts must be Decimal, int or str, never float.")
        try:
            amount = value if isinstance(value, Decimal) else Decimal(value)
        except InvalidOperation as error:
            raise invalid("not_a_number", "The amount is not a number.") from error
        return cls(amount, currency)

    @classmethod
    def zero(cls) -> Self:
        return cls(Decimal("0"))

    @property
    def is_zero(self) -> bool:
        return self.amount == 0

    def __add__(self, other: "Money") -> "Money":
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, quantity: int) -> "Money":
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise TypeError("Money can only be multiplied by a whole quantity.")
        return Money(self.amount * quantity, self.currency)

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"
