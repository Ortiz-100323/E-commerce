from collections.abc import AsyncIterator, Callable, Collection
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, datetime
from types import TracebackType
from typing import Self
from uuid import UUID

from ecommerce.catalog.application.audit import audit_entries, import_audit_entries
from ecommerce.catalog.application.importing import ExistingProducts
from ecommerce.catalog.application.products import ProductQueries, ProductQuery, ProductView
from ecommerce.catalog.application.unit_of_work import CatalogUnitOfWorkFactory
from ecommerce.catalog.domain.errors import DuplicateSku, ProductAlreadyExists, ProductNotFound
from ecommerce.catalog.domain.events import ProductEvent
from ecommerce.catalog.domain.importing.batch import BatchStatus, ImportBatch, ImportBatchId
from ecommerce.catalog.domain.importing.classification import ExistingProduct
from ecommerce.catalog.domain.importing.events import ImportEvent
from ecommerce.catalog.domain.importing.policies import ImportPolicies
from ecommerce.catalog.domain.product import Product, ProductId
from ecommerce.catalog.domain.value_objects import Sku
from ecommerce.catalog.infrastructure.csv_reader import CsvImportReader
from ecommerce.main import Dependencies
from ecommerce.shared_kernel.application.audit import ActorRequired, AuditEntry, JsonObject
from ecommerce.shared_kernel.domain.actor import Actor

FIXED_NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


class FakeDatabaseProbe:
    def __init__(self, up: bool) -> None:
        self.up = up

    async def is_up(self) -> bool:
        return self.up


class SequenceClock:
    def __init__(self, *moments: datetime) -> None:
        self.moments = list(moments) or [FIXED_NOW]
        self.index = 0

    def now(self) -> datetime:
        moment = self.moments[min(self.index, len(self.moments) - 1)]
        self.index += 1
        return moment


class InMemoryProductRepository:
    def __init__(self) -> None:
        self.items: dict[ProductId, Product] = {}
        self.stored_events: list[ProductEvent] = []
        self.saves = 0

    async def add(self, product: Product) -> None:
        if product.id in self.items:
            raise ProductAlreadyExists(product.id)
        if any(item.sku == product.sku for item in self.items.values()):
            raise DuplicateSku(product.sku.value)
        self.items[product.id] = product
        self.stored_events.extend(product.pull_events())

    async def get(self, product_id: ProductId) -> Product | None:
        return self.items.get(product_id)

    async def get_by_sku(self, sku: Sku) -> Product | None:
        return next((item for item in self.items.values() if item.sku == sku), None)

    async def save(self, product: Product) -> None:
        if not product.has_pending_events:
            return
        if product.id not in self.items:
            raise ProductNotFound(product.id)
        self.saves += 1
        product.bump_version()
        self.items[product.id] = product
        self.stored_events.extend(product.pull_events())

    async def lock_by_skus(self, skus: Collection[str]) -> dict[str, Product]:
        return {item.sku.value: item for item in self.items.values() if item.sku.value in set(skus)}


class InMemoryImportBatchRepository:
    def __init__(self) -> None:
        self.items: dict[ImportBatchId, ImportBatch] = {}
        self.stored_events: list[ImportEvent] = []

    async def add(self, batch: ImportBatch) -> None:
        self.items[batch.id] = batch
        batch.take_changed_lines()
        self.stored_events.extend(batch.pull_events())

    async def get(self, batch_id: ImportBatchId, *, for_update: bool = False) -> ImportBatch | None:
        return self.items.get(batch_id)

    async def save(self, batch: ImportBatch) -> None:
        self.items[batch.id] = batch
        batch.take_changed_lines()
        self.stored_events.extend(batch.pull_events())

    async def pending_with_sha256(self, sha256: str, now: datetime) -> list[ImportBatchId]:
        return [
            batch.id
            for batch in self.items.values()
            if batch.sha256 == sha256 and batch.status_at(now) is BatchStatus.PENDING_REVIEW
        ]


class FakeExistingProducts:
    def __init__(self, products: list[ExistingProduct] | None = None) -> None:
        self.products = {product.sku: product for product in products or []}
        self.requested: list[set[str]] = []

    async def existing_by_skus(self, skus: Collection[str]) -> dict[str, ExistingProduct]:
        self.requested.append(set(skus))
        return {sku: product for sku, product in self.products.items() if sku in skus}


class FakeProductQueries:
    def __init__(
        self, items: list[ProductView] | None = None, categories: list[str] | None = None
    ) -> None:
        self.items = items or []
        self.category_names = categories or []
        self.queries: list[ProductQuery] = []

    async def search(self, query: ProductQuery) -> tuple[list[ProductView], int]:
        self.queries.append(query)
        return self.items, len(self.items)

    async def categories(self) -> list[str]:
        return self.category_names


class InMemoryAuditLog:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    async def entries_for(self, entity: str, entity_id: str) -> list[AuditEntry]:
        return [
            entry
            for entry in self.entries
            if (entry.entity, entry.entity_id) == (entity, entity_id)
        ]


class InMemoryCatalogUnitOfWork:
    def __init__(self, catalog: "InMemoryCatalog", actor: Actor | None) -> None:
        self.products = catalog.products
        self.imports = catalog.imports
        self.audit_log = catalog.audit_log
        self.actor = actor
        self.committed = False
        self.contexts: dict[UUID, JsonObject] = {}

    def annotate(self, product_id: UUID, context: JsonObject) -> None:
        self.contexts[product_id] = context

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        events, self.products.stored_events = self.products.stored_events, []
        import_events, self.imports.stored_events = self.imports.stored_events, []
        if events or import_events:
            if self.actor is None:
                raise ActorRequired()
            self.audit_log.entries.extend(audit_entries(events, self.actor, self.contexts))
            self.audit_log.entries.extend(import_audit_entries(import_events, self.actor))
        self.contexts = {}
        self.committed = True

    async def rollback(self) -> None:
        self.products.stored_events = []
        self.imports.stored_events = []
        self.contexts = {}


class InMemoryCatalog:
    def __init__(self) -> None:
        self.products = InMemoryProductRepository()
        self.imports = InMemoryImportBatchRepository()
        self.audit_log = InMemoryAuditLog()
        self.opened: list[InMemoryCatalogUnitOfWork] = []

    def __call__(self, actor: Actor | None = None) -> InMemoryCatalogUnitOfWork:
        work = InMemoryCatalogUnitOfWork(self, actor)
        self.opened.append(work)
        return work


def dependencies_factory(
    *,
    database_up: bool = True,
    clock: SequenceClock | None = None,
    catalog: CatalogUnitOfWorkFactory | None = None,
    queries: ProductQueries | None = None,
    existing: ExistingProducts | None = None,
    policies: ImportPolicies | None = None,
) -> Callable[[], AbstractAsyncContextManager[Dependencies]]:
    dependencies = Dependencies(
        database_probe=FakeDatabaseProbe(database_up),
        catalog_unit_of_work=catalog or InMemoryCatalog(),
        catalog_queries=queries or FakeProductQueries(),
        existing_products=existing or FakeExistingProducts(),
        import_reader=CsvImportReader(),
        import_policies=policies or ImportPolicies(),
        clock=clock or SequenceClock(),
    )

    @asynccontextmanager
    async def factory() -> AsyncIterator[Dependencies]:
        yield dependencies

    return factory
