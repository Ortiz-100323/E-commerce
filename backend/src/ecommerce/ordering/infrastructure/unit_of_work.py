from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ecommerce.ordering.application.audit import SHOP_ACTOR, order_audit_entries
from ecommerce.ordering.application.idempotency import IdempotencyStore
from ecommerce.ordering.application.ports import CatalogGateway
from ecommerce.ordering.domain.repository import OrderRepository
from ecommerce.ordering.infrastructure.idempotency_store import SqlAlchemyIdempotencyStore
from ecommerce.ordering.infrastructure.order_repository import SqlAlchemyOrderRepository
from ecommerce.shared_kernel.application.audit import AuditEntry
from ecommerce.shared_kernel.domain.actor import Actor
from ecommerce.shared_kernel.infrastructure.audit import append_entries
from ecommerce.shared_kernel.infrastructure.unit_of_work import SqlAlchemyUnitOfWork

DEFAULT_LOCK_TIMEOUT_MS = 5000


class AuditedCatalogGateway(CatalogGateway, Protocol):
    def take_audit_entries(self, actor: Actor) -> list[AuditEntry]: ...

    def forget(self) -> None: ...


CatalogGatewayFactory = Callable[[AsyncSession], AuditedCatalogGateway]


class SqlAlchemyOrderingUnitOfWork(SqlAlchemyUnitOfWork):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        catalog_factory: CatalogGatewayFactory,
        lock_timeout_ms: int,
    ) -> None:
        super().__init__(session_factory)
        self._catalog_factory = catalog_factory
        self._lock_timeout_ms = lock_timeout_ms
        self._parts: (
            tuple[SqlAlchemyOrderRepository, AuditedCatalogGateway, SqlAlchemyIdempotencyStore]
            | None
        ) = None

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        await self.session.execute(text(f"SET LOCAL lock_timeout = {int(self._lock_timeout_ms)}"))
        self._parts = (
            SqlAlchemyOrderRepository(self.session),
            self._catalog_factory(self.session),
            SqlAlchemyIdempotencyStore(self.session),
        )
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
            self._parts = None

    @property
    def orders(self) -> OrderRepository:
        return self._active()[0]

    @property
    def catalog(self) -> CatalogGateway:
        return self._active()[1]

    @property
    def idempotency(self) -> IdempotencyStore:
        return self._active()[2]

    async def commit(self) -> None:
        orders, catalog, _ = self._active()
        await append_entries(
            self.session,
            [
                *order_audit_entries(orders.take_stored_events(), SHOP_ACTOR),
                *catalog.take_audit_entries(SHOP_ACTOR),
            ],
        )
        await self.session.commit()

    async def rollback(self) -> None:
        orders, catalog, _ = self._active()
        orders.forget_stored_events()
        catalog.forget()
        await self.session.rollback()

    def _active(
        self,
    ) -> tuple[SqlAlchemyOrderRepository, AuditedCatalogGateway, SqlAlchemyIdempotencyStore]:
        if self._parts is None:
            raise RuntimeError("The unit of work is not active.")
        return self._parts


class SqlAlchemyOrderingUnitOfWorkFactory:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        catalog_factory: CatalogGatewayFactory,
        *,
        lock_timeout_ms: int = DEFAULT_LOCK_TIMEOUT_MS,
    ) -> None:
        self._session_factory = session_factory
        self._catalog_factory = catalog_factory
        self._lock_timeout_ms = lock_timeout_ms

    def __call__(self) -> SqlAlchemyOrderingUnitOfWork:
        return SqlAlchemyOrderingUnitOfWork(
            self._session_factory, self._catalog_factory, self._lock_timeout_ms
        )
