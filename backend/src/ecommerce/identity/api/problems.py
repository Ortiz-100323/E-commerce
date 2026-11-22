from collections.abc import Mapping

from fastapi import Request
from fastapi.responses import Response

from ecommerce.identity.domain.errors import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    TooManyLoginAttempts,
)
from ecommerce.shared_kernel.api.problem_details import (
    ProblemMapping,
    ProblemType,
    problem_response,
)

INVALID_CREDENTIALS = ProblemType("invalid-credentials", 401, "The email or password is incorrect.")
TOO_MANY_LOGIN_ATTEMPTS = ProblemType(
    "too-many-login-attempts", 429, "Too many attempts. Wait a few minutes and try again."
)
EMAIL_ALREADY_REGISTERED = ProblemType(
    "email-already-registered", 409, "An account with this email already exists. Log in instead."
)

IDENTITY_PROBLEMS: Mapping[type[Exception], ProblemMapping] = {
    InvalidCredentials: ProblemMapping(INVALID_CREDENTIALS),
    EmailAlreadyRegistered: ProblemMapping(EMAIL_ALREADY_REGISTERED),
}


async def handle_too_many_login_attempts(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, TooManyLoginAttempts)
    minutes = max(1, -(-exc.retry_after_seconds // 60))
    return problem_response(
        request,
        TOO_MANY_LOGIN_ATTEMPTS,
        detail=f"Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
        extra={"retry_after_seconds": exc.retry_after_seconds},
        headers={"Retry-After": str(exc.retry_after_seconds)},
    )
