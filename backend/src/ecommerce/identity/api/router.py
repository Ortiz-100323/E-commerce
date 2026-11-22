from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status

from ecommerce.identity.api.schemas import (
    AccountResponse,
    AccountsResponse,
    LoginRequest,
    NewAccountRequest,
)
from ecommerce.identity.application.accounts import (
    CreateAdmin,
    ListAdmins,
    LoggedIn,
    LogIn,
    LogOut,
    NewAccount,
    SignUp,
)
from ecommerce.identity.application.ports import (
    IdentityUnitOfWorkFactory,
    PasswordHasher,
    TokenSource,
)
from ecommerce.identity.domain.session import ABSOLUTE_LIFETIME
from ecommerce.shared_kernel.api.access import (
    ADMIN_ONLY_RESPONSES,
    SESSION_COOKIE,
    SessionToken,
    require_admin,
    require_principal,
)
from ecommerce.shared_kernel.application.ports import Clock
from ecommerce.shared_kernel.domain.principal import Principal

COOKIE_PATH = "/api"

router = APIRouter(tags=["accounts"])

LOGIN_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "description": "The email or password is incorrect (`invalid-credentials`)."
    },
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "description": "Too many failed attempts for this email (`too-many-login-attempts`); "
        "see `Retry-After`."
    },
}
EMAIL_TAKEN: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {
        "description": "An account with this email already exists (`email-already-registered`)."
    }
}


def identity_of(request: Request) -> IdentityUnitOfWorkFactory:
    identity: IdentityUnitOfWorkFactory = request.app.state.identity_unit_of_work
    return identity


def hasher_of(request: Request) -> PasswordHasher:
    hasher: PasswordHasher = request.app.state.password_hasher
    return hasher


def tokens_of(request: Request) -> TokenSource:
    tokens: TokenSource = request.app.state.token_source
    return tokens


def clock_of(request: Request) -> Clock:
    clock: Clock = request.app.state.session_clock
    return clock


def get_log_in(request: Request) -> LogIn:
    return LogIn(identity_of(request), hasher_of(request), tokens_of(request), clock_of(request))


def get_log_out(request: Request) -> LogOut:
    return LogOut(identity_of(request), clock_of(request))


def get_create_admin(request: Request) -> CreateAdmin:
    return CreateAdmin(identity_of(request), hasher_of(request), clock_of(request))


def get_list_admins(request: Request) -> ListAdmins:
    return ListAdmins(identity_of(request))


def get_sign_up(request: Request) -> SignUp:
    return SignUp(identity_of(request), hasher_of(request), tokens_of(request), clock_of(request))


def set_session_cookie(request: Request, response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(ABSOLUTE_LIFETIME.total_seconds()),
        path=COOKIE_PATH,
        httponly=True,
        samesite="strict",
        secure=bool(request.app.state.session_cookie_secure),
    )


def clear_session_cookie(request: Request, response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path=COOKIE_PATH,
        httponly=True,
        samesite="strict",
        secure=bool(request.app.state.session_cookie_secure),
    )


def logged_in(request: Request, response: Response, result: LoggedIn) -> AccountResponse:
    set_session_cookie(request, response, result.token)
    response.headers["Cache-Control"] = "no-store"
    return AccountResponse.of_principal(result.principal)


def new_account_of(body: NewAccountRequest) -> NewAccount:
    return NewAccount(name=body.name, email=body.email, password=body.password)


@router.post(
    "/session",
    response_model=AccountResponse,
    responses=LOGIN_RESPONSES,
    summary="Log in (admins and customers alike); sets the session cookie",
)
async def log_in(
    body: LoginRequest,
    request: Request,
    response: Response,
    use_case: Annotated[LogIn, Depends(get_log_in)],
) -> AccountResponse:
    return logged_in(request, response, await use_case.execute(body.email, body.password))


@router.get(
    "/session",
    response_model=AccountResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Nobody is logged in."}},
    summary="Who is logged in",
)
async def current_session(
    principal: Annotated[Principal, Depends(require_principal)], response: Response
) -> AccountResponse:
    response.headers["Cache-Control"] = "no-store"
    return AccountResponse.of_principal(principal)


@router.delete(
    "/session",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out; harmless when already logged out",
)
async def log_out(
    request: Request,
    token: SessionToken,
    use_case: Annotated[LogOut, Depends(get_log_out)],
) -> Response:
    if token:
        await use_case.execute(token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(request, response)
    return response


@router.get(
    "/admin/accounts",
    response_model=AccountsResponse,
    responses=ADMIN_ONLY_RESPONSES,
    summary="The administrators",
    dependencies=[Depends(require_admin)],
)
async def list_admins(
    use_case: Annotated[ListAdmins, Depends(get_list_admins)],
) -> AccountsResponse:
    return AccountsResponse(
        items=[AccountResponse.of_account(account) for account in await use_case.execute()]
    )


@router.post(
    "/admin/accounts",
    status_code=status.HTTP_201_CREATED,
    response_model=AccountResponse,
    responses={**ADMIN_ONLY_RESPONSES, **EMAIL_TAKEN},
    summary="Create another administrator (the only way an administrator is made)",
)
async def create_admin(
    body: NewAccountRequest,
    admin: Annotated[Principal, Depends(require_admin)],
    use_case: Annotated[CreateAdmin, Depends(get_create_admin)],
) -> AccountResponse:
    return AccountResponse.of_account(await use_case.execute(new_account_of(body), admin))


@router.post(
    "/accounts",
    status_code=status.HTTP_201_CREATED,
    response_model=AccountResponse,
    responses=EMAIL_TAKEN,
    summary="Sign up as a customer and log in; never creates an administrator",
)
async def sign_up(
    body: NewAccountRequest,
    request: Request,
    response: Response,
    use_case: Annotated[SignUp, Depends(get_sign_up)],
) -> AccountResponse:
    return logged_in(request, response, await use_case.execute(new_account_of(body)))
