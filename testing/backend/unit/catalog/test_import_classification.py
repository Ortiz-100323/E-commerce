from collections.abc import Iterable
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from ecommerce.catalog.domain.importing.classification import (
    Change,
    Classification,
    ExistingProduct,
    RowOutcome,
    SourceRow,
    candidate_skus,
    classify,
)
from ecommerce.catalog.domain.importing.policies import (
    DuplicateSkuPolicy,
    ExistingSkuPolicy,
    ImportPolicies,
    SkuIdentityPolicy,
)
from ecommerce.shared_kernel.domain.errors import Severity, ValidationIssue

HEADER = ("name", "sku", "description", "category", "price", "stock", "weight_kg")
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


def run(
    *rows: SourceRow,
    catalog: Iterable[ExistingProduct] = (),
    policies: ImportPolicies = DEFAULTS,
) -> Classification:
    return classify(HEADER, rows, {item.sku: item for item in catalog}, policies)


def outcomes(result: Classification) -> list[str]:
    return [classified.outcome.value for classified in result.rows]


def codes(issues: Iterable[ValidationIssue]) -> list[str]:
    return [found.code for found in issues]


class TestRowsOnTheirOwn:
    def test_a_valid_new_row_is_created(self) -> None:
        result = run(row(2))

        assert outcomes(result) == ["create"]
        assert result.rows[0].product["sku"] == "RS-001"
        assert result.rows[0].target is None

    def test_a_row_of_empty_values_is_blank(self) -> None:
        empty = SourceRow(line=5, raw=",,,,,,", fields=("",) * 7)
        nothing = SourceRow(line=6, raw="", fields=())

        assert outcomes(run(empty, nothing)) == ["blank", "blank"]

    def test_a_row_with_the_wrong_number_of_values_is_rejected(self) -> None:
        short = SourceRow(line=3, raw="a,B-1", fields=("a", "B-1"))

        classified = run(short).rows[0]

        assert classified.outcome is RowOutcome.REJECTED
        assert codes(classified.issues) == ["wrong_field_count"]
        assert classified.issues[0].params == {"expected": 7, "found": 2}

    def test_the_worst_severity_decides(self) -> None:
        result = run(
            row(2, sku="ok-1", price="$5"),
            row(3, sku="REV-1", category=""),
            row(4, sku="ERR-1", category="", stock="-1"),
        )

        assert outcomes(result) == ["create", "needs_review", "rejected"]

    def test_counts_and_warnings_cover_every_outcome(self) -> None:
        result = run(row(2, price="$5"))

        assert result.counts == {
            "create": 1,
            "update": 0,
            "unchanged": 0,
            "needs_review": 0,
            "rejected": 0,
            "superseded": 0,
            "blank": 0,
        }
        assert [(line, found.code) for line, found in result.warnings] == [
            (2, "currency_symbol_stripped")
        ]


class TestDuplicatesInTheFile:
    def test_the_last_row_wins_by_default(self) -> None:
        result = run(row(2), row(5, description="Updated"), row(9, description="Newest"))

        assert outcomes(result) == ["superseded", "superseded", "create"]
        assert [classified.superseded_by for classified in result.rows] == [9, 9, None]
        winner = result.rows[2]
        assert codes(winner.issues) == ["duplicate_sku_in_file"]
        assert winner.issues[0].severity is Severity.WARNING
        assert winner.issues[0].params == {"superseded": "2, 5"}

    def test_first_wins_keeps_the_first_row(self) -> None:
        policies = ImportPolicies(duplicate_sku=DuplicateSkuPolicy.FIRST_WINS)

        result = run(row(2), row(5), policies=policies)

        assert outcomes(result) == ["create", "superseded"]
        assert result.rows[1].superseded_by == 2

    def test_reject_all_rejects_every_row_of_the_sku(self) -> None:
        policies = ImportPolicies(duplicate_sku=DuplicateSkuPolicy.REJECT_ALL)

        result = run(row(2), row(5), policies=policies)

        assert outcomes(result) == ["rejected", "rejected"]
        assert all(
            codes(classified.issues) == ["duplicate_sku_in_file"] for classified in result.rows
        )

    def test_different_products_with_the_same_sku_are_all_rejected(self) -> None:
        result = run(row(2, name="Running Shoes"), row(5, name="Yoga Mat"))

        assert outcomes(result) == ["rejected", "rejected"]
        assert all(
            codes(classified.issues) == ["sku_conflict_in_file"] for classified in result.rows
        )
        assert result.rows[0].issues[0].params == {"lines": "2, 5"}

    def test_a_rejected_winner_does_not_bring_back_an_earlier_row(self) -> None:
        result = run(row(2), row(5, stock="-1"))

        assert outcomes(result) == ["superseded", "rejected"]

    def test_sku_spelling_does_not_hide_a_duplicate(self) -> None:
        assert outcomes(run(row(2, sku="rs-001"), row(3, sku="RS-001"))) == ["superseded", "create"]


