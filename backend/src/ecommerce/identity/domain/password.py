from dataclasses import dataclass

from ecommerce.shared_kernel.domain.errors import DomainValidationError, ValidationIssue

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


def invalid(code: str, message: str, **params: int) -> DomainValidationError:
    return DomainValidationError([ValidationIssue("password", code, message, params=params)])


@dataclass(frozen=True, repr=False)
class Password:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise invalid("required", "Enter a password.")
        if len(self.value) < MIN_PASSWORD_LENGTH:
            raise invalid(
                "too_short",
                f"Use at least {MIN_PASSWORD_LENGTH} characters.",
                min_length=MIN_PASSWORD_LENGTH,
            )
        if len(self.value) > MAX_PASSWORD_LENGTH:
            raise invalid(
                "too_long",
                f"Use at most {MAX_PASSWORD_LENGTH} characters.",
                max_length=MAX_PASSWORD_LENGTH,
            )

    def __repr__(self) -> str:
        return "Password(****)"

    def __str__(self) -> str:
        return "****"
