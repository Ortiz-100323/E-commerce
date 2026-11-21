from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

PROBLEM_MEDIA_TYPE = "application/problem+json"
PROBLEM_TYPE_PREFIX = "urn:ecommerce:problem:"
REQUEST_ID_HEADER = "X-Request-ID"


@dataclass(frozen=True)
class ProblemType:
    slug: str
    status: int
    title: str

    @property
    def uri(self) -> str:
        return f"{PROBLEM_TYPE_PREFIX}{self.slug}"


@dataclass(frozen=True)
class ProblemMapping:
    problem: ProblemType
    headers: Mapping[str, str] = field(default_factory=dict)
    detail: Callable[[Exception], str] | None = None
    extra: Callable[[Exception], Mapping[str, Any]] | None = None


MALFORMED_REQUEST = ProblemType("malformed-request", 400, "The request body is not valid JSON.")
NOT_FOUND = ProblemType("not-found", 404, "The resource was not found.")
METHOD_NOT_ALLOWED = ProblemType(
    "method-not-allowed", 405, "The method is not allowed for this resource."
)
PAYLOAD_TOO_LARGE = ProblemType("payload-too-large", 413, "The upload is too large.")
UNSUPPORTED_MEDIA_TYPE = ProblemType(
    "unsupported-media-type", 415, "The upload is not in a supported format."
)
VALIDATION_ERROR = ProblemType("validation-error", 422, "The request is not valid.")
INTERNAL_ERROR = ProblemType("internal-error", 500, "An unexpected error occurred.")
UPSTREAM_UNAVAILABLE = ProblemType(
    "upstream-unavailable", 502, "An external service is unavailable."
)
SERVICE_UNAVAILABLE = ProblemType(
    "service-unavailable", 503, "The service is temporarily unavailable."
)

PROBLEMS_BY_STATUS = {
    problem.status: problem
    for problem in (
        MALFORMED_REQUEST,
        NOT_FOUND,
        METHOD_NOT_ALLOWED,
        PAYLOAD_TOO_LARGE,
        UNSUPPORTED_MEDIA_TYPE,
        VALIDATION_ERROR,
        INTERNAL_ERROR,
        UPSTREAM_UNAVAILABLE,
        SERVICE_UNAVAILABLE,
    )
}


def request_id_of(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str):
        return request_id
    generated = str(uuid4())
    request.state.request_id = generated
    return generated


def problem_response(
    request: Request,
    problem: ProblemType,
    *,
    detail: str | None = None,
    extra: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return build_response(
        request,
        type_uri=problem.uri,
        status=problem.status,
        title=problem.title,
        detail=detail,
        extra=extra,
        headers=headers,
    )


def status_problem_response(
    request: Request,
    status: int,
    *,
    detail: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    known = PROBLEMS_BY_STATUS.get(status)
    if known is not None:
        return problem_response(request, known, detail=detail, headers=headers)
    return build_response(
        request,
        type_uri="about:blank",
        status=status,
        title=HTTPStatus(status).phrase,
        detail=detail,
        extra=None,
        headers=headers,
    )


def build_response(
    request: Request,
    *,
    type_uri: str,
    status: int,
    title: str,
    detail: str | None,
    extra: Mapping[str, Any] | None,
    headers: Mapping[str, str] | None,
) -> JSONResponse:
    request_id = request_id_of(request)
    body: dict[str, Any] = {
        "type": type_uri,
        "title": title,
        "status": status,
        "instance": request.url.path,
        "request_id": request_id,
    }
    if detail:
        body["detail"] = detail
    if extra:
        body.update(extra)
    return JSONResponse(
        body,
        status_code=status,
        media_type=PROBLEM_MEDIA_TYPE,
        headers={**(headers or {}), REQUEST_ID_HEADER: request_id},
    )
