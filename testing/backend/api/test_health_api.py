from fastapi.testclient import TestClient

from ecommerce.main import create_app
from fakes import dependencies_factory


def test_health_is_ok_when_the_database_is_up() -> None:
    with TestClient(create_app(dependencies_factory(database_up=True))) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


def test_health_is_503_when_the_database_is_down() -> None:
    with TestClient(create_app(dependencies_factory(database_up=False))) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "down"}


def test_health_is_documented_in_swagger() -> None:
    with TestClient(create_app(dependencies_factory())) as client:
        paths = client.get("/openapi.json").json()["paths"]
        docs = client.get("/docs")

    assert "/api/v1/health" in paths
    assert docs.status_code == 200
