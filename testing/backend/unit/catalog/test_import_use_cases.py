from collections.abc import Collection
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from ecommerce.catalog.application.get_product_history import GetProductHistory
from ecommerce.catalog.application.importing import (
    CommitImport,
    DiscardImport,
    GetImport,
    ImportState,
    ResolveImportRow,
    StartImport,
    existing_of,
)
from ecommerce.catalog.domain.importing.batch import BATCH_LIFETIME, BatchStatus, RowAction
from ecommerce.catalog.domain.importing.classification import ExistingProduct, RowOutcome
from ecommerce.catalog.domain.importing.errors import (
    ImportNotCommittable,
    ImportNotFound,
    ImportNotPending,
    ImportStaleRows,
    InvalidCorrection,
)
from ecommerce.catalog.domain.importing.policies import ImportPolicies
from ecommerce.catalog.domain.product import Product, ProductStatus, new_product_id
from ecommerce.catalog.infrastructure.csv_reader import CsvImportReader
from ecommerce.shared_kernel.domain.actor import Actor
from fakes import InMemoryCatalog, SequenceClock

STARTED = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
LATER = STARTED + timedelta(minutes=10)
ANTONIO = Actor("Antonio")
MARIA = Actor("Maria")
UNKNOWN = UUID("00000000-0000-4000-8000-000000000099")
HEADER = "name,sku,description,category,price,stock,weight_kg\n"
FILE = (
    HEADER + "Running Shoes,RS-001,Light,Footwear,94.99,10,0.8\n"
    "Mystery Box,MB-001,Surprise,Gifts,0.00,50,1.0\n"
    "Gaming Keyboard,GK-088,RGB,Electronics,129.99,45,\n"
    "Bad Stock,BS-001,Broken,Misc,5.00,-5,0.1\n"
    "Coffee Beans,CB-010,Roasted,Food,18.75,500,1.0\n"
).encode()


class CatalogProducts:
    def __init__(self, catalog: InMemoryCatalog) -> None:
        self.catalog = catalog

    async def existing_by_skus(self, skus: Collection[str]) -> dict[str, ExistingProduct]:
        return {
            product.sku.value: existing_of(product)
            for product in self.catalog.products.items.values()
            if product.sku.value in skus
        }


class Workflow:
    def __init__(self, clock: SequenceClock | None = None) -> None:
        self.catalog = InMemoryCatalog()
        self.clock = clock or SequenceClock(STARTED, LATER)
        self.policies = ImportPolicies()

    async def start(self, content: bytes = FILE) -> ImportState:
        use_case = StartImport(
            CsvImportReader(),
            CatalogProducts(self.catalog),
            self.catalog,
            self.policies,
            self.clock,
        )
        return await use_case.execute(content, "text/csv", "products.csv", ANTONIO)

    async def resolve(
        self,
        batch_id: UUID,
        line: int,
        action: RowAction,
        values: dict[str, str] | None = None,
    ) -> None:
        use_case = ResolveImportRow(self.catalog, self.policies, self.clock)
        expected = None
        batch = self.catalog.imports.items.get(batch_id)
        if action is RowAction.CONFIRM and batch is not None:
            expected = batch.row(line).outcome
        await use_case.execute(
            batch_id,
            line,
            action,
            values,
            MARIA,
            expected_outcome=expected,
        )

    async def commit(self, batch_id: UUID) -> ImportState:
        return await CommitImport(self.catalog, self.policies, self.clock).execute(batch_id, MARIA)

    async def discard(self, batch_id: UUID) -> ImportState:
        return await DiscardImport(self.catalog, self.clock).execute(batch_id, MARIA)

    def add_product(self, sku: str, name: str, *, archived: bool = False) -> Product:
        product = Product.create(
            product_id=new_product_id(),
            sku=sku,
            name=name,
            description="Light",
            category="Footwear",
            price=Decimal("89.99"),
            stock=10,
            weight_kg=Decimal("0.8"),
            gift=False,
            at=STARTED,
        )
        if archived:
            product.archive(at=STARTED)
        product.pull_events()
        self.catalog.products.items[product.id] = product
        return product

    def product(self, sku: str) -> Product:
        return next(item for item in self.catalog.products.items.values() if item.sku.value == sku)

    def events(self) -> list[str]:
        return [entry.event for entry in self.catalog.audit_log.entries]


async def resolve_review_rows(workflow: Workflow, batch_id: UUID) -> None:
    await workflow.resolve(batch_id, 3, RowAction.CONFIRM)
    await workflow.resolve(batch_id, 4, RowAction.CORRECT, {"weight_kg": "1.10"})


