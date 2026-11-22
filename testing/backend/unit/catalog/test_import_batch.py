from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from ecommerce.catalog.domain.importing.batch import (
    BATCH_LIFETIME,
    BatchStatus,
    Decision,
    ImportBatch,
    ImportBatchId,
    RowAction,
)
from ecommerce.catalog.domain.importing.classification import (
    Change,
    ExistingProduct,
    RowOutcome,
    SourceRow,
    classify,
)
from ecommerce.catalog.domain.importing.errors import (
    ImportNotCommittable,
    ImportNotPending,
    ImportRowNotFound,
    ImportRowNotResolvable,
    InvalidCorrection,
)
from ecommerce.catalog.domain.importing.events import (
    ImportCommitted,
    ImportDiscarded,
    ImportRowConfirmed,
    ImportRowCorrected,
    ImportRowSkipped,
    ImportStarted,
)
from ecommerce.catalog.domain.importing.policies import ImportPolicies

HEADER = ("name", "sku", "description", "category", "price", "stock", "weight_kg")
STARTED = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
LATER = STARTED + timedelta(minutes=5)
BATCH_ID = ImportBatchId(UUID("00000000-0000-4000-8000-0000000000b1"))
DEFAULTS = ImportPolicies()


def row(line: int, name: str = "Running Shoes", sku: str = "RS-001", **overrides: str) -> SourceRow:
    values = {
        "name": name,
        "sku": sku,
        "description": "Lightweight shoes",
        "category": "Footwear",
        "price": "89.99",
        "stock": "150",
        "weight_kg": "0.35",
        **overrides,
    }
    fields = tuple(values[column] for column in HEADER)
    return SourceRow(line=line, raw=",".join(fields), fields=fields)


def existing(**overrides: Any) -> ExistingProduct:
    values: dict[str, Any] = {
        "product_id": UUID("00000000-0000-4000-8000-000000000001"),
        "version": 3,
        "sku": "RS-001",
        "name": "Running Shoes",
        "description": "Lightweight shoes",
        "category": "Footwear",
        "price": Decimal("89.99"),
        "stock": 150,
        "weight_kg": Decimal("0.350"),
        "gift": False,
        "archived": False,
        **overrides,
    }
    return ExistingProduct(**values)


def start(*rows: SourceRow, catalog: Iterable[ExistingProduct] = ()) -> ImportBatch:
    known = {item.sku: item for item in catalog}
    return ImportBatch.start(
        batch_id=BATCH_ID,
        file_name="products.csv",
        sha256="a" * 64,
        size_bytes=123,
        classification=classify(HEADER, rows, known, DEFAULTS),
        file_warnings=[],
        actor="Antonio",
        at=STARTED,
    )


def sample() -> ImportBatch:
    return start(
        row(2, sku="NEW-1"),
        row(3, sku="GIFT-1", name="Mystery Box", price="0.00"),
        row(4, sku="EMPTY-1", category=""),
        row(5, sku="BAD-1", stock="-5"),
        row(6, name="Running Shoes", sku="RS-001", price="94.99"),
        catalog=[existing()],
    )


def confirm(batch: ImportBatch, line: int, catalog: Iterable[ExistingProduct] = ()) -> None:
    known = {item.sku: item for item in catalog}
    batch.confirm(line, known, DEFAULTS, actor="Maria", at=LATER)


def correct(
    batch: ImportBatch, line: int, catalog: Iterable[ExistingProduct] = (), **values: str
) -> None:
    known = {item.sku: item for item in catalog}
    batch.correct(line, values, known, DEFAULTS, actor="Maria", at=LATER)


