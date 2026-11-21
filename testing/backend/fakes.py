from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, datetime

from ecommerce.main import Dependencies
from ecommerce.weather.domain.city import City
from ecommerce.weather.domain.weather_search import CurrentWeather, Location, WeatherSearch

LISBON = Location(name="Lisbon", country="Portugal", latitude=38.71667, longitude=-9.13333)
SUNNY = CurrentWeather(temperature_c=21.4, wind_speed_kmh=12.6, weather_code=0)
FIXED_NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


class FakeWeatherProvider:
    def __init__(
        self,
        location: Location = LISBON,
        weather: CurrentWeather = SUNNY,
        error: Exception | None = None,
    ) -> None:
        self.location = location
        self.weather = weather
        self.error = error
        self.calls: list[str] = []

    async def current_weather_for(self, city: City) -> tuple[Location, CurrentWeather]:
        self.calls.append(city.value)
        if self.error is not None:
            raise self.error
        return self.location, self.weather


class InMemoryWeatherSearchRepository:
    def __init__(self) -> None:
        self.items: list[WeatherSearch] = []

    async def add(self, search: WeatherSearch) -> None:
        self.items.append(search)

    async def latest(self, limit: int) -> list[WeatherSearch]:
        ordered = sorted(self.items, key=lambda search: search.searched_at, reverse=True)
        return ordered[:limit]


class FakeDatabaseProbe:
    def __init__(self, up: bool) -> None:
        self.up = up

    async def is_up(self) -> bool:
        return self.up


class SequenceClock:
    def __init__(self, *moments: datetime) -> None:
        self.moments = list(moments) or [FIXED_NOW]
        self.index = 0

    def now(self) -> datetime:
        moment = self.moments[min(self.index, len(self.moments) - 1)]
        self.index += 1
        return moment


def dependencies_factory(
    *,
    provider: FakeWeatherProvider | None = None,
    repository: InMemoryWeatherSearchRepository | None = None,
    database_up: bool = True,
    clock: SequenceClock | None = None,
) -> Callable[[], AbstractAsyncContextManager[Dependencies]]:
    dependencies = Dependencies(
        weather_provider=provider or FakeWeatherProvider(),
        weather_repository=repository or InMemoryWeatherSearchRepository(),
        database_probe=FakeDatabaseProbe(database_up),
        clock=clock or SequenceClock(),
    )

    @asynccontextmanager
    async def factory() -> AsyncIterator[Dependencies]:
        yield dependencies

    return factory