class TestStartingAnImport:
    async def test_the_file_is_kept_for_review_and_audited(self) -> None:
        workflow = Workflow()

        state = await workflow.start()

        assert state.status is BatchStatus.PENDING_REVIEW
        assert state.batch.counts["needs_review"] == 2
        assert workflow.catalog.imports.items[state.batch.id] is state.batch
        assert workflow.events() == ["import.started"]
        assert workflow.catalog.products.items == {}

    async def test_the_same_file_pending_twice_gets_a_warning(self) -> None:
        workflow = Workflow()
        first = await workflow.start()

        second = await workflow.start()

        [found] = second.batch.file_warnings
        assert found.code == "same_file_already_pending"
        assert found.params == {"batch_id": str(first.batch.id)}

    async def test_a_missing_import_is_not_found_by_every_use_case(self) -> None:
        workflow = Workflow()

        with pytest.raises(ImportNotFound):
            await GetImport(workflow.catalog, workflow.clock).execute(UNKNOWN)
        with pytest.raises(ImportNotFound):
            await workflow.commit(UNKNOWN)
        with pytest.raises(ImportNotFound):
            await workflow.resolve(UNKNOWN, 2, RowAction.SKIP)
        with pytest.raises(ImportNotFound):
            await workflow.discard(UNKNOWN)


class TestResolvingRows:
    async def test_each_resolution_is_audited_with_its_line(self) -> None:
        workflow = Workflow()
        state = await workflow.start()

        await resolve_review_rows(workflow, state.batch.id)

        entries = workflow.catalog.audit_log.entries[1:]
        assert [entry.event for entry in entries] == [
            "import.row.confirmed",
            "import.row.corrected",
        ]
        corrected = entries[1]
        assert corrected.entity == "import_row"
        assert corrected.entity_id == f"{state.batch.id}:4"
        assert corrected.sku == "GK-088"
        assert corrected.before == {"outcome": "needs_review", "weight_kg": ""}
        assert corrected.after == {"outcome": "create", "weight_kg": "1.10"}
        assert corrected.context == {
            "batch_id": str(state.batch.id),
            "line": 4,
            "file_sha256": state.batch.sha256,
            "original_issues": ["empty_required_field"],
        }
        assert corrected.actor == "Maria"

    async def test_a_correction_needs_values(self) -> None:
        workflow = Workflow()
        state = await workflow.start()

        with pytest.raises(InvalidCorrection) as raised:
            await workflow.resolve(state.batch.id, 4, RowAction.CORRECT)

        assert raised.value.issues[0].field == "values"

    async def test_a_correction_to_an_existing_sku_is_compared_with_that_product(self) -> None:
        workflow = Workflow()
        workflow.add_product("GK-100", "Gaming Keyboard")
        state = await workflow.start()

        await workflow.resolve(
            state.batch.id, 4, RowAction.CORRECT, {"sku": "GK-100", "weight_kg": "0.8"}
        )

        row = state.batch.row(4)
        assert row.outcome is RowOutcome.UPDATE
        assert row.target_product_id == workflow.product("GK-100").id

    async def test_a_confirmed_zero_price_with_a_catalog_match_needs_the_update_confirmed(
        self,
    ) -> None:
        workflow = Workflow()
        workflow.add_product("MB-001", "Mystery Box")
        state = await workflow.start()

        await workflow.resolve(state.batch.id, 3, RowAction.CONFIRM)

        assert state.batch.row(3).outcome is RowOutcome.UPDATE
        assert 3 in state.batch.pending_lines

    async def test_an_expired_import_is_marked_expired_and_refuses_changes(self) -> None:
        workflow = Workflow(SequenceClock(STARTED, STARTED + BATCH_LIFETIME))
        state = await workflow.start()

        with pytest.raises(ImportNotPending) as raised:
            await workflow.resolve(state.batch.id, 4, RowAction.SKIP)

        assert raised.value.status == "EXPIRED"
        assert workflow.catalog.imports.items[state.batch.id].status is BatchStatus.EXPIRED


