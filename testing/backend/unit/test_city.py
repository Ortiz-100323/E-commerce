import pytest

from ecommerce.weather.domain.city import City
from ecommerce.weather.domain.errors import InvalidCity


def test_city_is_trimmed() -> None:
    assert City("  Lisbon \n").value == "Lisbon"


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
def test_empty_city_is_rejected(raw: str) -> None:
    with pytest.raises(InvalidCity):
        City(raw)


def test_city_of_100_characters_is_accepted() -> None:
    assert len(City("a" * 100).value) == 100


def test_city_over_100_characters_is_rejected() -> None:
    with pytest.raises(InvalidCity):
        City("a" * 101)
