from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, Select, delete, exists, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ecommerce.identity.domain.account import (
    Account,
    AccountId,
    AccountName,
    EmailAddress,
)
from ecommerce.identity.domain.errors import EmailAlreadyRegistered
from ecommerce.identity.domain.session import Session
from ecommerce.identity.infrastructure.tables import account_sessions, accounts
from ecommerce.shared_kernel.domain.principal import Role
from ecommerce.shared_kernel.infrastructure.audit import audit_log

LOGGED_IN = "session.logged_in"
LOGIN_FAILED = "session.login_failed"
LOGIN_ENTITY = "login"
EMAIL_UNIQUE_INDEX = "ux_accounts_email"


def to_account(row: RowMapping) -> Account:
    return Account(
        account_id=AccountId(row["id"]),
        name=AccountName(row["name"]),
        email=EmailAddress(row["email"]),
        role=Role(row["role"]),
        password_hash=row["password_hash"],
        active=row["active"],
        created_at=row["created_at"],
    )


def to_session(row: RowMapping) -> Session:
    return Session(
        session_id=row["id"],
        account_id=row["account_id"],
        token_hash=row["token_hash"],
        created_at=row["created_at"],
        last_seen_at=row["last_seen_at"],
        expires_at=row["expires_at"],
    )


class SqlAlchemyAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, account: Account) -> None:
        row = {
            "id": account.id,
            "email": account.email.value,
            "name": account.name.value,
            "role": account.role.value,
            "password_hash": account.password_hash,
            "active": account.active,
            "created_at": account.created_at,
        }
        try:
            async with self._session.begin_nested():
                await self._session.execute(insert(accounts).values(row))
        except IntegrityError as error:
            if EMAIL_UNIQUE_INDEX in str(error.orig):
                raise EmailAlreadyRegistered() from error
            raise

    async def by_id(self, account_id: UUID) -> Account | None:
        return await self._first(select(accounts).where(accounts.c.id == account_id))

    async def by_email(self, email: EmailAddress) -> Account | None:
        return await self._first(select(accounts).where(accounts.c.email == email.value))

    async def admins(self) -> Sequence[Account]:
        statement = (
            select(accounts).where(accounts.c.role == Role.ADMIN.value).order_by(accounts.c.email)
        )
        rows = (await self._session.execute(statement)).mappings().all()
        return [to_account(row) for row in rows]

    async def any_admin(self) -> bool:
        statement = select(exists().where(accounts.c.role == Role.ADMIN.value))
        return bool(await self._session.scalar(statement))

    async def replace_password_hash(self, account_id: UUID, password_hash: str) -> None:
        await self._session.execute(
            update(accounts).where(accounts.c.id == account_id).values(password_hash=password_hash)
        )

    async def _first(self, statement: Select[Any]) -> Account | None:
        row = (await self._session.execute(statement)).mappings().first()
        return None if row is None else to_account(row)


class SqlAlchemySessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, session: Session) -> None:
        await self._session.execute(
            insert(account_sessions).values(
                id=session.session_id,
                account_id=session.account_id,
                token_hash=session.token_hash,
                created_at=session.created_at,
                last_seen_at=session.last_seen_at,
                expires_at=session.expires_at,
            )
        )

    async def by_token_hash(self, token_hash: str) -> Session | None:
        statement = select(account_sessions).where(account_sessions.c.token_hash == token_hash)
        row = (await self._session.execute(statement)).mappings().first()
        return None if row is None else to_session(row)

    async def touch(self, session_id: UUID, at: datetime) -> None:
        await self._session.execute(
            update(account_sessions)
            .where(account_sessions.c.id == session_id, account_sessions.c.last_seen_at < at)
            .values(last_seen_at=at)
        )

    async def remove(self, session_id: UUID) -> None:
        await self._session.execute(
            delete(account_sessions).where(account_sessions.c.id == session_id)
        )


class SqlAlchemyLoginHistory:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def failures_since_last_success(self, login_key: str, since: datetime) -> list[datetime]:
        last_success = (
            select(func.max(audit_log.c.id))
            .where(
                audit_log.c.entity == LOGIN_ENTITY,
                audit_log.c.entity_id == login_key,
                audit_log.c.event == LOGGED_IN,
            )
            .scalar_subquery()
        )
        statement = select(audit_log.c.occurred_at).where(
            audit_log.c.entity == LOGIN_ENTITY,
            audit_log.c.entity_id == login_key,
            audit_log.c.event == LOGIN_FAILED,
            audit_log.c.occurred_at >= since,
            audit_log.c.id > func.coalesce(last_success, 0),
        )
        return list((await self._session.scalars(statement)).all())
