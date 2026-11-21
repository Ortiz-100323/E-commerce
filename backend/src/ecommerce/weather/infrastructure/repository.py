from sqlalchemy import RowMapping, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.weather.domain.city import City
from ecommerce.weather.domain.weather_search import CurrentWeather, Location, WeatherSearch
from ecommerce.weather.infrastructure.orm import weather_searches


class SqlAlchemyWeatherSearchRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def add(self, search: WeatherSearch) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                insert(weather_searches).values(
                    id=search.id,
                    query=search.query.value,
                    location_name=search.location.name,
                    country=search.location.country,
                    latitude=search.location.latitude,
                    longitude=search.location.longitude,
                    temperature_c=search.weather.temperature_c,
                    wind_speed_kmh=search.weather.wind_speed_kmh,
                    weather_code=search.weather.weather_code,
                    searched_at=search.searched_at,
                )
            )

    async def latest(self, limit: int) -> list[WeatherSearch]:
        statement = (
            select(weather_searches).order_by(weather_searches.c.searched_at.desc()).limit(limit)
        )
        async with self._engine.connect() as connection:
            result = await connection.execute(statement)
            return [to_entity(row) for row in result.mappings()]


def to_entity(row: RowMapping) -> WeatherSearch:
    return WeatherSearch(
        id=row["id"],
        query=City(row["query"]),
        location=Location(
            name=row["location_name"],
            country=row["country"],
            latitude=row["latitude"],
            longitude=row["longitude"],
        ),
        weather=CurrentWeather(
            temperature_c=row["temperature_c"],
            wind_speed_kmh=row["wind_speed_kmh"],
            weather_code=row["weather_code"],
        ),
        searched_at=row["searched_at"],
    )
