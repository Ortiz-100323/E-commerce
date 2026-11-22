import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from ecommerce.shared_kernel.domain.errors import DomainValidationError, ValidationIssue

MAX_NAME_LENGTH = 200
MAX_EMAIL_LENGTH = 254
MAX_QUANTITY = 10_000
MAX_LINES = 50
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    PAYMENT_FAILED = "PAYMENT_FAILED"


def has_control_characters(value: str) -> bool:
    return any(unicodedata.category(character) == "Cc" for character in value)


def name_issues(raw: str) -> list[ValidationIssue]:
    field = "customer.name"
    if has_control_characters(raw):
        return [
            ValidationIssue(
                field,
                "control_characters_not_allowed",
                "The name must not contain line breaks, tabs or other control characters.",
            )
        ]
    name = raw.strip()
    if not name:
        return [ValidationIssue(field, "required", "Enter your name.")]
    if len(name) > MAX_NAME_LENGTH:
        return [
            ValidationIssue(
                field,
                "too_long",
                f"The name must be at most {MAX_NAME_LENGTH} characters.",
                params={"max_length": MAX_NAME_LENGTH},
            )
        ]
    return []


def email_issues(raw: str) -> list[ValidationIssue]:
    field = "customer.email"
    email = raw.strip()
    if not email:
        return [ValidationIssue(field, "required", "Enter your email address.")]
    if len(email) > MAX_EMAIL_LENGTH:
        return [
            ValidationIssue(
                field,
                "too_long",
                f"The email address must be at most {MAX_EMAIL_LENGTH} characters.",
                params={"max_length": MAX_EMAIL_LENGTH},
            )
        ]
    if EMAIL_PATTERN.fullmatch(email) is None:
        return [
            ValidationIssue(field, "invalid_email", "Enter an email address like name@example.com.")
        ]
    return []


@dataclass(frozen=True)
class Customer:
    name: str
    email: str

    @classmethod
    def of(cls, name: str, email: str) -> Self:
        issues = [*name_issues(name), *email_issues(email)]
        if issues:
            raise DomainValidationError(issues)
        return cls(name=name.strip(), email=email.strip().lower())
