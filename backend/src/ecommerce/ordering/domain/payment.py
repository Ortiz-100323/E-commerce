from dataclasses import dataclass, field
from datetime import date
from typing import Self

from ecommerce.shared_kernel.domain.errors import DomainValidationError, ValidationIssue

MIN_CARD_DIGITS = 12
MAX_CARD_DIGITS = 19
SEPARATORS = str.maketrans("", "", " -")


def luhn_valid(digits: str) -> bool:
    total = 0
    for position, character in enumerate(reversed(digits)):
        value = int(character)
        if position % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def number_issues(digits: str) -> list[ValidationIssue]:
    valid = (
        digits.isascii()
        and digits.isdigit()
        and MIN_CARD_DIGITS <= len(digits) <= MAX_CARD_DIGITS
        and luhn_valid(digits)
    )
    if valid:
        return []
    return [
        ValidationIssue(
            "payment.card_number",
            "invalid_card_number",
            "This card number is not valid. Check the digits and try again.",
        )
    ]


def expiry_issues(month: int, year: int, today: date) -> list[ValidationIssue]:
    if not 1 <= month <= 12:
        return [
            ValidationIssue("payment.expiry", "invalid_expiry", "The expiry month must be 1 to 12.")
        ]
    if (year, month) < (today.year, today.month):
        return [ValidationIssue("payment.expiry", "card_expired", "This card has expired.")]
    return []


def cvc_issues(cvc: str) -> list[ValidationIssue]:
    if cvc.isascii() and cvc.isdigit() and len(cvc) in (3, 4):
        return []
    return [
        ValidationIssue(
            "payment.cvc", "invalid_cvc", "The security code is the 3 or 4 digits on the card."
        )
    ]


@dataclass(frozen=True, repr=False)
class PaymentCard:
    number: str
    expiry_month: int
    expiry_year: int
    cvc: str = field(compare=False)

    @classmethod
    def of(cls, number: str, expiry_month: int, expiry_year: int, cvc: str, *, today: date) -> Self:
        digits = number.translate(SEPARATORS)
        issues = [
            *number_issues(digits),
            *expiry_issues(expiry_month, expiry_year, today),
            *cvc_issues(cvc),
        ]
        if issues:
            raise DomainValidationError(issues)
        return cls(number=digits, expiry_month=expiry_month, expiry_year=expiry_year, cvc=cvc)

    @property
    def last4(self) -> str:
        return self.number[-4:]

    def __repr__(self) -> str:
        return f"PaymentCard(**** {self.last4})"

    def __str__(self) -> str:
        return repr(self)
