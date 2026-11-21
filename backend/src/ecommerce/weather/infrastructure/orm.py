from sqlalchemy import Column, DateTime, Double, Integer, String, Table, Uuid

from ecommerce.shared_kernel.infrastructure.database import metadata

weather_searches = Table(
    "weather_searches",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("query", String(100), nullable=False),
    Column("location_name", String(200), nullable=False),
    Column("country", String(100), nullable=False),
    Column("latitude", Double, nullable=False),
    Column("longitude", Double, nullable=False),
    Column("temperature_c", Double, nullable=False),
    Column("wind_speed_kmh", Double, nullable=False),
    Column("weather_code", Integer, nullable=False),
    Column("searched_at", DateTime(timezone=True), nullable=False, index=True),
)
