from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.catalog.domain.importing.batch import (
    BATCH_LIFETIME,
    BatchStatus,
    Decision,
    ImportBatch,
    ImportBatchId,
)
from ecommerce.catalog.domain.importing.classification import RowOutcome, SourceRow, classify
from ecommerce.catalog.domain.importing.policies import ImportPolicies
from ecommerce.catalog.domain.product import Product, new_product_id
from ecommerce.catalog.infrastructure.unit_of_work import SqlAlchemyCatalogUnitOfWork
from ecommerce.shared_kernel.domain.actor import Actor
from ecommerce.shared_kernel.domain.errors import ValidationIssue
from ecommerce.shared_kernel.infrastructure.database import create_session_factory

STARTED = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
LATER = STARTED + timedelta(minutes=5)
TESTER = Actor("Tester")
HEADER = ("name", "sku", "description", "category", "price", "stock", "weight_kg")
BATCH_ID = ImportBatchId(UUID("00000000-0000-4000-8000-0000000000b1"))


def source(line: int, *fields: str) -> SourceRow:
    return SourceRow(line=line, raw=",".join(fields), fields=fields)


def new_batch(batch_id: ImportBatchId = BATCH_ID, sha256: str = "a" * 64) -> ImportBatch:
    rows = [
        source(2, "Running Shoes", "RS-001", "Light", "Footwear", "$89.99", "10", "0.8"),
        source(3, "Mystery Box", "MB-001", "Surprise", "Gifts", "0", "5", "1"),
        source(4, "Gaming Keyboard", "GK-088", "RGB", "Electronics", "129.99", "45", ""),
    ]
    return ImportBatch.start(
        batch_id=batch_id,
        file_name="products.csv",
        sha256=sha256,
        size_bytes=321,
        classification=classify(HEADER, rows, {}, ImportPolicies()),
        file_warnings=[ValidationIssue("file", "unknown_column_ignored", "Colour is ignored.")],
        actor="Antonio",
        at=STARTED,
    )


def unit_of_work(engine: AsyncEngine, actor: Actor | None = TESTER) -> SqlAlchemyCatalogUnitOfWork:
    return SqlAlchemyCatalogUnitOfWork(create_session_factory(engine), actor)


async def store(engine: AsyncEngine, batch: ImportBatch) -> None:
    async with unit_of_work(engine) as work:
        await work.imports.add(batch)
        await work.commit()


async def load(engine: AsyncEngine, batch_id: ImportBatchId = BATCH_ID) -> ImportBatch:
    async with unit_of_work(engine, None) as work:
        batch = await work.imports.get(batch_id)
    assert batch is not None
    return batch


async def test_a_batch_round_trips_with_every_row_detail(engine: AsyncEngine) -> None:
    original = new_batch()
    await store(engine, original)

    loaded = await load(engine)

    assert (loaded.file_name, loaded.sha256, loaded.size_bytes) == ("products.csv", "a" * 64, 321)
    assert (loaded.status, loaded.uploaded_by, loaded.uploaded_at) == (
        BatchStatus.PENDING_REVIEW,
        "Antonio",
        STARTED,
    )
    assert loaded.file_warnings == original.file_warnings
    for before, after in zip(original.rows, loaded.rows, strict=True):
        assert after == before
    assert loaded.row(2).product["price"] == Decimal("89.99")


async def test_resolutions_and_history_are_saved(engine: AsyncEngine) -> None:
    await store(engine, new_batch())
    async with unit_of_work(engine) as work:
        batch = await work.imports.get(BATCH_ID, for_update=True)
        assert batch is not None
        batch.confirm(3, {}, ImportPolicies(), actor="Maria", at=LATER)
        batch.correct(4, {"weight_kg": "1.10"}, {}, ImportPolicies(), actor="Maria", at=LATER)
        batch.skip(4, actor="Maria", at=LATER)
        await work.imports.save(batch)
        await work.commit()

    loaded = await load(engine)

    assert loaded.row(3).product["gift"] is True
    assert loaded.row(3).confirmed == frozenset({"zero_price"})
    assert loaded.row(4).values["weight_kg"] == "1.10"
    assert loaded.row(4).raw_values["weight_kg"] == ""
    assert loaded.row(4).decision is Decision.SKIPPED
    assert len(loaded.row(4).history) == 2
    assert loaded.row(4).history[0].before == {"outcome": "needs_review", "weight_kg": ""}
    assert loaded.row(4).history[0].at == LATER
    assert [found.outcome for found in loaded.rows] == [
        RowOutcome.CREATE,
        RowOutcome.CREATE,
        RowOutcome.CREATE,
    ]


async def test_import_events_are_written_to_the_audit_log(engine: AsyncEngine) -> None:
    await store(engine, new_batch())

    async with engine.connect() as connection:
        rows = (
            await connection.execute(text("SELECT event, entity, entity_id, actor FROM audit_log"))
        ).all()

    assert [tuple(row) for row in rows] == [
        ("import.started", "import_batch", str(BATCH_ID), "Tester")
    ]


async def test_status_and_result_are_saved(engine: AsyncEngine) -> None:
    await store(engine, new_batch())
    async with unit_of_work(engine) as work:
        batch = await work.imports.get(BATCH_ID, for_update=True)
        assert batch is not None
        batch.discard(LATER)
        await work.imports.save(batch)
        await work.commit()

    loaded = await load(engine)

    assert (loaded.status, loaded.finished_at) == (BatchStatus.DISCARDED, LATER)


async def test_only_live_pending_batches_count_as_the_same_file(engine: AsyncEngine) -> None:
    other = ImportBatchId(UUID("00000000-0000-4000-8000-0000000000b2"))
    await store(engine, new_batch())
    await store(engine, new_batch(other, sha256="b" * 64))

    async with unit_of_work(engine, None) as work:
        same = await work.imports.pending_with_sha256("a" * 64, LATER)
        expired = await work.imports.pending_with_sha256("a" * 64, STARTED + BATCH_LIFETIME)
        unknown = await work.imports.pending_with_sha256("c" * 64, LATER)

    assert (same, expired, unknown) == ([BATCH_ID], [], [])


async def test_an_unknown_batch_is_none(engine: AsyncEngine) -> None:
    async with unit_of_work(engine, None) as work:
        assert await work.imports.get(ImportBatchId(UUID(int=7))) is None


async def test_products_are_locked_and_returned_by_sku(engine: AsyncEngine) -> None:
    async with unit_of_work(engine) as work:
        for sku in ("BB-1", "AA-1"):
            await work.products.add(
                Product.create(
                    product_id=new_product_id(),
                    sku=sku,
                    name="Item",
                    description="",
                    category="Misc",
                    price=Decimal("1.00"),
                    stock=1,
                    weight_kg=Decimal("0.1"),
                    gift=False,
                    at=STARTED,
                )
            )
        await work.commit()

    async with unit_of_work(engine, None) as work:
        locked = await work.products.lock_by_skus({"AA-1", "BB-1", "ZZ-9"})
        nothing = await work.products.lock_by_skus(set())

    assert sorted(locked) == ["AA-1", "BB-1"]
    assert nothing == {}


async def test_the_database_refuses_an_unknown_row_outcome(engine: AsyncEngine) -> None:
    await store(engine, new_batch())

    with pytest.raises(IntegrityError) as raised:
        async with engine.begin() as connection:
            await connection.execute(
                text("UPDATE import_batch_rows SET outcome = 'maybe' WHERE line = 2")
            )

    assert "ck_import_batch_rows_known_outcome" in str(raised.value)
