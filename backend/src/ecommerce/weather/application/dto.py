from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ecommerce.weather.domain.weather_search import WeatherSearch


@dataclass(frozen=True)
class WeatherSearchView:
    id: UUID
    city: str
    location_name: str
    country: str
    latitude: float
    longitude: float
    temperature_c: float
    wind_speed_kmh: float
    weather_code: int
    searched_at: datetime

    @classmethod
    def from_entity(cls, search: WeatherSearch) -> "WeatherSearchView":
        return cls(
            id=search.id,
            city=search.query.value,
            location_name=search.location.name,
            country=search.location.country,
            latitude=search.location.latitude,
            longitude=search.location.longitude,
            temperature_c=search.weather.temperature_c,
            wind_speed_kmh=search.weather.wind_speed_kmh,
            weather_code=search.weather.weather_code,
            searched_at=search.searched_at,
        )
