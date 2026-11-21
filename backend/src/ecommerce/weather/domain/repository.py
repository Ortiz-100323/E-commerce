from typing import Protocol

from ecommerce.weather.domain.weather_search import WeatherSearch


class WeatherSearchRepository(Protocol):
    async def add(self, search: WeatherSearch) -> None: ...

    async def latest(self, limit: int) -> list[WeatherSearch]: ...
