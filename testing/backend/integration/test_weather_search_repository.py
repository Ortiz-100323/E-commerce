from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.weather.domain.city import City
from ecommerce.weather.domain.weather_search import WeatherSearch
from ecommerce.weather.infrastructure.repository import SqlAlchemyWeatherSearchRepository
from fakes import FIXED_NOW, LISBON, SUNNY


def search_at(city: str, minutes: int) -> WeatherSearch:
    return WeatherSearch.record(City(city), LISBON, SUNNY, FIXED_NOW + timedelta(minutes=minutes))


async def test_saved_search_round_trips_with_every_field(engine: AsyncEngine) -> None:
    repository = SqlAlchemyWeatherSearchRepository(engine)
    search = search_at("Lisbon", 0)

    await repository.add(search)

    assert await repository.latest(10) == [search]


async def test_latest_returns_newest_first_up_to_the_limit(engine: AsyncEngine) -> None:
    repository = SqlAlchemyWeatherSearchRepository(engine)
    for minutes, city in enumerate(["Lisbon", "Porto", "Faro"]):
        await repository.add(search_at(city, minutes))

    latest = await repository.latest(2)

    assert [search.query.value for search in latest] == ["Faro", "Porto"]
