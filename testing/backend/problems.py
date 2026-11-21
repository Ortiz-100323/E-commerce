from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ecommerce.main import create_app
from fakes import dependencies_factory

PROBLEM_PREFIX = "urn:ecommerce:problem:"


def problem_client(app: FastAPI | None = None) -> TestClient:
    application = app or create_app(dependencies_factory())
    return TestClient(application, raise_server_exceptions=False)


def assert_problem(response: httpx.Response, status: int, slug: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body: dict[str, Any] = response.json()
    assert body["type"] == f"{PROBLEM_PREFIX}{slug}"
    assert body["status"] == status
    assert isinstance(body["title"], str) and body["title"]
    assert body["request_id"] == response.headers["x-request-id"]
    assert body["instance"] == response.request.url.path
    return body
