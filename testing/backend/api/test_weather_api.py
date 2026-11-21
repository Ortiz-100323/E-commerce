from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from ecommerce.main import create_app
from ecommerce.weather.application.errors import CityNotFound, WeatherUnavailable
from fakes import FIXED_NOW, FakeWeatherProvider, SequenceClock, dependencies_factory

SEARCHES = "/api/v1/weather/searches"


def client_with(
    provider: FakeWeatherProvider | None = None, clock: SequenceClock | None = None
) -> TestClient:
    return TestClient(create_app(dependencies_factory(provider=provider, clock=clock)))


def test_search_returns_201_with_the_saved_search() -> None:
    with client_with() as client:
        response = client.post(SEARCHES, json={"city": "Lisbon"})

    assert response.status_code == 201
    body = response.json()
    assert body["city"] == "Lisbon"
    assert body["location_name"] == "Lisbon"
    assert body["country"] == "Portugal"
    assert body["temperature_c"] == 21.4
    assert body["wind_speed_kmh"] == 12.6
    assert body["weather_code"] == 0
    assert body["searched_at"].startswith("2026-11-21T12:00:00")
    assert set(body) == {
        "id",
        "city",
        "location_name",
        "country",
        "latitude",
        "longitude",
        "temperature_c",
        "wind_speed_kmh",
        "weather_code",
        "searched_at",
    }


def test_history_lists_searches_newest_first_with_a_limit() -> None:
    clock = SequenceClock(*(FIXED_NOW + timedelta(minutes=minute) for minute in range(3)))
    with client_with(clock=clock) as client:
        for city in ["Lisbon", "Porto", "Faro"]:
            client.post(SEARCHES, json={"city": city})
        response = client.get(SEARCHES, params={"limit": 2})

    assert response.status_code == 200
    assert [item["city"] for item in response.json()] == ["Faro", "Porto"]


def test_history_is_empty_at_first() -> None:
    with client_with() as client:
        response = client.get(SEARCHES)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("limit", [0, 51, "abc"])
def test_history_rejects_an_invalid_limit(limit: object) -> None:
    with client_with() as client:
        response = client.get(SEARCHES, params={"limit": limit})

    assert response.status_code == 422


def test_unknown_city_returns_404() -> None:
    with client_with(FakeWeatherProvider(error=CityNotFound("Atlantis"))) as client:
        response = client.post(SEARCHES, json={"city": "Atlantis"})

    assert response.status_code == 404
    assert response.json() == {"detail": "City not found."}


def test_upstream_failure_returns_502() -> None:
    with client_with(FakeWeatherProvider(error=WeatherUnavailable("down"))) as client:
        response = client.post(SEARCHES, json={"city": "Lisbon"})

    assert response.status_code == 502
    assert response.json() == {"detail": "The weather service is unavailable. Try again later."}


@pytest.mark.parametrize("payload", [{"city": "   "}, {"city": "a" * 101}, {}, {"city": 5}])
def test_invalid_city_returns_422(payload: object) -> None:
    with client_with() as client:
        response = client.post(SEARCHES, json=payload)

    assert response.status_code == 422
