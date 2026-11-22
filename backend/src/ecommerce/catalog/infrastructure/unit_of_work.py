from types import TracebackType
from typing import Self
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ecommerce.catalog.application.audit import audit_entries, import_audit_entries
from ecommerce.catalog.domain.importing.repository import ImportBatchRepository
from ecommerce.catalog.domain.repository import ProductRepository
from ecommerce.catalog.infrastructure.import_repository import SqlAlchemyImportBatchRepository
from ecommerce.catalog.infrastructure.product_repository import SqlAlchemyProductRepository
from ecommerce.shared_kernel.application.audit import ActorRequired, AuditLog, JsonObject
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
        self._imports: SqlAlchemyImportBatchRepository | None = None
        self._contexts: dict[UUID, JsonObject] = {}

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self._products = SqlAlchemyProductRepository(self.session)
        self._imports = SqlAlchemyImportBatchRepository(self.session)
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
            self._imports = None
            self._contexts = {}

    @property
    def products(self) -> ProductRepository:
        return self._repositories()[0]

    @property
    def imports(self) -> ImportBatchRepository:
        return self._repositories()[1]

    @property
    def audit_log(self) -> AuditLog:
        return SqlAlchemyAuditLog(self.session)

    def annotate(self, product_id: UUID, context: JsonObject) -> None:
        self._contexts[product_id] = context

    async def commit(self) -> None:
        products, imports = self._repositories()
        product_events = products.take_stored_events()
        import_events = imports.take_stored_events()
        if product_events or import_events:
            if self._actor is None:
                raise ActorRequired()
            await append_entries(
                self.session,
                [
                    *audit_entries(product_events, self._actor, self._contexts),
                    *import_audit_entries(import_events, self._actor),
                ],
            )
        await self.session.commit()
        self._contexts = {}

    async def rollback(self) -> None:
        products, imports = self._repositories()
        products.forget_stored_events()
        imports.forget_stored_events()
        self._contexts = {}
        await self.session.rollback()

    def _repositories(
        self,
    ) -> tuple[SqlAlchemyProductRepository, SqlAlchemyImportBatchRepository]:
        if self._products is None or self._imports is None:
            raise RuntimeError("The unit of work is not active.")
        return self._products, self._imports


class SqlAlchemyCatalogUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self, actor: Actor | None = None) -> SqlAlchemyCatalogUnitOfWork:
        return SqlAlchemyCatalogUnitOfWork(self._session_factory, actor)
