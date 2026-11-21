from dataclasses import dataclass

from ecommerce.weather.domain.errors import InvalidCity

MAX_CITY_LENGTH = 100


@dataclass(frozen=True)
class City:
    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed:
            raise InvalidCity("The city name is empty.")
        if len(trimmed) > MAX_CITY_LENGTH:
            raise InvalidCity(f"The city name is longer than {MAX_CITY_LENGTH} characters.")
        object.__setattr__(self, "value", trimmed)
