from collections.abc import Callable

import httpx
import pytest

from ecommerce.weather.application.errors import CityNotFound, WeatherUnavailable
from ecommerce.weather.domain.city import City
from ecommerce.weather.infrastructure.open_meteo import OpenMeteoWeatherProvider

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

GEOCODING_BODY = {
    "results": [
        {"name": "Lisbon", "country": "Portugal", "latitude": 38.71667, "longitude": -9.13333}
    ]
}
FORECAST_BODY = {
    "current": {
        "time": "2026-11-21T12:00",
        "temperature_2m": 18.3,
        "wind_speed_10m": 9.7,
        "weather_code": 3,
    }
}

Handler = Callable[[httpx.Request], httpx.Response]


def open_meteo(geocoding: Handler, forecast: Handler) -> tuple[Handler, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "geocoding-api.open-meteo.com":
            return geocoding(request)
        return forecast(request)

    return handler, requests


def provider_for(handler: Handler) -> OpenMeteoWeatherProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenMeteoWeatherProvider(client, GEOCODING_URL, FORECAST_URL)


def ok(body: object) -> Handler:
    return lambda request: httpx.Response(200, json=body)


async def test_maps_geocoding_and_forecast_responses() -> None:
    handler, requests = open_meteo(ok(GEOCODING_BODY), ok(FORECAST_BODY))

    location, weather = await provider_for(handler).current_weather_for(City("Lisbon"))

    assert (location.name, location.country) == ("Lisbon", "Portugal")
    assert (location.latitude, location.longitude) == (38.71667, -9.13333)
    assert (weather.temperature_c, weather.wind_speed_kmh, weather.weather_code) == (18.3, 9.7, 3)
    geocoding_request, forecast_request = requests
    assert geocoding_request.url.params["name"] == "Lisbon"
    assert geocoding_request.url.params["count"] == "1"
    assert forecast_request.url.params["latitude"] == "38.71667"
    assert forecast_request.url.params["longitude"] == "-9.13333"
    assert set(forecast_request.url.params["current"].split(",")) == {
        "temperature_2m",
        "wind_speed_10m",
        "weather_code",
    }


@pytest.mark.parametrize("body", [{}, {"results": []}])
async def test_unknown_city_raises_city_not_found(body: object) -> None:
    handler, requests = open_meteo(ok(body), ok(FORECAST_BODY))

    with pytest.raises(CityNotFound):
        await provider_for(handler).current_weather_for(City("Atlantis"))

    assert len(requests) == 1


def server_error(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, json={"error": True})


def timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("timed out", request=request)


@pytest.mark.parametrize(
    ("geocoding", "forecast"),
    [
        (server_error, ok(FORECAST_BODY)),
        (ok(GEOCODING_BODY), server_error),
        (timeout, ok(FORECAST_BODY)),
        (ok(GEOCODING_BODY), timeout),
        (ok(GEOCODING_BODY), ok({"unexpected": "shape"})),
        (ok({"results": [{"name": "Lisbon"}]}), ok(FORECAST_BODY)),
    ],
    ids=[
        "geocoding-500",
        "forecast-500",
        "geocoding-timeout",
        "forecast-timeout",
        "forecast-malformed",
        "geocoding-malformed",
    ],
)
async def test_upstream_failures_raise_weather_unavailable(
    geocoding: Handler, forecast: Handler
) -> None:
    handler, _ = open_meteo(geocoding, forecast)

    with pytest.raises(WeatherUnavailable):
        await provider_for(handler).current_weather_for(City("Lisbon"))
