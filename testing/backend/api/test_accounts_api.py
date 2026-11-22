from typing import Any

import httpx
import pytest
from identity_fakes import TEST_PASSWORD
from live import (
    ACCOUNTS,
    ADMIN_ACCOUNTS,
    ANTONIO,
    BEA,
    PRODUCTS,
    SESSION,
    live_api,
    product_body,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.identity.domain.throttle import MAX_FAILURES
from ecommerce.main import create_app
from fakes import dependencies_factory
from problems import assert_problem

NEW_PASSWORD = "a brand new long password"


async def log_in(
    client: httpx.AsyncClient, email: str, password: str = TEST_PASSWORD
) -> httpx.Response:
    return await client.post(SESSION, json={"email": email, "password": password})


def set_cookie(response: httpx.Response) -> str:
    return response.headers.get("set-cookie", "")


async def accounts_with(engine: AsyncEngine, email: str) -> list[tuple[str, str]]:
    async with engine.connect() as connection:
        rows = await connection.execute(
            text("SELECT role, password_hash FROM accounts WHERE email = :email"),
            {"email": email},
        )
        return [(row[0], row[1]) for row in rows]


class TestLogIn:
    async def test_an_admin_logs_in_and_the_cookie_is_locked_down(
        self, engine: AsyncEngine
    ) -> None:
        async with live_api(engine) as client:
            response = await log_in(client, "Antonio@Example.com")
            me = await client.get(SESSION)

        assert response.status_code == 200
        assert response.json()["role"] == "ADMIN"
        assert me.json() == response.json()
        cookie = set_cookie(response).lower()
        for attribute in ("httponly", "samesite=strict", "path=/api", "max-age=28800"):
            assert attribute in cookie
        assert "secure" not in cookie.replace("samesite", "")
        assert response.headers["cache-control"] == "no-store"

    async def test_a_buyer_logs_in_as_a_buyer(self, engine: AsyncEngine) -> None:
        async with live_api(engine) as client:
            response = await log_in(client, "bea@example.com")

        assert response.json()["role"] == "BUYER"

    @pytest.mark.parametrize(
        ("email", "password"),
        [("antonio@example.com", "a wrong password"), ("nobody@example.com", TEST_PASSWORD)],
    )
    async def test_a_wrong_email_or_password_looks_the_same(
        self, engine: AsyncEngine, email: str, password: str
    ) -> None:
        async with live_api(engine) as client:
            response = await log_in(client, email, password)

        body = assert_problem(response, 401, "invalid-credentials")
        assert body["title"] == "The email or password is incorrect."
        assert "set-cookie" not in response.headers

    async def test_the_sixth_attempt_is_refused_even_with_the_right_password(
        self, engine: AsyncEngine
    ) -> None:
        async with live_api(engine) as client:
            for _ in range(MAX_FAILURES):
                await log_in(client, "antonio@example.com", "a wrong password")
            refused = await log_in(client, "antonio@example.com")
            other = await log_in(client, "maria@example.com")

        body = assert_problem(refused, 429, "too-many-login-attempts")
        assert 0 < int(refused.headers["retry-after"]) <= 15 * 60
        assert body["retry_after_seconds"] == int(refused.headers["retry-after"])
        assert other.status_code == 200

    async def test_logging_out_ends_the_session_at_once(self, engine: AsyncEngine) -> None:
        async with live_api(engine) as client:
            first = await client.delete(SESSION, headers=ANTONIO)
            after = await client.get(SESSION, headers=ANTONIO)
            again = await client.delete(SESSION, headers=ANTONIO)
            change = await client.post(PRODUCTS, json=product_body(), headers=ANTONIO)

        assert first.status_code == again.status_code == 204
        assert "max-age=0" in set_cookie(first).lower()
        assert_problem(after, 401, "authentication-required")
        assert_problem(change, 401, "authentication-required")

    async def test_the_cookie_is_secure_when_configured(self) -> None:
        app = create_app(dependencies_factory(cookie_secure=True))
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await log_in(client, "antonio@example.com")

        assert "; secure" in set_cookie(response).lower()


class TestAdmins:
    async def test_an_admin_creates_an_admin_who_can_log_in(self, engine: AsyncEngine) -> None:
        body = {"name": "Ana Souza", "email": "ana@example.com", "password": NEW_PASSWORD}
        async with live_api(engine) as client:
            created = await client.post(ADMIN_ACCOUNTS, json=body, headers=ANTONIO)
            listed = await client.get(ADMIN_ACCOUNTS, headers=ANTONIO)
            logged_in = await log_in(client, "ana@example.com", NEW_PASSWORD)

        assert created.status_code == 201
        assert created.json()["role"] == "ADMIN"
        assert [item["name"] for item in listed.json()["items"]] == [
            "Ana Souza",
            "Antonio",
            "Maria",
        ]
        assert logged_in.json()["role"] == "ADMIN"

    async def test_a_buyer_cannot_create_an_admin(self, engine: AsyncEngine) -> None:
        body = {"name": "Mallory", "email": "mallory@example.com", "password": NEW_PASSWORD}
        async with live_api(engine) as client:
            response = await client.post(ADMIN_ACCOUNTS, json=body, headers=BEA)
            listing = await client.get(ADMIN_ACCOUNTS, headers=BEA)

        assert_problem(response, 403, "admin-required")
        assert_problem(listing, 403, "admin-required")
        assert await accounts_with(engine, "mallory@example.com") == []

    async def test_a_buyers_email_is_never_promoted(self, engine: AsyncEngine) -> None:
        body = {"name": "Bea", "email": "BEA@example.com", "password": NEW_PASSWORD}
        async with live_api(engine) as client:
            before = await accounts_with(engine, "bea@example.com")
            response = await client.post(ADMIN_ACCOUNTS, json=body, headers=ANTONIO)

        assert_problem(response, 409, "email-already-registered")
        after = await accounts_with(engine, "bea@example.com")
        assert [role for role, _ in after] == ["BUYER"]
        assert after == before

    async def test_invalid_details_are_reported_per_field(self, engine: AsyncEngine) -> None:
        async with live_api(engine) as client:
            response = await client.post(
                ADMIN_ACCOUNTS,
                json={"name": "", "email": "x", "password": "short"},
                headers=ANTONIO,
            )

        body = assert_problem(response, 422, "validation-error")
        assert [error["field"] for error in body["errors"]] == ["name", "email", "password"]


class TestSignUp:
    async def test_creates_a_buyer_and_logs_them_in(self, engine: AsyncEngine) -> None:
        body = {"name": "Carla", "email": "Carla@Example.com", "password": NEW_PASSWORD}
        async with live_api(engine) as client:
            response = await client.post(ACCOUNTS, json=body)
            me = await client.get(SESSION)

        assert response.status_code == 201
        assert (response.json()["role"], me.json()["email"]) == ("BUYER", "carla@example.com")
        assert "httponly" in set_cookie(response).lower()
        assert [role for role, _ in await accounts_with(engine, "carla@example.com")] == ["BUYER"]

    @pytest.mark.parametrize(
        "extra",
        [{"role": "ADMIN"}, {"role": "admin"}, {"is_admin": True}, {"roles": ["ADMIN"]}],
    )
    async def test_a_request_to_be_an_admin_is_refused_and_creates_nothing(
        self, engine: AsyncEngine, extra: dict[str, Any]
    ) -> None:
        body = {"name": "Mallory", "email": "mallory@example.com", "password": NEW_PASSWORD}
        async with live_api(engine) as client:
            response = await client.post(ACCOUNTS, json={**body, **extra})

        assert_problem(response, 422, "validation-error")
        assert await accounts_with(engine, "mallory@example.com") == []

    async def test_never_takes_over_an_admins_email(self, engine: AsyncEngine) -> None:
        body = {"name": "Mallory", "email": "Antonio@example.com", "password": NEW_PASSWORD}
        async with live_api(engine) as client:
            before = await accounts_with(engine, "antonio@example.com")
            response = await client.post(ACCOUNTS, json=body)

        assert_problem(response, 409, "email-already-registered")
        assert await accounts_with(engine, "antonio@example.com") == before
        assert [role for role, _ in before] == ["ADMIN"]

    async def test_a_new_buyer_is_refused_on_the_admin_side(self, engine: AsyncEngine) -> None:
        body = {"name": "Carla", "email": "carla@example.com", "password": NEW_PASSWORD}
        async with live_api(engine) as client:
            await client.post(ACCOUNTS, json=body)
            change = await client.post(PRODUCTS, json=product_body())
            admins = await client.post(
                ADMIN_ACCOUNTS,
                json={"name": "Carla", "email": "carla2@example.com", "password": NEW_PASSWORD},
            )

        assert_problem(change, 403, "admin-required")
        assert_problem(admins, 403, "admin-required")

    async def test_signing_up_twice_with_the_same_email_makes_one_account(
        self, engine: AsyncEngine
    ) -> None:
        body = {"name": "Carla", "email": "carla@example.com", "password": NEW_PASSWORD}
        async with live_api(engine) as client:
            first = await client.post(ACCOUNTS, json=body)
            second = await client.post(ACCOUNTS, json={**body, "email": "CARLA@example.com"})

        assert first.status_code == 201
        assert_problem(second, 409, "email-already-registered")
        assert len(await accounts_with(engine, "carla@example.com")) == 1


class TestSensitiveValues:
    async def test_no_password_is_ever_stored_or_returned(self, engine: AsyncEngine) -> None:
        body = {"name": "Carla", "email": "carla@example.com", "password": NEW_PASSWORD}
        async with live_api(engine) as client:
            responses = [
                await client.post(ACCOUNTS, json=body),
                await log_in(client, "carla@example.com", NEW_PASSWORD),
                await log_in(client, "carla@example.com", "wrong " + NEW_PASSWORD),
                await client.get(SESSION),
            ]
        async with engine.connect() as connection:
            tables = [
                str((await connection.execute(text(f"SELECT * FROM {table}"))).all())
                for table in ("accounts", "account_sessions", "audit_log")
            ]

        for text_seen in [response.text for response in responses] + tables:
            assert NEW_PASSWORD not in text_seen
        stored = await accounts_with(engine, "carla@example.com")
        assert stored[0][1].startswith("scrypt$")
