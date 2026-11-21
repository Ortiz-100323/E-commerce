import logging
from collections.abc import Awaitable, Callable, Mapping
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from ecommerce.shared_kernel.api.actor import InvalidHeader
from ecommerce.shared_kernel.api.problem_details import (
    INTERNAL_ERROR,
    MALFORMED_REQUEST,
    NOT_FOUND,
    VALIDATION_ERROR,
    ProblemMapping,
    problem_response,
    request_id_of,
    status_problem_response,
)
from ecommerce.shared_kernel.api.validation import (
    FieldError,
    describe,
    field_error_from_issue,
    field_error_from_pydantic,
)
from ecommerce.shared_kernel.domain.errors import DomainValidationError, NotFoundError

logger = logging.getLogger("ecommerce.errors")

Handler = Callable[[Request, Exception], Awaitable[Response]]


def validation_problem(request: Request, errors: list[FieldError]) -> JSONResponse:
    return problem_response(
        request,
        VALIDATION_ERROR,
        detail=describe(errors),
        extra={"errors": [error.as_dict() for error in errors]},
    )


async def handle_request_validation(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)
    raw_errors = list(exc.errors())
    if any(error.get("type") == "json_invalid" for error in raw_errors):
        return problem_response(request, MALFORMED_REQUEST)
    return validation_problem(request, [field_error_from_pydantic(error) for error in raw_errors])


async def handle_domain_validation(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, DomainValidationError)
    return validation_problem(request, [field_error_from_issue(issue) for issue in exc.issues])


async def handle_invalid_header(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, InvalidHeader)
    return validation_problem(
        request, [field_error_from_issue(issue, location="header") for issue in exc.issues]
    )


async def handle_not_found(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, NotFoundError)
    return problem_response(request, NOT_FOUND, detail=exc.detail)


async def handle_http_exception(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, StarletteHTTPException)
    phrase = HTTPStatus(exc.status_code).phrase
    detail = exc.detail if isinstance(exc.detail, str) and exc.detail != phrase else None
    return status_problem_response(
        request, exc.status_code, detail=detail, headers=exc.headers or None
    )


async def handle_unexpected(request: Request, exc: Exception) -> Response:
    request_id = request_id_of(request)
    logger.error(
        "unhandled error",
        exc_info=(type(exc), exc, exc.__traceback__),
        extra={"request_id": request_id, "path": request.url.path},
    )
    return problem_response(request, INTERNAL_ERROR)


def mapped_handler(mapping: ProblemMapping) -> Handler:
    async def handle(request: Request, exc: Exception) -> Response:
        return problem_response(request, mapping.problem, headers=mapping.headers)

    return handle


def install_problem_handlers(
    app: FastAPI, mappings: Mapping[type[Exception], ProblemMapping]
) -> None:
    app.add_exception_handler(RequestValidationError, handle_request_validation)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(DomainValidationError, handle_domain_validation)
    app.add_exception_handler(InvalidHeader, handle_invalid_header)
    app.add_exception_handler(NotFoundError, handle_not_found)
    for exception_type, mapping in mappings.items():
        app.add_exception_handler(exception_type, mapped_handler(mapping))
    app.add_exception_handler(Exception, handle_unexpected)
