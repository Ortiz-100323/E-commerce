from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from ecommerce.shared_kernel.api.problem_details import ProblemType, problem_response

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
CROSS_SITE_REQUEST = ProblemType(
    "cross-site-request", 403, "Changes must be sent from this site's own pages."
)


def origin_matches(origin: str, host: str | None) -> bool:
    if origin == "null" or host is None:
        return False
    parts = urlsplit(origin)
    return parts.scheme in ("http", "https") and parts.netloc.lower() == host.lower()


def is_cross_site(headers: Headers) -> bool:
    if headers.get("sec-fetch-site", "").lower() == "cross-site":
        return True
    origin = headers.get("origin")
    return origin is not None and not origin_matches(origin, headers.get("host"))


class SameSiteMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in SAFE_METHODS:
            await self.app(scope, receive, send)
            return
        if is_cross_site(Headers(scope=scope)):
            response = problem_response(Request(scope), CROSS_SITE_REQUEST)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
