import json
import logging
import sys

from ecommerce.shared_kernel.infrastructure.logging import JsonFormatter, configure_logging
from ecommerce.shared_kernel.infrastructure.request_context import request_id_var


def record(**extra: object) -> logging.LogRecord:
    log_record = logging.LogRecord(
        "ecommerce.test", logging.INFO, __file__, 1, "hello %s", ("you",), None
    )
    for key, value in extra.items():
        setattr(log_record, key, value)
    return log_record


def test_log_line_is_json_with_the_current_request_id() -> None:
    token = request_id_var.set("req-123")
    try:
        line = json.loads(JsonFormatter().format(record()))
    finally:
        request_id_var.reset(token)

    assert line["level"] == "INFO"
    assert line["logger"] == "ecommerce.test"
    assert line["message"] == "hello you"
    assert line["request_id"] == "req-123"
    assert "time" in line


def test_explicit_request_id_and_request_fields_are_included() -> None:
    line = json.loads(
        JsonFormatter().format(
            record(request_id="req-9", method="GET", path="/x", status=200, duration_ms=1.5)
        )
    )

    assert line["request_id"] == "req-9"
    assert (line["method"], line["path"], line["status"], line["duration_ms"]) == (
        "GET",
        "/x",
        200,
        1.5,
    )


def test_exceptions_are_included_as_text() -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        failing = record()
        failing.exc_info = sys.exc_info()

    line = json.loads(JsonFormatter().format(failing))

    assert "RuntimeError: boom" in line["exception"]


def test_configure_logging_writes_json_and_silences_the_duplicate_access_log() -> None:
    names = ["", "uvicorn", "uvicorn.error", "uvicorn.access"]
    saved = {
        name: (
            logging.getLogger(name).handlers[:],
            logging.getLogger(name).propagate,
            logging.getLogger(name).level,
        )
        for name in names
    }
    try:
        configure_logging("WARNING")

        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JsonFormatter)
        assert root.level == logging.WARNING
        assert logging.getLogger("uvicorn.error").handlers == []
        assert logging.getLogger("uvicorn.error").propagate is True
        assert logging.getLogger("uvicorn.access").handlers == []
        assert logging.getLogger("uvicorn.access").propagate is False
    finally:
        for name, (handlers, propagate, level) in saved.items():
            logger = logging.getLogger(name)
            logger.handlers = handlers
            logger.propagate = propagate
            logger.setLevel(level)


def test_request_id_is_null_outside_a_request() -> None:
    assert json.loads(JsonFormatter().format(record()))["request_id"] is None
