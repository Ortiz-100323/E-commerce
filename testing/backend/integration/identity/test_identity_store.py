import asyncio
import logging

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.identity.application.accounts import NewAccount, SignUp
from ecommerce.identity.domain.errors import EmailAlreadyRegistered
from ecommerce.identity.infrastructure.security import ScryptPasswordHasher, SecretTokenSource
from ecommerce.identity.infrastructure.settings import IdentitySettings
from ecommerce.identity.infrastructure.unit_of_work import SqlAlchemyIdentityUnitOfWorkFactory
from ecommerce.identity.seed import seed_first_admin
from ecommerce.shared_kernel.application.ports import SystemClock
from ecommerce.shared_kernel.infrastructure.database import create_session_factory

HASHER = ScryptPasswordHasher(n=2**10, r=8, p=1)
PASSWORD = "seed admin password"


def identity(engine: AsyncEngine) -> SqlAlchemyIdentityUnitOfWorkFactory:
    return SqlAlchemyIdentityUnitOfWorkFactory(create_session_factory(engine))


async def rows(engine: AsyncEngine) -> list[tuple[str, str]]:
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT email, role FROM accounts ORDER BY email"))
        return [(row[0], row[1]) for row in result]


def settings(
    email: str | None = "Admin@Example.com", password: str | None = PASSWORD
) -> IdentitySettings:
    return IdentitySettings(
        admin_seed_email=email,
        admin_seed_password=None if password is None else SecretStr(password),
        admin_seed_name="Administrator",
    )


async def test_the_seed_creates_the_first_admin_once(engine: AsyncEngine) -> None:
    first = await seed_first_admin(identity(engine), HASHER, SystemClock(), settings())
    second = await seed_first_admin(
        identity(engine), HASHER, SystemClock(), settings("other@example.com")
    )

    assert first == second == 0
    assert await rows(engine) == [("admin@example.com", "ADMIN")]


async def test_the_seed_never_changes_an_existing_admins_password(engine: AsyncEngine) -> None:
    await seed_first_admin(identity(engine), HASHER, SystemClock(), settings())
    async with engine.connect() as connection:
        before = await connection.scalar(text("SELECT password_hash FROM accounts"))

    await seed_first_admin(
        identity(engine), HASHER, SystemClock(), settings(password="changed password!")
    )

    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT password_hash FROM accounts")) == before


async def test_without_settings_the_seed_warns_and_creates_nothing(
    engine: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="ecommerce.identity.seed"):
        result = await seed_first_admin(identity(engine), HASHER, SystemClock(), settings(None))

    assert result == 0
    assert await rows(engine) == []
    assert "ADMIN_SEED_EMAIL" in caplog.text


async def test_the_seed_never_promotes_a_customer(engine: AsyncEngine) -> None:
    sign_up = SignUp(identity(engine), HASHER, SecretTokenSource(), SystemClock())
    await sign_up.execute(NewAccount(name="Bea", email="admin@example.com", password=PASSWORD))

    result = await seed_first_admin(identity(engine), HASHER, SystemClock(), settings())

    assert result == 0
    assert await rows(engine) == [("admin@example.com", "BUYER")]


async def test_an_invalid_seed_is_an_error_and_creates_nothing(engine: AsyncEngine) -> None:
    result = await seed_first_admin(
        identity(engine), HASHER, SystemClock(), settings(password="short")
    )

    assert result == 1
    assert await rows(engine) == []


async def test_two_sign_ups_at_once_with_one_email_make_one_account(engine: AsyncEngine) -> None:
    sign_up = SignUp(identity(engine), HASHER, SecretTokenSource(), SystemClock())
    new = NewAccount(name="Carla", email="carla@example.com", password=PASSWORD)

    results = await asyncio.gather(
        sign_up.execute(new), sign_up.execute(new), return_exceptions=True
    )

    assert sorted(type(result).__name__ for result in results) == [
        "EmailAlreadyRegistered",
        "LoggedIn",
    ]
    assert any(isinstance(result, EmailAlreadyRegistered) for result in results)
    assert await rows(engine) == [("carla@example.com", "BUYER")]
