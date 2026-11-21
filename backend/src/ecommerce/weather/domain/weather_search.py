from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from ecommerce.weather.domain.city import City


@dataclass(frozen=True)
class Location:
    name: str
    country: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class CurrentWeather:
    temperature_c: float
    wind_speed_kmh: float
    weather_code: int


@dataclass(frozen=True)
class WeatherSearch:
    id: UUID
    query: City
    location: Location
    weather: CurrentWeather
    searched_at: datetime

    @classmethod
    def record(
        cls, query: City, location: Location, weather: CurrentWeather, searched_at: datetime
    ) -> "WeatherSearch":
        return cls(uuid4(), query, location, weather, searched_at)
