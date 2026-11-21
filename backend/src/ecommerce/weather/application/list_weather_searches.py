from ecommerce.weather.application.dto import WeatherSearchView
from ecommerce.weather.domain.repository import WeatherSearchRepository


class ListWeatherSearches:
    def __init__(self, repository: WeatherSearchRepository) -> None:
        self._repository = repository

    async def execute(self, limit: int) -> list[WeatherSearchView]:
        searches = await self._repository.latest(limit)
        return [WeatherSearchView.from_entity(search) for search in searches]
