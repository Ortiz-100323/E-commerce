from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from ecommerce.catalog.application.unit_of_work import CatalogUnitOfWork, CatalogUnitOfWorkFactory
from ecommerce.catalog.domain.importing.batch import (
    BatchStatus,
    ImportBatch,
    ImportBatchId,
    ImportRow,
    RowAction,
)
from ecommerce.catalog.domain.importing.classification import (
    Classification,
    ExistingProduct,
    RowOutcome,
    SourceRow,
    candidate_skus,
    classify,
)
from ecommerce.catalog.domain.importing.errors import (
    ImportNotFound,
    ImportStaleRows,
    InvalidCorrection,
)
from ecommerce.catalog.domain.importing.fields import warning
from ecommerce.catalog.domain.importing.policies import ImportPolicies
from ecommerce.catalog.domain.product import Product, ProductStatus, new_product_id
from ecommerce.catalog.domain.value_objects import Sku
from ecommerce.shared_kernel.application.audit import JsonObject
from ecommerce.shared_kernel.application.ports import Clock
from ecommerce.shared_kernel.domain.actor import Actor
from ecommerce.shared_kernel.domain.errors import (
    DomainValidationError,
    ParamValue,
    ValidationIssue,
)

MAX_FILE_BYTES = 5 * 1024 * 1024
DEFAULT_FILE_NAME = "upload.csv"


@dataclass(frozen=True, kw_only=True)
class ImportFile:
    sha256: str
    size_bytes: int
    header: tuple[str, ...]
    rows: tuple[SourceRow, ...]
    warnings: tuple[ValidationIssue, ...]


class ImportFileRejected(Exception):
    def __init__(self, code: str, message: str, **params: ParamValue) -> None:
        self.code = code
        self.message = message
        self.params = params
        super().__init__(message)


class ImportFileReader(Protocol):
    def read(self, content: bytes, media_type: str | None, max_rows: int) -> ImportFile: ...


class ExistingProducts(Protocol):
    async def existing_by_skus(self, skus: Collection[str]) -> dict[str, ExistingProduct]: ...


@dataclass(frozen=True, kw_only=True)
class ImportPreview:
    file: ImportFile
    classification: Classification


@dataclass(frozen=True, kw_only=True)
class ImportState:
    batch: ImportBatch
    now: datetime

    @property
    def status(self) -> BatchStatus:
        return self.batch.status_at(self.now)

    @property
    def committable(self) -> bool:
        return self.batch.is_committable(self.now)


@dataclass(frozen=True, kw_only=True)
class RowChange:
    state: ImportState
    row: ImportRow


def existing_of(product: Product) -> ExistingProduct:
    return ExistingProduct(
        product_id=product.id,
        version=product.version,
        sku=product.sku.value,
        name=product.name.value,
        description=product.description.value,
        category=product.category.value,
        price=product.price.amount,
        stock=product.stock.value,
        weight_kg=product.weight.kg,
        gift=product.is_gift,
        archived=product.status is ProductStatus.ARCHIVED,
    )


async def read_and_classify(
    reader: ImportFileReader,
    products: ExistingProducts,
    policies: ImportPolicies,
    content: bytes,
    media_type: str | None,
) -> ImportPreview:
    imported = reader.read(content, media_type, policies.max_rows)
    skus = candidate_skus(imported.header, imported.rows)
    existing = await products.existing_by_skus(skus) if skus else {}
    classification = classify(imported.header, imported.rows, existing, policies)
    return ImportPreview(file=imported, classification=classification)


async def catalog_entry(work: CatalogUnitOfWork, raw_sku: str) -> dict[str, ExistingProduct]:
    try:
        sku = Sku(raw_sku)
    except DomainValidationError:
        return {}
    product = await work.products.get_by_sku(sku)
    return {} if product is None else {sku.value: existing_of(product)}


