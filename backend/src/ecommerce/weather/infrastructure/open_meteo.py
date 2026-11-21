from typing import Any

import httpx

from ecommerce.weather.application.errors import CityNotFound, WeatherUnavailable
from ecommerce.weather.domain.city import City
from ecommerce.weather.domain.weather_search import CurrentWeather, Location

CURRENT_FIELDS = "temperature_2m,wind_speed_10m,weather_code"


class OpenMeteoWeatherProvider:
    def __init__(self, client: httpx.AsyncClient, geocoding_url: str, forecast_url: str) -> None:
        self._client = client
        self._geocoding_url = geocoding_url
        self._forecast_url = forecast_url

    async def current_weather_for(self, city: City) -> tuple[Location, CurrentWeather]:
        try:
            location = await self._locate(city)
            weather = await self._current_weather(location)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise WeatherUnavailable(str(error)) from error
        return location, weather

    async def _locate(self, city: City) -> Location:
        body = await self._get_json(
            self._geocoding_url,
            {"name": city.value, "count": 1, "language": "en", "format": "json"},
        )
        results = body.get("results") or []
        if not results:
            raise CityNotFound(city.value)
        first = results[0]
        return Location(
            name=str(first["name"]),
            country=str(first.get("country", "")),
            latitude=float(first["latitude"]),
            longitude=float(first["longitude"]),
        )

    async def _current_weather(self, location: Location) -> CurrentWeather:
        body = await self._get_json(
            self._forecast_url,
            {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "current": CURRENT_FIELDS,
            },
        )
        current = body["current"]
        return CurrentWeather(
            temperature_c=float(current["temperature_2m"]),
            wind_speed_kmh=float(current["wind_speed_10m"]),
            weather_code=int(current["weather_code"]),
        )

    async def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("Unexpected response from Open-Meteo.")
        return body
