from collections.abc import Mapping
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie

from ecommerce.shared_kernel.api.problem_details import ProblemMapping, ProblemType
from ecommerce.shared_kernel.application.ports import Authenticator
from ecommerce.shared_kernel.domain.actor import Actor
from ecommerce.shared_kernel.domain.principal import (
    AdminRequired,
    AuthenticationRequired,
    BuyerRequired,
    Principal,
)

SESSION_COOKIE = "session"

session_cookie = APIKeyCookie(
    name=SESSION_COOKIE,
    auto_error=False,
    scheme_name="session",
    description="Set by `POST /api/v1/session` when you log in.",
)

AUTHENTICATION_REQUIRED = ProblemType("authentication-required", 401, "Log in to continue.")
ADMIN_REQUIRED = ProblemType("admin-required", 403, "This is for administrators only.")
BUYER_REQUIRED = ProblemType("buyer-required", 403, "This is for customer accounts only.")

CLEARED_SESSION_COOKIE = f"{SESSION_COOKIE}=; Max-Age=0; Path=/api; HttpOnly; SameSite=Strict"

ACCESS_PROBLEMS: Mapping[type[Exception], ProblemMapping] = {
    AuthenticationRequired: ProblemMapping(
        AUTHENTICATION_REQUIRED,
        headers={
            "WWW-Authenticate": f'Cookie name="{SESSION_COOKIE}"',
            "Set-Cookie": CLEARED_SESSION_COOKIE,
        },
    ),
    AdminRequired: ProblemMapping(ADMIN_REQUIRED),
    BuyerRequired: ProblemMapping(BUYER_REQUIRED),
}

SessionToken = Annotated[str | None, Depends(session_cookie)]


async def principal_of(request: Request, token: str | None) -> Principal | None:
    if not token:
        return None
    authenticator: Authenticator = request.app.state.authenticator
    principal = await authenticator.authenticate(token)
    if principal is None:
        raise AuthenticationRequired()
    return principal


async def admin_of(request: Request, token: str | None) -> Principal:
    principal = await principal_of(request, token)
    if principal is None:
        raise AuthenticationRequired()
    if not principal.is_admin:
        raise AdminRequired()
    return principal


async def optional_principal(request: Request, token: SessionToken) -> Principal | None:
    return await principal_of(request, token)


async def require_principal(request: Request, token: SessionToken) -> Principal:
    principal = await principal_of(request, token)
    if principal is None:
        raise AuthenticationRequired()
    return principal


async def require_admin(request: Request, token: SessionToken) -> Principal:
    return await admin_of(request, token)


async def require_buyer(
    principal: Annotated[Principal, Depends(require_principal)],
) -> Principal:
    if not principal.is_buyer:
        raise BuyerRequired()
    return principal


async def require_actor(admin: Annotated[Principal, Depends(require_admin)]) -> Actor:
    return admin.actor()


ADMIN_ONLY_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Not logged in, or the session has ended (`authentication-required`)."},
    403: {"description": "Logged in, but not as an administrator (`admin-required`)."},
}
BUYER_ONLY_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Not logged in, or the session has ended (`authentication-required`)."},
    403: {"description": "Logged in, but not with a customer account (`buyer-required`)."},
}
