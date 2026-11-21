from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WeatherSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str = Field(max_length=1000, examples=["Lisbon"])


class WeatherSearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class ErrorResponse(BaseModel):
    detail: str