class TestStarting:
    def test_a_new_batch_keeps_every_row_and_waits_for_review(self) -> None:
        batch = sample()

        assert batch.status is BatchStatus.PENDING_REVIEW
        assert [found.outcome for found in batch.rows] == [
            RowOutcome.CREATE,
            RowOutcome.NEEDS_REVIEW,
            RowOutcome.NEEDS_REVIEW,
            RowOutcome.REJECTED,
            RowOutcome.UPDATE,
        ]
        assert batch.expires_at == STARTED + BATCH_LIFETIME
        assert batch.uploaded_by == "Antonio"
        assert batch.row(4).raw == "Running Shoes,EMPTY-1,Lightweight shoes,,89.99,150,0.35"
        assert batch.row(4).raw_values["category"] == ""

    def test_starting_records_one_event_with_the_summary(self) -> None:
        [event] = sample().pull_events()

        assert isinstance(event, ImportStarted)
        assert (event.file_name, event.rows) == ("products.csv", 5)
        assert event.summary["needs_review"] == 2

    def test_review_rows_and_unconfirmed_updates_are_pending(self) -> None:
        batch = sample()

        assert batch.pending_lines == [3, 4, 6]
        assert not batch.is_committable(LATER)

    def test_an_unknown_line_is_not_found(self) -> None:
        with pytest.raises(ImportRowNotFound):
            sample().row(99)

    def test_each_row_offers_only_the_actions_that_fit_it(self) -> None:
        batch = sample()

        assert {line: batch.row(line).actions for line in (2, 3, 4, 5, 6)} == {
            2: (),
            3: (RowAction.CONFIRM, RowAction.CORRECT, RowAction.SKIP),
            4: (RowAction.CORRECT, RowAction.SKIP),
            5: (),
            6: (RowAction.CONFIRM, RowAction.SKIP),
        }


class TestOnlyReviewRowsAreEditable:
    @pytest.mark.parametrize("line", [2, 5, 6])
    def test_rows_not_held_for_review_cannot_be_corrected(self, line: int) -> None:
        with pytest.raises(ImportRowNotResolvable) as raised:
            correct(sample(), line, name="Changed")

        assert raised.value.line == line

    def test_a_rejected_row_cannot_be_confirmed_or_skipped(self) -> None:
        batch = sample()

        with pytest.raises(ImportRowNotResolvable):
            confirm(batch, 5)
        with pytest.raises(ImportRowNotResolvable):
            batch.skip(5, actor="Maria", at=LATER)

    def test_an_empty_value_cannot_be_confirmed_only_corrected(self) -> None:
        with pytest.raises(ImportRowNotResolvable):
            confirm(sample(), 4)


class TestConfirming:
    def test_confirming_a_zero_price_imports_the_row_as_a_gift(self) -> None:
        batch = sample()
        batch.pull_events()

        confirm(batch, 3)

        gift = batch.row(3)
        assert (gift.outcome, gift.product["gift"]) == (RowOutcome.CREATE, True)
        assert gift.confirmed == frozenset({"zero_price"})
        [event] = batch.pull_events()
        assert isinstance(event, ImportRowConfirmed)
        assert event.original_issues == ("zero_price",)
        assert event.before == {"outcome": "needs_review", "gift": False}
        assert event.after == {"outcome": "create", "gift": True}

    def test_confirming_a_zero_weight_imports_the_row(self) -> None:
        batch = start(row(2, sku="DIGITAL-1", weight_kg="0"))

        confirm(batch, 2)

        assert batch.row(2).outcome is RowOutcome.CREATE
        assert batch.is_committable(LATER)

    def test_confirming_an_update_marks_it_confirmed(self) -> None:
        batch = sample()

        confirm(batch, 6)

        assert batch.row(6).decision is Decision.CONFIRMED
        assert batch.row(6).applies

    def test_confirming_twice_is_a_safe_retry(self) -> None:
        batch = sample()
        confirm(batch, 3)
        confirm(batch, 6)
        batch.pull_events()

        confirm(batch, 3)
        confirm(batch, 6)

        assert batch.pull_events() == []
        assert len(batch.row(3).history) == 1

    def test_a_confirmed_review_row_with_a_catalog_match_becomes_an_update(self) -> None:
        batch = start(row(2, price="0"), catalog=[existing()])

        confirm(batch, 2, [existing()])

        found = batch.row(2)
        assert found.outcome is RowOutcome.UPDATE
        assert found.changes == {"price": Change("89.99", "0.00"), "gift": Change("no", "yes")}
        assert batch.pending_lines == [2]


