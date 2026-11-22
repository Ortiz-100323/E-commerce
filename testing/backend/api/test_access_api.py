from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
from identity_fakes import ANTONIO_TOKEN, BEA_TOKEN

from ecommerce.main import API_PREFIX, create_app
from ecommerce.shared_kernel.api.access import SESSION_COOKIE
from fakes import dependencies_factory

VALID_ID = "00000000-0000-4000-8000-000000000001"
CHANGE_METHODS = {"post", "put", "patch", "delete"}
ADMIN = {"Cookie": f"{SESSION_COOKIE}={ANTONIO_TOKEN}"}
BUYER = {"Cookie": f"{SESSION_COOKIE}={BEA_TOKEN}"}
TYPED_NAME_ONLY = {"X-Actor-Name": "Antonio"}
INVENTED = {"Cookie": f"{SESSION_COOKIE}=invented-token-value"}


def admin_endpoints() -> Iterator[tuple[str, str]]:
    openapi = create_app(dependencies_factory()).openapi()
    for path, item in openapi["paths"].items():
        for method in item:
            admin = (
                (path.startswith(f"{API_PREFIX}/products") and method in CHANGE_METHODS)
                or path.endswith("/history")
                or path.startswith(f"{API_PREFIX}/imports")
                or path.startswith(f"{API_PREFIX}/admin/")
            )
            if admin:
                filled = "/".join(
                    VALID_ID if part.startswith("{") and "line" not in part else part
                    for part in path.split("/")
                ).replace("{line}", "2")
                yield method.upper(), filled
    yield "GET", f"{API_PREFIX}/products?status=ALL"
    yield "GET", f"{API_PREFIX}/products?status=ARCHIVED"


ADMIN_ENDPOINTS = sorted(set(admin_endpoints()))


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(dependencies_factory())
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def send(
    client: httpx.AsyncClient, method: str, url: str, headers: dict[str, str]
) -> httpx.Response:
    body: dict[str, Any] = {"json": {}} if method in {"POST", "PUT", "PATCH"} else {}
    return await client.request(method, url, headers=headers, **body)


def problem_slug(response: httpx.Response) -> str:
    return str(response.json()["type"]).rsplit(":", 1)[-1]


def test_the_matrix_covers_every_admin_endpoint() -> None:
    assert len(ADMIN_ENDPOINTS) == 17


@pytest.mark.parametrize(("method", "url"), ADMIN_ENDPOINTS)
async def test_nobody_logged_in_is_refused(
    client: httpx.AsyncClient, method: str, url: str
) -> None:
    response = await send(client, method, url, {})

    assert response.status_code == 401, (method, url)
    assert problem_slug(response) == "authentication-required"


@pytest.mark.parametrize(("method", "url"), ADMIN_ENDPOINTS)
async def test_the_old_typed_name_header_alone_is_refused(
    client: httpx.AsyncClient, method: str, url: str
) -> None:
    response = await send(client, method, url, TYPED_NAME_ONLY)

    assert response.status_code == 401, (method, url)


@pytest.mark.parametrize(("method", "url"), ADMIN_ENDPOINTS)
async def test_an_invented_cookie_is_refused(
    client: httpx.AsyncClient, method: str, url: str
) -> None:
    response = await send(client, method, url, INVENTED)

    assert response.status_code == 401, (method, url)


@pytest.mark.parametrize(("method", "url"), ADMIN_ENDPOINTS)
async def test_a_buyer_is_refused_everywhere_on_the_admin_side(
    client: httpx.AsyncClient, method: str, url: str
) -> None:
    response = await send(client, method, url, BUYER)

    assert response.status_code == 403, (method, url)
    assert problem_slug(response) == "admin-required"


@pytest.mark.parametrize(("method", "url"), ADMIN_ENDPOINTS)
async def test_an_admin_gets_past_the_door(
    client: httpx.AsyncClient, method: str, url: str
) -> None:
    response = await send(client, method, url, ADMIN)

    assert response.status_code not in (401, 403), (method, url, response.text)


async def test_a_refused_cookie_is_cleared_so_the_next_request_is_a_guest(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(f"{API_PREFIX}/session", headers=INVENTED)

    assert response.status_code == 401
    cleared = response.headers["set-cookie"].lower()
    assert cleared.startswith(f"{SESSION_COOKIE}=;")
    assert "max-age=0" in cleared and "path=/api" in cleared


async def test_the_shop_needs_no_login(client: httpx.AsyncClient) -> None:
    for url in (
        f"{API_PREFIX}/products",
        f"{API_PREFIX}/products?status=ACTIVE",
        f"{API_PREFIX}/categories",
    ):
        assert (await client.get(url)).status_code == 200, url


async def test_a_stale_cookie_never_blocks_the_shop(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_PREFIX}/products", headers=INVENTED)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": "null"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
async def test_a_change_sent_from_another_site_is_refused(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.post(f"{API_PREFIX}/products", json={}, headers={**ADMIN, **headers})

    assert response.status_code == 403
    assert problem_slug(response) == "cross-site-request"


async def test_a_change_from_this_site_passes_the_site_check(client: httpx.AsyncClient) -> None:
    response = await client.post(
        f"{API_PREFIX}/products",
        json={},
        headers={**ADMIN, "Origin": "http://test", "Sec-Fetch-Site": "same-origin"},
    )

    assert response.status_code == 422
