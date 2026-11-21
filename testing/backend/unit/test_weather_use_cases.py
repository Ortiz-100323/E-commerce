from datetime import timedelta

import pytest

from ecommerce.weather.application.errors import CityNotFound, WeatherUnavailable
from ecommerce.weather.application.list_weather_searches import ListWeatherSearches
from ecommerce.weather.application.search_weather import SearchWeather
from ecommerce.weather.domain.errors import InvalidCity
from fakes import (
    FIXED_NOW,
    LISBON,
    SUNNY,
    FakeWeatherProvider,
    InMemoryWeatherSearchRepository,
    SequenceClock,
)


def build(
    provider: FakeWeatherProvider | None = None,
    clock: SequenceClock | None = None,
) -> tuple[SearchWeather, FakeWeatherProvider, InMemoryWeatherSearchRepository]:
    provider = provider or FakeWeatherProvider()
    repository = InMemoryWeatherSearchRepository()
    use_case = SearchWeather(provider, repository, clock or SequenceClock())
    return use_case, provider, repository


async def test_search_saves_and_returns_the_search() -> None:
    use_case, provider, repository = build()

    view = await use_case.execute("  Lisbon ")

    assert provider.calls == ["Lisbon"]
    assert len(repository.items) == 1
    assert view.id == repository.items[0].id
    assert view.city == "Lisbon"
    assert view.location_name == LISBON.name
    assert view.country == LISBON.country
    assert view.latitude == LISBON.latitude
    assert view.longitude == LISBON.longitude
    assert view.temperature_c == SUNNY.temperature_c
    assert view.wind_speed_kmh == SUNNY.wind_speed_kmh
    assert view.weather_code == SUNNY.weather_code
    assert view.searched_at == FIXED_NOW


async def test_invalid_city_is_rejected_before_calling_the_provider() -> None:
    use_case, provider, repository = build()

    with pytest.raises(InvalidCity):
        await use_case.execute("   ")

    assert provider.calls == []
    assert repository.items == []


@pytest.mark.parametrize("error", [CityNotFound(), WeatherUnavailable("down")])
async def test_provider_errors_propagate_and_nothing_is_saved(error: Exception) -> None:
    use_case, _, repository = build(provider=FakeWeatherProvider(error=error))

    with pytest.raises(type(error)):
        await use_case.execute("Atlantis")

    assert repository.items == []


async def test_history_is_newest_first_and_respects_the_limit() -> None:
    clock = SequenceClock(*(FIXED_NOW + timedelta(minutes=minute) for minute in range(3)))
    use_case, _, repository = build(clock=clock)
    for city in ["Lisbon", "Porto", "Faro"]:
        await use_case.execute(city)

    history = await ListWeatherSearches(repository).execute(limit=2)

    assert [view.city for view in history] == ["Faro", "Porto"]