class TestCorrecting:
    def test_a_correction_checks_the_row_again_and_moves_it(self) -> None:
        batch = sample()
        batch.pull_events()

        correct(batch, 4, category="Sports")

        fixed = batch.row(4)
        assert (fixed.outcome, fixed.values["category"]) == (RowOutcome.CREATE, "Sports")
        assert fixed.raw_values["category"] == ""
        [event] = batch.pull_events()
        assert isinstance(event, ImportRowCorrected)
        assert event.before == {"outcome": "needs_review", "category": ""}
        assert event.after == {"outcome": "create", "category": "Sports"}
        assert event.original_issues == ("empty_required_field",)
        assert fixed.history[0].actor == "Maria"

    def test_a_correction_that_still_needs_review_stays_in_review(self) -> None:
        batch = sample()

        correct(batch, 4, category="Sports", price="0")

        assert batch.row(4).outcome is RowOutcome.NEEDS_REVIEW
        assert batch.row(4).review_codes == frozenset({"zero_price"})

    def test_an_invalid_correction_is_refused_and_changes_nothing(self) -> None:
        batch = sample()
        batch.pull_events()

        with pytest.raises(InvalidCorrection) as raised:
            correct(batch, 4, category="Sports", stock="-1", price="abc")

        assert [(found.field, found.code) for found in raised.value.issues] == [
            ("price", "invalid_number"),
            ("stock", "negative_value"),
        ]
        assert batch.row(4).outcome is RowOutcome.NEEDS_REVIEW
        assert batch.row(4).values["category"] == ""
        assert batch.pull_events() == []

    def test_a_correction_cannot_reuse_another_rows_sku(self) -> None:
        with pytest.raises(InvalidCorrection) as raised:
            correct(sample(), 4, category="Sports", sku="NEW-1")

        [found] = raised.value.issues
        assert (found.code, found.params) == ("duplicate_sku_in_file", {"line": 2})

    def test_a_correction_cannot_take_a_different_products_sku(self) -> None:
        batch = start(row(4, sku="EMPTY-1", category=""))

        with pytest.raises(InvalidCorrection) as raised:
            correct(batch, 4, [existing()], category="Sports", sku="RS-001", name="Yoga Mat")

        assert [found.code for found in raised.value.issues] == ["sku_belongs_to_different_product"]

    def test_an_unknown_column_is_refused(self) -> None:
        with pytest.raises(InvalidCorrection) as raised:
            correct(sample(), 4, colour="red")

        assert [found.code for found in raised.value.issues] == ["unknown_field"]

    def test_the_same_values_again_record_nothing(self) -> None:
        batch = sample()
        correct(batch, 4, category="Sports")
        batch.pull_events()

        correct(batch, 4, category="Sports")

        assert batch.pull_events() == []

    def test_a_corrected_row_can_be_corrected_again(self) -> None:
        batch = sample()
        correct(batch, 4, category="Sports")

        correct(batch, 4, category="Outdoor")

        assert batch.row(4).values["category"] == "Outdoor"
        assert len(batch.row(4).history) == 2

    def test_a_confirmed_gift_stops_being_a_gift_when_the_price_is_corrected(self) -> None:
        batch = sample()
        confirm(batch, 3)

        correct(batch, 3, price="12.50")

        assert batch.row(3).product["gift"] is False
        assert batch.row(3).outcome is RowOutcome.CREATE

    def test_a_kept_duplicate_warning_survives_a_correction(self) -> None:
        batch = start(row(2, sku="DUP-1"), row(3, sku="DUP-1", category=""))

        correct(batch, 3, category="Sports")

        assert [found.code for found in batch.row(3).issues] == ["duplicate_sku_in_file"]


