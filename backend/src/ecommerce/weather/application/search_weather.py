from ecommerce.shared_kernel.application.ports import Clock
from ecommerce.weather.application.dto import WeatherSearchView
from ecommerce.weather.application.ports import WeatherProvider
from ecommerce.weather.domain.city import City
from ecommerce.weather.domain.repository import WeatherSearchRepository
from ecommerce.weather.domain.weather_search import WeatherSearch


class SearchWeather:
    def __init__(
        self, provider: WeatherProvider, repository: WeatherSearchRepository, clock: Clock
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._clock = clock

    async def execute(self, city_name: str) -> WeatherSearchView:
        city = City(city_name)
        location, weather = await self._provider.current_weather_for(city)
        search = WeatherSearch.record(city, location, weather, self._clock.now())
        await self._repository.add(search)
        return WeatherSearchView.from_entity(search)
