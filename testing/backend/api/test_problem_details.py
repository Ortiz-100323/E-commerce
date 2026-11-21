import logging
from typing import Annotated

import pytest
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import OperationalError

from ecommerce.main import create_app
from ecommerce.shared_kernel.domain.errors import (
    DomainValidationError,
    NotFoundError,
    ValidationIssue,
)
from fakes import dependencies_factory
from problems import assert_problem, problem_client

SIGNUPS = "/test/signups"


class Line(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: int = Field(ge=1)


class Order(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lines: list[Line]


class Signup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(max_length=10)


def app_with_test_routes() -> FastAPI:
    app = create_app(dependencies_factory())

    async def create_order(order: Order) -> dict[str, int]:
        return {"lines": len(order.lines)}

    async def sign_up(signup: Signup) -> dict[str, str]:
        if not signup.name.strip():
            raise DomainValidationError([ValidationIssue("name", "required", "Type a name.")])
        return {"name": signup.name}

    async def list_items(limit: Annotated[int, Query(ge=1)] = 10) -> dict[str, int]:
        return {"limit": limit}

    async def explode() -> None:
        raise RuntimeError("secret internals")

    async def database_down() -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    async def missing() -> None:
        raise NotFoundError()

    async def missing_with_detail() -> None:
        raise NotFoundError("Order not found.")

    async def upstream_down() -> None:
        raise HTTPException(status_code=502)

    async def domain_invalid() -> None:
        raise DomainValidationError(
            [
                ValidationIssue("name", "required", "Type a name."),
                ValidationIssue("price", "too_small", "Too small.", params={"min": 0}),
            ]
        )

    app.add_api_route("/test/orders", create_order, methods=["POST"])
    app.add_api_route(SIGNUPS, sign_up, methods=["POST"])
    app.add_api_route("/test/items", list_items)
    app.add_api_route("/test/explode", explode)
    app.add_api_route("/test/database-down", database_down)
    app.add_api_route("/test/missing", missing)
    app.add_api_route("/test/missing-with-detail", missing_with_detail)
    app.add_api_route("/test/upstream-down", upstream_down)
    app.add_api_route("/test/domain-invalid", domain_invalid)
    return app


def test_unknown_route_is_a_not_found_problem() -> None:
    with problem_client() as client:
        response = client.get("/api/v1/nowhere")

    assert_problem(response, 404, "not-found")


def test_wrong_method_is_a_method_not_allowed_problem() -> None:
    with problem_client() as client:
        response = client.delete("/api/v1/health")

    assert_problem(response, 405, "method-not-allowed")
    assert "GET" in response.headers["allow"]


def test_broken_json_is_a_malformed_request() -> None:
    with problem_client(app_with_test_routes()) as client:
        response = client.post(
            SIGNUPS, content=b'{"name":', headers={"Content-Type": "application/json"}
        )

    body = assert_problem(response, 400, "malformed-request")
    assert "errors" not in body


def test_missing_field_is_a_validation_error_with_field_errors() -> None:
    with problem_client(app_with_test_routes()) as client:
        response = client.post(SIGNUPS, json={})

    body = assert_problem(response, 422, "validation-error")
    assert body["detail"] == "1 field is not valid."
    assert body["errors"] == [
        {
            "location": "body",
            "field": "name",
            "code": "required",
            "message": "Field required",
            "params": {},
        }
    ]


@pytest.mark.parametrize(
    ("payload", "field", "code"),
    [
        ({"name": 5}, "name", "not_a_string"),
        ({"name": "Ann", "country": "PT"}, "country", "unknown_field"),
        ({"name": "x" * 11}, "name", "too_long"),
    ],
)
def test_schema_errors_use_stable_codes(payload: object, field: str, code: str) -> None:
    with problem_client(app_with_test_routes()) as client:
        response = client.post(SIGNUPS, json=payload)

    body = assert_problem(response, 422, "validation-error")
    assert [(error["field"], error["code"]) for error in body["errors"]] == [(field, code)]


def test_query_errors_point_at_the_query_parameter() -> None:
    with problem_client(app_with_test_routes()) as client:
        response = client.get("/test/items", params={"limit": 0})

    body = assert_problem(response, 422, "validation-error")
    assert body["errors"][0]["location"] == "query"
    assert body["errors"][0]["field"] == "limit"
    assert body["errors"][0]["code"] == "too_small"
    assert body["errors"][0]["params"] == {"ge": 1}


def test_nested_fields_use_dotted_paths_with_indexes() -> None:
    with problem_client(app_with_test_routes()) as client:
        response = client.post("/test/orders", json={"lines": [{"quantity": 1}, {"quantity": 0}]})

    body = assert_problem(response, 422, "validation-error")
    assert body["errors"][0]["field"] == "lines[1].quantity"


def test_every_validation_issue_is_reported_at_once() -> None:
    with problem_client(app_with_test_routes()) as client:
        response = client.get("/test/domain-invalid")

    body = assert_problem(response, 422, "validation-error")
    assert body["detail"] == "2 fields are not valid."
    assert [(error["field"], error["code"]) for error in body["errors"]] == [
        ("name", "required"),
        ("price", "too_small"),
    ]
    assert body["errors"][1]["params"] == {"min": 0}


def test_domain_rule_errors_share_the_validation_format() -> None:
    with problem_client(app_with_test_routes()) as client:
        response = client.post(SIGNUPS, json={"name": "   "})

    body = assert_problem(response, 422, "validation-error")
    assert body["errors"][0]["location"] == "body"
    assert body["errors"][0]["field"] == "name"
    assert body["errors"][0]["code"] == "required"


def test_not_found_errors_from_the_domain_are_not_found_problems() -> None:
    with problem_client(app_with_test_routes()) as client:
        response = client.get("/test/missing-with-detail")

    body = assert_problem(response, 404, "not-found")
    assert body["detail"] == "Order not found."


def test_not_found_without_detail_omits_it() -> None:
    with problem_client(app_with_test_routes()) as client:
        response = client.get("/test/missing")

    body = assert_problem(response, 404, "not-found")
    assert "detail" not in body


def test_upstream_failure_is_an_upstream_unavailable_problem() -> None:
    with problem_client(app_with_test_routes()) as client:
        response = client.get("/test/upstream-down")

    assert_problem(response, 502, "upstream-unavailable")


def test_database_outage_is_a_service_unavailable_problem() -> None:
    with problem_client(app_with_test_routes()) as client:
        response = client.get("/test/database-down")

    body = assert_problem(response, 503, "service-unavailable")
    assert response.headers["retry-after"] == "1"
    assert "connection refused" not in response.text
    assert "detail" not in body


def test_unexpected_errors_are_internal_problems_without_internals(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR)
    with problem_client(app_with_test_routes()) as client:
        response = client.get("/test/explode")

    body = assert_problem(response, 500, "internal-error")
    assert "secret internals" not in response.text
    assert "detail" not in body
    logged = [record for record in caplog.records if getattr(record, "request_id", None)]
    assert any(record.request_id == body["request_id"] for record in logged)
