from pathlib import Path

import pytest

from ecommerce.catalog.application.importing import MAX_FILE_BYTES, ImportFileRejected
from ecommerce.catalog.infrastructure.csv_reader import CsvImportReader

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "csv"
HEADER = b"name,sku,description,category,price,stock,weight_kg\r\n"
ROW = b"Running Shoes,RS-001,Light,Footwear,89.99,150,0.35\r\n"
READER = CsvImportReader()


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def rejected(
    content: bytes, media_type: str | None = "text/csv", max_rows: int = 10_000
) -> ImportFileRejected:
    with pytest.raises(ImportFileRejected) as raised:
        READER.read(content, media_type, max_rows)
    return raised.value


def test_the_sample_is_read_line_by_line_with_its_raw_text() -> None:
    content = fixture("sample-products.csv")

    imported = READER.read(content, "text/csv", 10_000)

    assert imported.header == (
        "name",
        "sku",
        "description",
        "category",
        "price",
        "stock",
        "weight_kg",
    )
    assert len(imported.rows) == 97
    assert imported.rows[0].line == 2
    assert imported.rows[0].raw == (
        "Running Shoes,RS-001,Lightweight running shoes for daily training,Footwear,89.99,150,0.35"
    )
    assert imported.rows[-1].line == 98
    assert imported.rows[2].fields[4] == "$29.99"
    assert imported.size_bytes == 8930
    assert len(imported.sha256) == 64
    assert imported.warnings == ()


def test_quotes_commas_and_escaped_quotes_are_parsed() -> None:
    imported = READER.read(fixture("extra-column.csv"), "text/csv", 10_000)

    assert imported.rows[0].fields[2] == 'Light, "fast" shoes'


def test_a_bom_is_tolerated_silently() -> None:
    imported = READER.read(fixture("with-bom.csv"), "text/csv", 10_000)

    assert imported.header[0] == "name"
    assert imported.warnings == ()


def test_header_names_are_trimmed_and_case_insensitive_and_extra_columns_are_warned() -> None:
    imported = READER.read(fixture("extra-column.csv"), "text/csv", 10_000)

    assert imported.header[:7] == (
        "name",
        "sku",
        "description",
        "category",
        "price",
        "stock",
        "weight_kg",
    )
    assert [(found.code, found.params) for found in imported.warnings] == [
        ("unknown_column_ignored", {"column": "colour"})
    ]


def test_lf_and_crlf_line_endings_give_the_same_rows() -> None:
    crlf = READER.read(HEADER + ROW, "text/csv", 10)
    lf = READER.read((HEADER + ROW).replace(b"\r\n", b"\n"), "text/csv", 10)

    assert crlf.rows[0].fields == lf.rows[0].fields


@pytest.mark.parametrize(
    "media_type",
    ["text/csv", "text/csv; charset=utf-8", "application/csv", "application/vnd.ms-excel"],
)
def test_csv_media_types_are_accepted(media_type: str) -> None:
    assert len(READER.read(HEADER + ROW, media_type, 10).rows) == 1


def test_an_oversized_file_is_refused_before_reading() -> None:
    found = rejected(b"x" * (MAX_FILE_BYTES + 1))

    assert (found.code, found.params) == ("file_too_large", {"max_bytes": MAX_FILE_BYTES})


@pytest.mark.parametrize("media_type", ["application/json", "text/plain", None, ""])
def test_other_media_types_are_refused(media_type: str | None) -> None:
    assert rejected(HEADER + ROW, media_type).code == "unsupported_media_type"


def test_a_file_that_is_not_utf8_is_refused() -> None:
    found = rejected(fixture("not-utf8.csv"))

    assert found.code == "invalid_encoding"
    assert found.params == {"byte": 56}


@pytest.mark.parametrize("content", [b"", b"   \r\n", b",,,\r\n"])
def test_an_empty_file_or_header_is_refused(content: bytes) -> None:
    assert rejected(content).code == "empty_file"


def test_a_missing_column_is_refused_with_its_name() -> None:
    found = rejected(fixture("missing-column.csv"))

    assert (found.code, found.params) == ("missing_columns", {"columns": "weight_kg"})


def test_a_duplicated_column_is_refused() -> None:
    found = rejected(fixture("duplicate-column.csv"))

    assert (found.code, found.params) == ("duplicate_columns", {"columns": "sku"})


def test_more_rows_than_the_limit_are_refused() -> None:
    found = rejected(HEADER + ROW * 3, max_rows=2)

    assert (found.code, found.params) == ("too_many_rows", {"max_rows": 2})
    assert len(READER.read(HEADER + ROW * 2, "text/csv", 2).rows) == 2


def test_an_unclosed_quote_is_malformed_with_its_line() -> None:
    found = rejected(fixture("unclosed-quote.csv"))

    assert found.code == "malformed_csv"
    assert found.params == {"line": 2}


def test_a_broken_header_is_malformed() -> None:
    assert rejected(b'"name,sku\n').code == "malformed_csv"
