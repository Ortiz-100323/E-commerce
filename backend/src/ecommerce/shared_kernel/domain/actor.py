import unicodedata
from dataclasses import dataclass

from ecommerce.shared_kernel.domain.errors import DomainValidationError, ValidationIssue

MAX_ACTOR_LENGTH = 100
ACTOR_FIELD = "actor"


def invalid_actor(code: str, message: str, **params: int) -> DomainValidationError:
    return DomainValidationError([ValidationIssue(ACTOR_FIELD, code, message, params=params)])


@dataclass(frozen=True)
class Actor:
    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError("An actor name must be text.")
        if any(unicodedata.category(character) == "Cc" for character in self.name):
            raise invalid_actor(
                "control_characters_not_allowed",
                "The name must not contain line breaks, tabs or other control characters.",
            )
        name = self.name.strip()
        if not name:
            raise invalid_actor("required", "Tell us who is making this change.")
        if len(name) > MAX_ACTOR_LENGTH:
            raise invalid_actor(
                "too_long",
                f"The name must be at most {MAX_ACTOR_LENGTH} characters.",
                max_length=MAX_ACTOR_LENGTH,
            )
        object.__setattr__(self, "name", name)
