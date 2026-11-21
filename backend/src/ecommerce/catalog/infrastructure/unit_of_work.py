from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ecommerce.catalog.application.audit import audit_entries
from ecommerce.catalog.domain.repository import ProductRepository
from ecommerce.catalog.infrastructure.product_repository import SqlAlchemyProductRepository
from ecommerce.shared_kernel.application.audit import ActorRequired, AuditLog
from ecommerce.shared_kernel.domain.actor import Actor
from ecommerce.shared_kernel.infrastructure.audit import SqlAlchemyAuditLog, append_entries
from ecommerce.shared_kernel.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyCatalogUnitOfWork(SqlAlchemyUnitOfWork):
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], actor: Actor | None = None
    ) -> None:
        super().__init__(session_factory)
        self._actor = actor
        self._products: SqlAlchemyProductRepository | None = None

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self._products = SqlAlchemyProductRepository(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            await super().__aexit__(exc_type, exc, traceback)
        finally:
            self._products = None

    @property
    def products(self) -> ProductRepository:
        return self._repository()

    @property
    def audit_log(self) -> AuditLog:
        return SqlAlchemyAuditLog(self.session)

    async def commit(self) -> None:
        events = self._repository().take_stored_events()
        if events:
            if self._actor is None:
                raise ActorRequired()
            await append_entries(self.session, audit_entries(events, self._actor))
        await self.session.commit()

    async def rollback(self) -> None:
        self._repository().forget_stored_events()
        await self.session.rollback()

    def _repository(self) -> SqlAlchemyProductRepository:
        if self._products is None:
            raise RuntimeError("The unit of work is not active.")
        return self._products


class SqlAlchemyCatalogUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self, actor: Actor | None = None) -> SqlAlchemyCatalogUnitOfWork:
        return SqlAlchemyCatalogUnitOfWork(self._session_factory, actor)