class TestComparisonWithTheCatalog:
    def test_an_identical_row_is_unchanged(self) -> None:
        classified = run(row(2), catalog=[existing()]).rows[0]

        assert classified.outcome is RowOutcome.UNCHANGED
        assert classified.changes == {}
        assert classified.target == existing()

    def test_a_different_row_is_an_update_with_a_diff_that_needs_confirmation(self) -> None:
        classified = run(
            row(2, price="94.99", stock="120", category="FOOTWEAR"), catalog=[existing()]
        ).rows[0]

        assert classified.outcome is RowOutcome.UPDATE
        assert classified.needs_confirmation
        assert classified.changes == {
            "price": Change("89.99", "94.99"),
            "stock": Change("150", "120"),
        }

    def test_a_similar_name_is_a_rename(self) -> None:
        classified = run(row(2, name="Running Shoes Pro"), catalog=[existing()]).rows[0]

        assert classified.outcome is RowOutcome.UPDATE
        assert classified.changes == {"name": Change("Running Shoes", "Running Shoes Pro")}

    def test_a_different_product_under_the_sku_is_rejected(self) -> None:
        classified = run(row(2, name="Yoga Mat"), catalog=[existing()]).rows[0]

        assert classified.outcome is RowOutcome.REJECTED
        assert codes(classified.issues) == ["sku_belongs_to_different_product"]
        assert classified.issues[0].message == (
            'SKU RS-001 is "Running Shoes" in the catalog, but this row describes "Yoga Mat". '
            "Use another SKU, or rename the product in the admin first."
        )

    def test_an_archived_product_is_restored_by_the_update(self) -> None:
        classified = run(row(2), catalog=[existing(archived=True)]).rows[0]

        assert classified.outcome is RowOutcome.UPDATE
        assert classified.changes == {"status": Change("ARCHIVED", "ACTIVE")}
        assert codes(classified.issues) == ["restores_archived_product"]

    def test_a_row_held_for_review_keeps_its_target(self) -> None:
        classified = run(row(2, weight_kg=""), catalog=[existing()]).rows[0]

        assert classified.outcome is RowOutcome.NEEDS_REVIEW
        assert classified.target == existing()

    def test_a_row_without_a_name_is_not_compared_by_name(self) -> None:
        classified = run(row(2, name=""), catalog=[existing()]).rows[0]

        assert classified.outcome is RowOutcome.NEEDS_REVIEW

    def test_a_gift_flag_change_is_part_of_the_diff(self) -> None:
        policies = ImportPolicies(zero_price=ImportPolicies().zero_price.ACCEPT_AS_GIFT)

        classified = run(row(2, price="0"), catalog=[existing()], policies=policies).rows[0]

        assert classified.changes == {"price": Change("89.99", "0.00"), "gift": Change("no", "yes")}

    def test_create_only_rejects_an_existing_sku(self) -> None:
        policies = ImportPolicies(existing_sku=ExistingSkuPolicy.CREATE_ONLY)

        classified = run(row(2, price="1"), catalog=[existing()], policies=policies).rows[0]

        assert classified.outcome is RowOutcome.REJECTED
        assert codes(classified.issues) == ["sku_already_exists"]

    def test_update_silently_needs_no_confirmation(self) -> None:
        policies = ImportPolicies(existing_sku=ExistingSkuPolicy.UPDATE_SILENTLY)

        classified = run(row(2, price="1"), catalog=[existing()], policies=policies).rows[0]

        assert classified.outcome is RowOutcome.UPDATE
        assert not classified.needs_confirmation

    @pytest.mark.parametrize(
        ("policy", "outcome"),
        [
            (SkuIdentityPolicy.EXACT_NAME, "rejected"),
            (SkuIdentityPolicy.SKU_ONLY, "update"),
            (SkuIdentityPolicy.NAME_SIMILARITY, "update"),
        ],
    )
    def test_the_identity_policy_decides_what_a_rename_is(
        self, policy: SkuIdentityPolicy, outcome: str
    ) -> None:
        policies = ImportPolicies(sku_identity=policy)

        result = run(row(2, name="Running Shoes Pro"), catalog=[existing()], policies=policies)

        assert outcomes(result) == [outcome]


def test_candidate_skus_are_trimmed_upper_case_and_skip_blanks() -> None:
    rows = [row(2, sku=" rs-001 "), row(3, sku=""), SourceRow(line=4, raw="", fields=())]

    assert candidate_skus(HEADER, rows) == {"RS-001"}
    assert candidate_skus(("name",), rows) == set()