class TestCommitting:
    async def test_commit_is_refused_while_rows_are_pending(self) -> None:
        workflow = Workflow()
        state = await workflow.start()

        with pytest.raises(ImportNotCommittable) as raised:
            await workflow.commit(state.batch.id)

        assert raised.value.pending_lines == (3, 4)
        assert workflow.catalog.products.items == {}

    async def test_commit_creates_the_products_with_their_source_line(self) -> None:
        workflow = Workflow()
        state = await workflow.start()
        await resolve_review_rows(workflow, state.batch.id)

        committed = await workflow.commit(state.batch.id)

        assert committed.status is BatchStatus.COMMITTED
        assert committed.batch.result == {"created": 4, "updated": 0, "skipped": 0}
        gift = workflow.product("MB-001")
        assert gift.is_gift
        created = next(
            entry
            for entry in workflow.catalog.audit_log.entries
            if entry.event == "product.created" and entry.sku == "GK-088"
        )
        assert created.context == {
            "source": "import",
            "batch_id": str(state.batch.id),
            "line": 4,
            "file_sha256": state.batch.sha256,
            "raw": "Gaming Keyboard,GK-088,RGB,Electronics,129.99,45,",
        }
        assert workflow.events()[-1] == "import.committed"

    async def test_committing_again_is_a_safe_retry(self) -> None:
        workflow = Workflow()
        state = await workflow.start()
        await resolve_review_rows(workflow, state.batch.id)
        await workflow.commit(state.batch.id)
        entries = len(workflow.catalog.audit_log.entries)

        again = await workflow.commit(state.batch.id)

        assert again.status is BatchStatus.COMMITTED
        assert len(workflow.catalog.products.items) == 4
        assert len(workflow.catalog.audit_log.entries) == entries

    async def test_a_confirmed_update_changes_and_restores_the_product(self) -> None:
        workflow = Workflow()
        shoes = workflow.add_product("RS-001", "Running Shoes", archived=True)
        state = await workflow.start()
        await resolve_review_rows(workflow, state.batch.id)
        await workflow.resolve(state.batch.id, 2, RowAction.CONFIRM)

        committed = await workflow.commit(state.batch.id)

        assert committed.batch.result["updated"] == 1
        assert shoes.price.amount == Decimal("94.99")
        assert shoes.status is ProductStatus.ACTIVE
        changed = [
            entry.event for entry in workflow.catalog.audit_log.entries if entry.sku == "RS-001"
        ]
        assert changed == ["import.row.confirmed", "product.changed", "product.restored"]

    async def test_a_product_changed_after_the_preview_sends_its_row_back(self) -> None:
        workflow = Workflow()
        shoes = workflow.add_product("RS-001", "Running Shoes")
        state = await workflow.start()
        await resolve_review_rows(workflow, state.batch.id)
        await workflow.resolve(state.batch.id, 2, RowAction.CONFIRM)
        shoes.reprice(Decimal("80.00"), at=LATER)
        shoes.bump_version()

        with pytest.raises(ImportStaleRows) as raised:
            await workflow.commit(state.batch.id)

        assert raised.value.lines == (2,)
        row = state.batch.row(2)
        assert row.decision is None
        assert row.changes["price"].before == "80.00"
        assert state.batch.pending_lines == [2]
        assert len(workflow.catalog.products.items) == 1

    async def test_a_new_sku_taken_after_the_preview_is_stale(self) -> None:
        workflow = Workflow()
        state = await workflow.start()
        await resolve_review_rows(workflow, state.batch.id)
        workflow.add_product("CB-010", "Coffee Beans")

        with pytest.raises(ImportStaleRows) as raised:
            await workflow.commit(state.batch.id)

        assert raised.value.lines == (6,)
        assert state.batch.row(6).outcome is RowOutcome.UPDATE
        assert state.batch.pending_lines == [6]


class TestDiscarding:
    async def test_discarding_closes_the_import_without_touching_the_catalog(self) -> None:
        workflow = Workflow()
        state = await workflow.start()

        discarded = await workflow.discard(state.batch.id)

        assert discarded.status is BatchStatus.DISCARDED
        assert workflow.events() == ["import.started", "import.discarded"]
        assert workflow.catalog.products.items == {}


class TestProductHistory:
    async def test_an_imported_product_history_starts_with_its_row_resolutions(self) -> None:
        workflow = Workflow()
        state = await workflow.start()
        await resolve_review_rows(workflow, state.batch.id)
        await workflow.commit(state.batch.id)
        keyboard = workflow.product("GK-088")

        history = await GetProductHistory(workflow.catalog).execute(keyboard.id)

        assert [entry.event for entry in history] == ["import.row.corrected", "product.created"]
        assert history[1].context["raw"] == "Gaming Keyboard,GK-088,RGB,Electronics,129.99,45,"