async def batch_to_change(work: CatalogUnitOfWork, batch_id: UUID, now: datetime) -> ImportBatch:
    batch = await work.imports.get(ImportBatchId(batch_id), for_update=True)
    if batch is None:
        raise ImportNotFound(batch_id)
    if batch.expire_if_due(now):
        await work.imports.save(batch)
        await work.commit()
    return batch


def is_stale(row: ImportRow, locked: Mapping[str, Product]) -> bool:
    product = locked.get(row.sku or "")
    if row.outcome is RowOutcome.CREATE:
        return product is not None
    return (
        product is None
        or product.id != row.target_product_id
        or product.version != row.target_version
    )


def decimal_of(value: object) -> Decimal:
    assert isinstance(value, Decimal)
    return value


def text_of(value: object) -> str:
    assert isinstance(value, str)
    return value


def int_of(value: object) -> int:
    assert isinstance(value, int)
    return value


def import_context(batch: ImportBatch, row: ImportRow) -> JsonObject:
    return {
        "source": "import",
        "batch_id": str(batch.id),
        "line": row.line,
        "file_sha256": batch.sha256,
        "raw": row.raw,
    }


@dataclass(frozen=True, kw_only=True)
class RowFields:
    sku: str
    name: str
    description: str
    category: str
    price: Decimal
    stock: int
    weight_kg: Decimal
    gift: bool

    @classmethod
    def of(cls, row: ImportRow) -> "RowFields":
        values = row.product
        return cls(
            sku=text_of(values["sku"]),
            name=text_of(values["name"]),
            description=text_of(values["description"]),
            category=text_of(values["category"]),
            price=decimal_of(values["price"]),
            stock=int_of(values["stock"]),
            weight_kg=decimal_of(values["weight_kg"]),
            gift=values.get("gift") is True,
        )


async def apply_row(
    work: CatalogUnitOfWork, row: ImportRow, locked: Mapping[str, Product], now: datetime
) -> Product:
    fields = RowFields.of(row)
    if row.outcome is RowOutcome.CREATE:
        product = Product.create(
            product_id=new_product_id(),
            sku=fields.sku,
            name=fields.name,
            description=fields.description,
            category=fields.category,
            price=fields.price,
            stock=fields.stock,
            weight_kg=fields.weight_kg,
            gift=fields.gift,
            at=now,
        )
        await work.products.add(product)
        return product
    product = locked[fields.sku]
    product.revise(
        name=fields.name,
        description=fields.description,
        category=fields.category,
        price=fields.price,
        stock=fields.stock,
        weight_kg=fields.weight_kg,
        gift=fields.gift,
        at=now,
    )
    product.restore(at=now)
    await work.products.save(product)
    return product


class PreviewImport:
    def __init__(
        self, reader: ImportFileReader, products: ExistingProducts, policies: ImportPolicies
    ) -> None:
        self._reader = reader
        self._products = products
        self._policies = policies

    async def execute(self, content: bytes, media_type: str | None) -> ImportPreview:
        return await read_and_classify(
            self._reader, self._products, self._policies, content, media_type
        )


class StartImport:
    def __init__(
        self,
        reader: ImportFileReader,
        products: ExistingProducts,
        catalog: CatalogUnitOfWorkFactory,
        policies: ImportPolicies,
        clock: Clock,
    ) -> None:
        self._reader = reader
        self._products = products
        self._catalog = catalog
        self._policies = policies
        self._clock = clock

    async def execute(
        self, content: bytes, media_type: str | None, file_name: str, actor: Actor
    ) -> ImportState:
        preview = await read_and_classify(
            self._reader, self._products, self._policies, content, media_type
        )
        now = self._clock.now()
        async with self._catalog(actor) as work:
            pending = await work.imports.pending_with_sha256(preview.file.sha256, now)
            warnings = list(preview.file.warnings)
            if pending:
                warnings.append(
                    warning(
                        "file",
                        "same_file_already_pending",
                        "This same file is already waiting for review in another import.",
                        batch_id=str(pending[0]),
                    )
                )
            batch = ImportBatch.start(
                batch_id=ImportBatchId(uuid4()),
                file_name=file_name,
                sha256=preview.file.sha256,
                size_bytes=preview.file.size_bytes,
                classification=preview.classification,
                file_warnings=warnings,
                actor=actor.name,
                at=now,
            )
            await work.imports.add(batch)
            await work.commit()
        return ImportState(batch=batch, now=now)


