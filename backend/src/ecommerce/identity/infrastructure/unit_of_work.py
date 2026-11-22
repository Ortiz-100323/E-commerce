from typing import Self

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ecommerce.identity.infrastructure.repositories import (
    SqlAlchemyAccountRepository,
    SqlAlchemyLoginHistory,
    SqlAlchemySessionRepository,
)
from ecommerce.shared_kernel.application.audit import AuditEntry
from ecommerce.shared_kernel.infrastructure.audit import append_entries
from ecommerce.shared_kernel.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyIdentityUnitOfWork(SqlAlchemyUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(session_factory)
        self._entries: list[AuditEntry] = []

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self._entries = []
        return self

    @property
    def accounts(self) -> SqlAlchemyAccountRepository:
        return SqlAlchemyAccountRepository(self.session)

    @property
    def sessions(self) -> SqlAlchemySessionRepository:
        return SqlAlchemySessionRepository(self.session)

    @property
    def logins(self) -> SqlAlchemyLoginHistory:
        return SqlAlchemyLoginHistory(self.session)

    async def lock(self, key: str) -> None:
        await self.session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(f"identity:{key}", 0)))
        )

    def record(self, entry: AuditEntry) -> None:
        self._entries.append(entry)

    async def commit(self) -> None:
        entries, self._entries = self._entries, []
        await append_entries(self.session, entries)
        await super().commit()

    async def rollback(self) -> None:
        self._entries = []
        await super().rollback()


class SqlAlchemyIdentityUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> SqlAlchemyIdentityUnitOfWork:
        return SqlAlchemyIdentityUnitOfWork(self._session_factory)
