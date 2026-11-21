from dataclasses import dataclass

from ecommerce.shared_kernel.domain.errors import ValidationIssue
from ecommerce.weather.domain.errors import InvalidCity

MAX_CITY_LENGTH = 100


@dataclass(frozen=True)
class City:
    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed:
            raise InvalidCity([ValidationIssue("city", "required", "Type a city name.")])
        if len(trimmed) > MAX_CITY_LENGTH:
            raise InvalidCity(
                [
                    ValidationIssue(
                        "city",
                        "too_long",
                        f"Use at most {MAX_CITY_LENGTH} characters.",
                        params={"max_length": MAX_CITY_LENGTH},
                    )
                ]
            )
        object.__setattr__(self, "value", trimmed)
