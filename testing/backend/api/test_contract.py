from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from identity_fakes import ANTONIO_TOKEN, BEA_TOKEN

from ecommerce.main import API_PREFIX, create_app
from ecommerce.ordering.api.router import IDEMPOTENCY_HEADER
from ecommerce.shared_kernel.api.access import SESSION_COOKIE
from fakes import dependencies_factory

PROBLEM_FIELDS = {"type", "title", "status", "instance", "request_id"}
VALID_ID = "00000000-0000-4000-8000-000000000001"
ACTOR = {"Cookie": f"{SESSION_COOKIE}={ANTONIO_TOKEN}", IDEMPOTENCY_HEADER: VALID_ID}
BUYER = {"Cookie": f"{SESSION_COOKIE}={BEA_TOKEN}"}
OLD_ACTOR_HEADER = "X-Actor-Name"
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


def headers_for(path: str) -> dict[str, str]:
    return BUYER if path.startswith(f"{API_PREFIX}/me/") else ACTOR


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
                    {"params": {parameter["name"]: value}, "headers": headers_for(path)},
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


def is_admin_operation(path: str, method: str) -> bool:
    return (
        (path.startswith(f"{API_PREFIX}/products") and method in CHANGE_METHODS)
        or path.endswith("/history")
        or path.startswith(f"{API_PREFIX}/imports")
        or path.startswith(f"{API_PREFIX}/admin/")
    )


def test_every_admin_endpoint_declares_the_session_and_its_401_and_403() -> None:
    admin = [(method, path) for path, method, _ in operations() if is_admin_operation(path, method)]

    assert len(admin) == 15
    for path, method, operation in operations():
        if (method, path) in admin:
            assert {"session": []} in operation.get("security", []), (method, path)
            assert {"401", "403"} <= set(operation["responses"]), (method, path)


def test_no_endpoint_accepts_the_old_typed_name_header() -> None:
    for path, method, operation in operations():
        names = [parameter["name"] for parameter in parameters(operation, "header")]
        assert OLD_ACTOR_HEADER not in names, (method, path)


def test_the_contract_covers_every_endpoint_that_takes_input() -> None:
    covered = {(case.values[0], str(case.id).split(" ")[1]) for case in bad_requests()}
    taking_input = {
        (method, path)
        for path, method, operation in operations()
        if operation.get("parameters") or "requestBody" in operation
    }

    assert len(taking_input) == 22
    assert taking_input <= covered


def test_checkout_takes_an_idempotency_key_and_no_actor() -> None:
    checkout = OPENAPI["paths"][f"{API_PREFIX}/orders"]["post"]

    headers = [
        (parameter["name"], parameter["required"]) for parameter in parameters(checkout, "header")
    ]

    assert headers == [(IDEMPOTENCY_HEADER, False)]


def schema_properties(schema: dict[str, Any]) -> set[str]:
    found = resolved(schema)
    names = set(found.get("properties", {}))
    for nested in found.get("properties", {}).values():
        names |= schema_properties(non_null(nested))
    for option in found.get("anyOf", []) + found.get("allOf", []):
        names |= schema_properties(option)
    return names


def test_no_request_anywhere_accepts_a_role() -> None:
    for path, method, operation in operations():
        content = operation.get("requestBody", {}).get("content", {})
        for media in content.values():
            names = schema_properties(media.get("schema", {}))
            assert not {"role", "roles", "is_admin"} & names, (method, path)


def test_only_create_admin_can_make_an_administrator() -> None:
    makers = [
        (method, path)
        for path, method, operation in operations()
        if operation.get("summary", "").startswith("Create")
        and "administrator" in operation["summary"]
    ]

    assert makers == [("post", f"{API_PREFIX}/admin/accounts")]
    sign_up = OPENAPI["paths"][f"{API_PREFIX}/accounts"]["post"]
    assert "never creates an administrator" in sign_up["summary"]