class GetImport:
    def __init__(self, catalog: CatalogUnitOfWorkFactory, clock: Clock) -> None:
        self._catalog = catalog
        self._clock = clock

    async def execute(self, batch_id: UUID) -> ImportState:
        async with self._catalog() as work:
            batch = await work.imports.get(ImportBatchId(batch_id))
        if batch is None:
            raise ImportNotFound(batch_id)
        return ImportState(batch=batch, now=self._clock.now())


class ResolveImportRow:
    def __init__(
        self, catalog: CatalogUnitOfWorkFactory, policies: ImportPolicies, clock: Clock
    ) -> None:
        self._catalog = catalog
        self._policies = policies
        self._clock = clock

    async def execute(
        self,
        batch_id: UUID,
        line: int,
        action: RowAction,
        values: Mapping[str, str] | None,
        actor: Actor,
    ) -> RowChange:
        now = self._clock.now()
        async with self._catalog(actor) as work:
            batch = await batch_to_change(work, batch_id, now)
            batch.ensure_pending(now)
            row = batch.row(line)
            if action is RowAction.SKIP:
                batch.skip(line, actor=actor.name, at=now)
            elif action is RowAction.CONFIRM:
                existing = await catalog_entry(work, row.values.get("sku", ""))
                batch.confirm(line, existing, self._policies, actor=actor.name, at=now)
            else:
                if values is None:
                    raise InvalidCorrection(
                        [ValidationIssue("values", "required", "Send the corrected values.")]
                    )
                existing = await catalog_entry(work, values.get("sku", row.values.get("sku", "")))
                batch.correct(line, values, existing, self._policies, actor=actor.name, at=now)
            await work.imports.save(batch)
            await work.commit()
        return RowChange(state=ImportState(batch=batch, now=now), row=batch.row(line))


class CommitImport:
    def __init__(
        self, catalog: CatalogUnitOfWorkFactory, policies: ImportPolicies, clock: Clock
    ) -> None:
        self._catalog = catalog
        self._policies = policies
        self._clock = clock

    async def execute(self, batch_id: UUID, actor: Actor) -> ImportState:
        now = self._clock.now()
        async with self._catalog(actor) as work:
            batch = await batch_to_change(work, batch_id, now)
            if batch.status is BatchStatus.COMMITTED:
                return ImportState(batch=batch, now=now)
            batch.ensure_committable(now)
            rows = batch.rows_to_apply()
            locked = await work.products.lock_by_skus({row.sku for row in rows if row.sku})
            stale = {
                row.line: existing_of(locked[row.sku]) if row.sku in locked else None
                for row in rows
                if is_stale(row, locked)
            }
            if stale:
                batch.recheck(stale, self._policies)
                await work.imports.save(batch)
                await work.commit()
                raise ImportStaleRows(sorted(stale))
            created = updated = 0
            for row in rows:
                product = await apply_row(work, row, locked, now)
                work.annotate(product.id, import_context(batch, row))
                if row.outcome is RowOutcome.CREATE:
                    created += 1
                else:
                    updated += 1
            batch.mark_committed(created=created, updated=updated, at=now)
            await work.imports.save(batch)
            await work.commit()
        return ImportState(batch=batch, now=now)


class DiscardImport:
    def __init__(self, catalog: CatalogUnitOfWorkFactory, clock: Clock) -> None:
        self._catalog = catalog
        self._clock = clock

    async def execute(self, batch_id: UUID, actor: Actor) -> ImportState:
        now = self._clock.now()
        async with self._catalog(actor) as work:
            batch = await batch_to_change(work, batch_id, now)
            batch.discard(now)
            await work.imports.save(batch)
            await work.commit()
        return ImportState(batch=batch, now=now)
