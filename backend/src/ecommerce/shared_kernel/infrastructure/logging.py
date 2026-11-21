import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from ecommerce.shared_kernel.infrastructure.request_context import request_id_var

REQUEST_FIELDS = ("method", "path", "status", "duration_ms")
ACCESS_LOGGER = "uvicorn.access"
SERVER_LOGGERS = ("uvicorn", "uvicorn.error", ACCESS_LOGGER)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None) or request_id_var.get(),
        }
        for name in REQUEST_FIELDS:
            if hasattr(record, name):
                payload[name] = getattr(record, name)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    for name in SERVER_LOGGERS:
        server_logger = logging.getLogger(name)
        server_logger.handlers = []
        server_logger.propagate = name != ACCESS_LOGGER
