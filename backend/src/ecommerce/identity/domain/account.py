import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import NewType, Self
from uuid import UUID, uuid4

from ecommerce.shared_kernel.domain.actor import MAX_ACTOR_LENGTH
from ecommerce.shared_kernel.domain.errors import (
    DomainValidationError,
    IssueCollector,
    ValidationIssue,
)
from ecommerce.shared_kernel.domain.principal import Principal, Role

AccountId = NewType("AccountId", UUID)

MAX_EMAIL_LENGTH = 254
MAX_ACCOUNT_NAME_LENGTH = MAX_ACTOR_LENGTH
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def new_account_id() -> AccountId:
    return AccountId(uuid4())


def has_control_characters(value: str) -> bool:
    return any(unicodedata.category(character) == "Cc" for character in value)


def invalid(field_name: str, code: str, message: str, **params: int) -> DomainValidationError:
    return DomainValidationError([ValidationIssue(field_name, code, message, params=params)])


@dataclass(frozen=True)
class EmailAddress:
    value: str

    def __post_init__(self) -> None:
        if has_control_characters(self.value):
            raise invalid(
                "email",
                "control_characters_not_allowed",
                "The email address must not contain control characters.",
            )
        email = self.value.strip().lower()
        if not email:
            raise invalid("email", "required", "Enter your email address.")
        if len(email) > MAX_EMAIL_LENGTH:
            raise invalid(
                "email",
                "too_long",
                f"The email address must be at most {MAX_EMAIL_LENGTH} characters.",
                max_length=MAX_EMAIL_LENGTH,
            )
        if EMAIL_PATTERN.fullmatch(email) is None:
            raise invalid("email", "invalid_email", "Enter an email address like name@example.com.")
        object.__setattr__(self, "value", email)


@dataclass(frozen=True)
class AccountName:
    value: str

    def __post_init__(self) -> None:
        if has_control_characters(self.value):
            raise invalid(
                "name",
                "control_characters_not_allowed",
                "The name must not contain line breaks, tabs or other control characters.",
            )
        name = self.value.strip()
        if not name:
            raise invalid("name", "required", "Enter a name.")
        if len(name) > MAX_ACCOUNT_NAME_LENGTH:
            raise invalid(
                "name",
                "too_long",
                f"The name must be at most {MAX_ACCOUNT_NAME_LENGTH} characters.",
                max_length=MAX_ACCOUNT_NAME_LENGTH,
            )
        object.__setattr__(self, "value", name)


@dataclass(frozen=True, kw_only=True)
class Account:
    account_id: AccountId
    name: AccountName
    email: EmailAddress
    role: Role
    password_hash: str = field(repr=False)
    active: bool
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        account_id: AccountId,
        name: str,
        email: str,
        role: Role,
        password_hash: str,
        at: datetime,
    ) -> Self:
        collector = IssueCollector()
        valid_name = collector.attempt(AccountName, name)
        valid_email = collector.attempt(EmailAddress, email)
        if collector.issues:
            raise DomainValidationError(collector.issues)
        assert valid_name is not None and valid_email is not None
        return cls(
            account_id=account_id,
            name=valid_name,
            email=valid_email,
            role=role,
            password_hash=password_hash,
            active=True,
            created_at=at,
        )

    @property
    def id(self) -> AccountId:
        return self.account_id

    def principal(self) -> Principal:
        return Principal(
            account_id=self.account_id,
            name=self.name.value,
            email=self.email.value,
            role=self.role,
        )
