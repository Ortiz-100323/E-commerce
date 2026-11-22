from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from ecommerce.main import API_PREFIX, create_app
from ecommerce.ordering.api.router import IDEMPOTENCY_HEADER
from ecommerce.shared_kernel.api.actor import ACTOR_HEADER
from fakes import dependencies_factory

PROBLEM_FIELDS = {"type", "title", "status", "instance", "request_id"}
VALID_ID = "00000000-0000-4000-8000-000000000001"
ACTOR = {ACTOR_HEADER: "Contract Test", IDEMPOTENCY_HEADER: VALID_ID}
CHANGE_METHODS = {"post", "put", "patch", "delete"}
BAD_VALUES = {"integer": "abc", "number": "abc", "boolean": "maybe"}

APP = create_app(dependencies_factory())
OPENAPI = APP.openapi()
COMPONENTS = OPENAPI.get("components", {}).get("schemas", {})


def operations() -> Iterator[tuple[str, str, dict[str, Any]]]:
    for path, item in OPENAPI["paths"].items():
        for method, operation in item.items():
            yield path, method, operation


def resolved(schema: dict[str, Any]) -> dict[str, Any]:
    reference = schema.get("$ref")
    if reference is None:
        return schema
    found: dict[str, Any] = COMPONENTS[reference.rsplit("/", 1)[-1]]
    return found


def non_null(schema: dict[str, Any]) -> dict[str, Any]:
    for option in schema.get("anyOf", []):
        if option.get("type") != "null":
            return resolved(option)
    return resolved(schema)


def bad_value(schema: dict[str, Any]) -> str | None:
    schema = non_null(schema)
    if "enum" in schema:
        return "not-one-of-the-values"
    if "maxLength" in schema:
        return "x" * (schema["maxLength"] + 1)
    if schema.get("format") == "uuid":
        return "not-a-uuid"
    return BAD_VALUES.get(schema.get("type", ""))


def with_path(path: str, operation: dict[str, Any] | None = None) -> str:
    integers = {
        parameter["name"]
        for parameter in (operation or {}).get("parameters", [])
        if parameter["in"] == "path" and non_null(parameter["schema"]).get("type") == "integer"
    }
    for part in path.split("/"):
        if part.startswith("{"):
            path = path.replace(part, "2" if part.strip("{}") in integers else VALID_ID)
    return path


def parameters(operation: dict[str, Any], location: str) -> list[dict[str, Any]]:
    return [item for item in operation.get("parameters", []) if item["in"] == location]


def bad_requests() -> Iterator[Any]:
    for path, method, operation in operations():
        for parameter in parameters(operation, "path"):
            yield pytest.param(
                method,
                path.replace(f"{{{parameter['name']}}}", "not-a-uuid"),
                {"headers": ACTOR},
                422,
                id=f"{method} {path} bad path {parameter['name']}",
            )
        for parameter in parameters(operation, "query"):
            value = bad_value(parameter["schema"])
            if value is not None:
                yield pytest.param(
                    method,
                    with_path(path, operation),
                    {"params": {parameter["name"]: value}, "headers": ACTOR},
                    422,
                    id=f"{method} {path} bad query {parameter['name']}",
                )
        for parameter in parameters(operation, "header"):
            yield pytest.param(
                method,
                with_path(path, operation),
                {"json": {}},
                400 if parameter["name"] == IDEMPOTENCY_HEADER else 422,
                id=f"{method} {path} missing header {parameter['name']}",
            )
        body_types = operation.get("requestBody", {}).get("content", {})
        if "text/csv" in body_types:
            yield pytest.param(
                method,
                with_path(path, operation),
                {"json": {"name": "x"}, "headers": ACTOR},
                415,
                id=f"{method} {path} JSON instead of CSV",
            )
            yield pytest.param(
                method,
                with_path(path, operation),
                {"content": b"", "headers": {**ACTOR, "content-type": "text/csv"}},
                422,
                id=f"{method} {path} empty CSV",
            )
            yield pytest.param(
                method,
                with_path(path, operation),
                {"content": b"\xff\xfe", "headers": {**ACTOR, "content-type": "text/csv"}},
                422,
                id=f"{method} {path} CSV that is not UTF-8",
            )
        if "application/json" in body_types:
            yield pytest.param(
                method,
                with_path(path, operation),
                {
                    "content": b'{"name":',
                    "headers": {**ACTOR, "content-type": "application/json"},
                },
                400,
                id=f"{method} {path} malformed body",
            )
            yield pytest.param(
                method,
                with_path(path, operation),
                {"json": [], "headers": ACTOR},
                422,
                id=f"{method} {path} body of the wrong type",
            )
            yield pytest.param(
                method,
                with_path(path, operation),
                {"json": {}, "headers": ACTOR},
                422,
                id=f"{method} {path} empty body",
            )


def assert_problem_details(response: httpx.Response, status: int) -> None:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert PROBLEM_FIELDS <= body.keys()
    assert body["status"] == status
    assert body["type"].startswith("urn:ecommerce:problem:")
    assert body["request_id"] == response.headers["x-request-id"]
    if status == 422:
        assert body["errors"], body
        for error in body["errors"]:
            assert {"location", "field", "code", "message", "params"} <= error.keys()


@pytest.mark.parametrize(("method", "path", "request_options", "status"), list(bad_requests()))
def test_bad_input_to_every_endpoint_returns_problem_details(
    method: str, path: str, request_options: dict[str, Any], status: int
) -> None:
    with TestClient(APP, raise_server_exceptions=False) as client:
        response = client.request(method.upper(), path, **request_options)

    assert_problem_details(response, status)


def test_every_product_change_requires_the_actor_header() -> None:
    changes = [
        (method, path)
        for path, method, operation in operations()
        if path.startswith(f"{API_PREFIX}/products") and method in CHANGE_METHODS
    ]

    assert len(changes) == 4
    for path, method, operation in operations():
        if (method, path) in changes:
            headers = [
                (parameter["name"], parameter["required"])
                for parameter in parameters(operation, "header")
            ]
            assert headers == [(ACTOR_HEADER, True)], (method, path)


def test_every_import_change_requires_the_actor_header() -> None:
    changes = [
        (method, path)
        for path, method, operation in operations()
        if path.startswith(f"{API_PREFIX}/imports")
        and method in CHANGE_METHODS
        and not path.endswith("/preview")
    ]

    assert len(changes) == 4
    for path, method, operation in operations():
        if (method, path) in changes:
            headers = [
                (parameter["name"], parameter["required"])
                for parameter in parameters(operation, "header")
            ]
            assert headers == [(ACTOR_HEADER, True)], (method, path)


def test_the_contract_covers_every_endpoint_that_takes_input() -> None:
    covered = {(case.values[0], str(case.id).split(" ")[1]) for case in bad_requests()}
    taking_input = {
        (method, path)
        for path, method, operation in operations()
        if operation.get("parameters") or "requestBody" in operation
    }

    assert len(taking_input) == 16
    assert taking_input <= covered


def test_checkout_takes_an_idempotency_key_and_no_actor() -> None:
    checkout = OPENAPI["paths"][f"{API_PREFIX}/orders"]["post"]

    headers = [
        (parameter["name"], parameter["required"]) for parameter in parameters(checkout, "header")
    ]

    assert headers == [(IDEMPOTENCY_HEADER, False)]
