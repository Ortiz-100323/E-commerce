from pathlib import Path
from types import ModuleType

import pytest

SAMPLE = Path(__file__).resolve().parents[1] / "fixtures" / "csv" / "sample-products.csv"


def test_the_profile_of_the_sample_matches_the_architecture(profile_csv: ModuleType) -> None:
    result = profile_csv.profile(SAMPLE.read_bytes())

    assert (result.encoding, result.has_bom, result.line_endings) == ("UTF-8", False, "CRLF")
    assert (result.ends_with_newline, result.data_rows) == (False, 97)
    assert result.blank_rows == [62, 63]
    assert result.duplicate_skus == {"RS-001": [2, 36], "BS-021": [11, 56, 89]}
    assert result.wrong_field_counts == []


@pytest.mark.parametrize(
    ("content", "expected"),
    [(b"a\nb\n", "LF"), (b"a\r\nb\n", "mixed"), (b"a", "none")],
)
def test_line_endings_are_detected(profile_csv: ModuleType, content: bytes, expected: str) -> None:
    assert profile_csv.line_endings(content) == expected


def test_the_profile_notices_a_bom_bad_encoding_and_short_rows(profile_csv: ModuleType) -> None:
    result = profile_csv.profile(b"\xef\xbb\xbfname,sku\nShoes\n")
    latin = profile_csv.profile("name,sku\nCaf\xe9,C-1\n".encode("latin-1"))

    assert result.has_bom
    assert result.wrong_field_counts == [2]
    assert latin.encoding == "not UTF-8"


def test_the_profile_report_and_usage(
    profile_csv: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    assert profile_csv.main([str(SAMPLE)]) == 0
    assert "Line endings: CRLF" in capsys.readouterr().out
    assert profile_csv.main([]) == 2


def test_the_simulation_reproduces_the_expected_numbers(
    simulate_import: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    assert simulate_import.main([str(SAMPLE)]) == 0
    output = capsys.readouterr().out

    for expected in ("create: 84", "needs_review: 6", "rejected: 2", "superseded: 3", "blank: 2"):
        assert expected in output
    assert "Warnings: 3" in output
    assert "line 16 DL-007: negative_value" in output


def test_the_simulation_reports_a_rejected_file(
    simulate_import: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "broken.csv"
    broken.write_bytes(b"name,sku\n")

    assert simulate_import.main([str(broken)]) == 1
    assert "missing_columns" in capsys.readouterr().out
