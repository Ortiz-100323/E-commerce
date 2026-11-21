from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from ecommerce.main import API_PREFIX, create_app
from ecommerce.shared_kernel.api.actor import ACTOR_HEADER, require_actor
from ecommerce.shared_kernel.domain.actor import MAX_ACTOR_LENGTH, Actor
from fakes import dependencies_factory
from problems import assert_problem

CHANGE = f"{API_PREFIX}/test-only/changes"


def app_with_a_change_route() -> FastAPI:
    app = create_app(dependencies_factory())

    async def change(actor: Annotated[Actor, Depends(require_actor)]) -> dict[str, str]:
        return {"actor": actor.name}

    app.add_api_route(CHANGE, change, methods=["POST"])
    return app


def send(headers: dict[str, str] | None = None) -> Any:
    with TestClient(app_with_a_change_route()) as client:
        return client.post(CHANGE, headers=headers or {})


def assert_header_problem(response: Any, code: str) -> dict[str, Any]:
    body = assert_problem(response, 422, "validation-error")
    [error] = body["errors"]
    assert (error["location"], error["field"], error["code"]) == ("header", ACTOR_HEADER, code)
    assert error["message"]
    return dict(error)


def test_a_change_without_the_header_returns_422_required() -> None:
    assert_header_problem(send(), "required")


@pytest.mark.parametrize("value", ["", "   "])
def test_a_blank_name_returns_422_required(value: str) -> None:
    assert_header_problem(send({ACTOR_HEADER: value}), "required")


def test_a_name_over_the_limit_returns_422_too_long() -> None:
    error = assert_header_problem(send({ACTOR_HEADER: "x" * (MAX_ACTOR_LENGTH + 1)}), "too_long")
    assert error["params"] == {"max_length": MAX_ACTOR_LENGTH}


@pytest.mark.parametrize("value", ["Ann%0ASmith", "Ann\tSmith", "Ann%00"])
def test_control_characters_return_422(value: str) -> None:
    assert_header_problem(send({ACTOR_HEADER: value}), "control_characters_not_allowed")


@pytest.mark.parametrize("value", ["%C3", "Jos%E9"])
def test_bad_percent_encoding_returns_422_invalid_encoding(value: str) -> None:
    assert_header_problem(send({ACTOR_HEADER: value}), "invalid_encoding")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Antonio", "Antonio"),
        ("  Maria  ", "Maria"),
        ("Maria%20Silva", "Maria Silva"),
        ("%C5%81ukasz", "Łukasz"),
        ("%E6%9D%8E", "李"),
        ("100% sure", "100% sure"),
    ],
)
def test_a_valid_name_reaches_the_change(value: str, expected: str) -> None:
    response = send({ACTOR_HEADER: value})

    assert response.status_code == 200, response.text
    assert response.json() == {"actor": expected}


def test_the_header_is_documented_on_the_change() -> None:
    openapi = app_with_a_change_route().openapi()
    [parameter] = openapi["paths"][CHANGE]["post"]["parameters"]

    assert (parameter["name"], parameter["in"]) == (ACTOR_HEADER, "header")
    assert "percent-encoded" in parameter["description"]