class TestSkipping:
    def test_skipping_leaves_the_row_out_and_unblocks_the_commit(self) -> None:
        batch = sample()
        batch.pull_events()

        for line in (3, 4, 6):
            batch.skip(line, actor="Maria", at=LATER)

        assert batch.is_committable(LATER)
        assert [found.line for found in batch.rows_to_apply()] == [2]
        events = batch.pull_events()
        assert all(isinstance(event, ImportRowSkipped) for event in events)
        assert events[0].after == {"outcome": "needs_review", "decision": "skipped"}

    def test_skipping_twice_is_a_safe_retry(self) -> None:
        batch = sample()
        batch.skip(4, actor="Maria", at=LATER)
        batch.pull_events()

        batch.skip(4, actor="Maria", at=LATER)

        assert batch.pull_events() == []

    def test_a_skipped_review_row_comes_back_when_corrected(self) -> None:
        batch = sample()
        batch.skip(4, actor="Maria", at=LATER)

        correct(batch, 4, category="Sports")

        assert batch.row(4).decision is None
        assert batch.row(4).applies

    def test_a_skipped_update_can_still_be_confirmed(self) -> None:
        batch = sample()
        batch.skip(6, actor="Maria", at=LATER)

        confirm(batch, 6)

        assert batch.row(6).decision is Decision.CONFIRMED


class TestCommitting:
    def test_a_batch_with_pending_rows_cannot_be_committed(self) -> None:
        with pytest.raises(ImportNotCommittable) as raised:
            sample().ensure_committable(LATER)

        assert raised.value.pending_lines == (3, 4, 6)

    def test_committing_records_the_result_and_closes_the_batch(self) -> None:
        batch = sample()
        confirm(batch, 3)
        correct(batch, 4, category="Sports")
        batch.skip(6, actor="Maria", at=LATER)
        batch.pull_events()

        batch.mark_committed(created=3, updated=0, at=LATER)

        assert batch.status is BatchStatus.COMMITTED
        assert batch.result == {"created": 3, "updated": 0, "skipped": 1}
        assert batch.finished_at == LATER
        [event] = batch.pull_events()
        assert isinstance(event, ImportCommitted)
        assert (event.created, event.skipped) == (3, 1)

    def test_a_committed_batch_can_no_longer_change(self) -> None:
        batch = start(row(2, sku="NEW-1"))
        batch.mark_committed(created=1, updated=0, at=LATER)

        with pytest.raises(ImportNotPending) as raised:
            batch.skip(2, actor="Maria", at=LATER)

        assert raised.value.status == "COMMITTED"
        with pytest.raises(ImportNotPending):
            batch.discard(LATER)

    def test_a_recheck_sends_changed_rows_back_with_a_fresh_diff(self) -> None:
        batch = sample()
        confirm(batch, 6)

        batch.recheck({6: existing(version=4, price=Decimal("90.00"))}, DEFAULTS)

        rechecked = batch.row(6)
        assert rechecked.decision is None
        assert rechecked.target_version == 4
        assert rechecked.changes == {"price": Change("90.00", "94.99")}
        assert [found.code for found in rechecked.issues][-1] == "changed_since_preview"
        assert 6 in batch.pending_lines
        assert batch.take_changed_lines() == [6]

    def test_a_new_row_whose_sku_was_taken_is_rejected_on_recheck(self) -> None:
        batch = sample()

        batch.recheck({2: existing(sku="NEW-1", name="Yoga Mat")}, DEFAULTS)

        assert batch.row(2).outcome is RowOutcome.REJECTED


class TestExpiryAndDiscarding:
    def test_a_batch_expires_24_hours_after_the_upload(self) -> None:
        batch = sample()
        due = STARTED + BATCH_LIFETIME

        assert batch.status_at(due - timedelta(seconds=1)) is BatchStatus.PENDING_REVIEW
        assert batch.status_at(due) is BatchStatus.EXPIRED
        assert not batch.expire_if_due(due - timedelta(seconds=1))
        assert batch.expire_if_due(due)
        assert (batch.status, batch.finished_at) == (BatchStatus.EXPIRED, due)
        assert not batch.expire_if_due(due)

    def test_an_expired_batch_refuses_every_change(self) -> None:
        batch = sample()
        late = STARTED + BATCH_LIFETIME

        with pytest.raises(ImportNotPending) as raised:
            batch.skip(4, actor="Maria", at=late)

        assert raised.value.status == "EXPIRED"

    def test_discarding_keeps_the_rows_and_is_a_safe_retry(self) -> None:
        batch = sample()
        batch.pull_events()

        batch.discard(LATER)
        batch.discard(LATER)

        assert batch.status is BatchStatus.DISCARDED
        assert len(batch.rows) == 5
        assert [type(event) for event in batch.pull_events()] == [ImportDiscarded]
