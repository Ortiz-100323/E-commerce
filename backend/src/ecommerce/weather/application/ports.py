from typing import Protocol

from ecommerce.weather.domain.city import City
from ecommerce.weather.domain.weather_search import CurrentWeather, Location


class WeatherProvider(Protocol):
    async def current_weather_for(self, city: City) -> tuple[Location, CurrentWeather]: ...
