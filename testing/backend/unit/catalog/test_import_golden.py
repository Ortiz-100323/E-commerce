import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from ecommerce.catalog.domain.importing.classification import Classification, RowOutcome, classify
from ecommerce.catalog.domain.importing.policies import ImportPolicies
from ecommerce.catalog.infrastructure.csv_reader import CsvImportReader
from ecommerce.catalog.infrastructure.import_settings import ImportSettings
from ecommerce.shared_kernel.domain.errors import Severity

SAMPLE = Path(__file__).resolve().parents[3] / "fixtures" / "csv" / "sample-products.csv"


def classify_sample(policies: ImportPolicies) -> Classification:
    imported = CsvImportReader().read(SAMPLE.read_bytes(), "text/csv", policies.max_rows)
    return classify(imported.header, imported.rows, {}, policies)


def lines_with(result: Classification, outcome: RowOutcome) -> list[int]:
    return [row.line for row in result.rows if row.outcome is outcome]


def test_the_sample_gives_the_expected_outcomes_on_an_empty_catalog() -> None:
    result = classify_sample(ImportPolicies())

    assert result.counts == {
        "create": 84,
        "update": 0,
        "unchanged": 0,
        "needs_review": 6,
        "rejected": 2,
        "superseded": 3,
        "blank": 2,
    }
    assert lines_with(result, RowOutcome.BLANK) == [62, 63]
    assert lines_with(result, RowOutcome.REJECTED) == [16, 20]
    assert lines_with(result, RowOutcome.NEEDS_REVIEW) == [7, 25, 41, 47, 50, 52]
    assert lines_with(result, RowOutcome.SUPERSEDED) == [2, 11, 56]


def test_the_sample_gives_exactly_three_warnings_and_no_identity_conflict() -> None:
    result = classify_sample(ImportPolicies())

    assert [(line, found.code) for line, found in result.warnings] == [
        (4, "currency_symbol_stripped"),
        (36, "duplicate_sku_in_file"),
        (89, "duplicate_sku_in_file"),
    ]
    conflicts = [
        found
        for row in result.rows
        for found in row.issues
        if found.code in ("sku_conflict_in_file", "sku_belongs_to_different_product")
    ]
    assert conflicts == []


def test_the_sample_rejections_and_reviews_have_the_expected_reasons() -> None:
    result = classify_sample(ImportPolicies())
    reasons = {
        row.line: [found.code for found in row.issues if found.severity is not Severity.WARNING]
        for row in result.rows
        if row.outcome in (RowOutcome.REJECTED, RowOutcome.NEEDS_REVIEW)
    }

    assert reasons == {
        7: ["zero_price"],
        16: ["negative_value"],
        20: ["markup_in_name"],
        25: ["empty_required_field"],
        41: ["empty_required_field"],
        47: ["zero_price"],
        50: ["empty_required_field"],
        52: ["empty_required_field", "zero_weight"],
    }
    sql = next(row for row in result.rows if row.line == 29)
    assert (sql.outcome, sql.product["name"]) == (
        RowOutcome.CREATE,
        "Robert'); DROP TABLE products;--",
    )


@pytest.fixture
def environment() -> Iterator[dict[str, str]]:
    saved = dict(os.environ)
    yield os.environ
    os.environ.clear()
    os.environ.update(saved)


@pytest.mark.parametrize(
    ("variables", "expected"),
    [
        ({}, {"create": 84, "needs_review": 6, "rejected": 2}),
        ({"IMPORT_ZERO_PRICE_POLICY": "reject"}, {"create": 84, "needs_review": 4, "rejected": 4}),
        (
            {"IMPORT_ZERO_PRICE_POLICY": "accept_as_gift"},
            {"create": 86, "needs_review": 4, "rejected": 2},
        ),
        ({"IMPORT_EMPTY_FIELD_POLICY": "reject"}, {"create": 84, "needs_review": 2, "rejected": 6}),
        ({"IMPORT_ZERO_WEIGHT_POLICY": "accept"}, {"create": 84, "needs_review": 6, "rejected": 2}),
        (
            {"IMPORT_CURRENCY_SYMBOL_POLICY": "reject"},
            {"create": 83, "needs_review": 6, "rejected": 3},
        ),
        (
            {"IMPORT_DUPLICATE_SKU_IN_FILE_POLICY": "reject_all"},
            {"create": 82, "needs_review": 6, "rejected": 7},
        ),
        ({"IMPORT_MAX_ROWS": "97"}, {"create": 84, "needs_review": 6, "rejected": 2}),
    ],
)
def test_changing_a_setting_changes_the_classification_without_code_changes(
    environment: dict[str, str], variables: dict[str, str], expected: dict[str, int]
) -> None:
    environment.update(variables)

    result = classify_sample(ImportSettings().policies())

    assert {key: result.counts[key] for key in expected} == expected


def test_the_row_limit_setting_is_applied_to_the_file(environment: dict[str, str]) -> None:
    environment["IMPORT_MAX_ROWS"] = "96"

    with pytest.raises(Exception, match="more than 96 rows"):
        classify_sample(ImportSettings().policies())


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("IMPORT_ZERO_PRICE_POLICY", "maybe"),
        ("IMPORT_MAX_ROWS", "0"),
        ("IMPORT_SKU_SIMILARITY_THRESHOLD", "2"),
    ],
)
def test_a_bad_setting_stops_the_app_and_names_the_setting(
    environment: dict[str, str], name: str, value: str
) -> None:
    environment[name] = value

    with pytest.raises(ValidationError) as raised:
        ImportSettings()

    assert name.removeprefix("IMPORT_").lower() in str(raised.value)
