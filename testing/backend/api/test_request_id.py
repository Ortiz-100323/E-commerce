import logging
import uuid

import pytest

from problems import problem_client


def test_every_response_carries_a_generated_request_id() -> None:
    with problem_client() as client:
        first = client.get("/api/v1/health")
        second = client.get("/api/v1/health")

    assert uuid.UUID(first.headers["x-request-id"])
    assert first.headers["x-request-id"] != second.headers["x-request-id"]


def test_a_valid_incoming_request_id_is_kept() -> None:
    with problem_client() as client:
        response = client.get("/api/v1/health", headers={"X-Request-ID": "trace-0001-abcd"})

    assert response.headers["x-request-id"] == "trace-0001-abcd"


@pytest.mark.parametrize("incoming", ["bad id!", "x" * 65, "short", "<script>"])
def test_an_unsafe_incoming_request_id_is_replaced(incoming: str) -> None:
    with problem_client() as client:
        response = client.get("/api/v1/health", headers={"X-Request-ID": incoming})

    assert response.headers["x-request-id"] != incoming
    assert uuid.UUID(response.headers["x-request-id"])


def test_the_request_log_line_has_the_same_request_id(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="ecommerce.request")
    with problem_client() as client:
        response = client.get("/api/v1/health", params={"token": "should-not-be-logged"})

    records = [record for record in caplog.records if record.name == "ecommerce.request"]
    assert len(records) == 1
    line = records[0]
    assert line.request_id == response.headers["x-request-id"]
    assert (line.method, line.path, line.status) == ("GET", "/api/v1/health", 200)
    assert line.duration_ms >= 0
    assert "should-not-be-logged" not in caplog.text


def test_error_responses_also_carry_the_request_id() -> None:
    with problem_client() as client:
        response = client.get("/api/v1/nowhere")

    assert response.json()["request_id"] == response.headers["x-request-id"]
