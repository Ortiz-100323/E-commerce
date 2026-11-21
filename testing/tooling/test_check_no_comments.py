from pathlib import Path
from types import ModuleType

import pytest


def python_lines(no_comments: ModuleType, source: str) -> list[int]:
    return [finding.line for finding in no_comments.find_python_comments(source)]


def ts_lines(no_comments: ModuleType, source: str) -> list[int]:
    return [finding.line for finding in no_comments.find_ts_comments(source)]


def test_python_line_comment_is_found(no_comments: ModuleType) -> None:
    assert python_lines(no_comments, "x = 1\n# note\n") == [2]


def test_python_inline_comment_is_found(no_comments: ModuleType) -> None:
    assert python_lines(no_comments, "x = 1  # note\n") == [1]


def test_python_hash_inside_string_is_not_a_comment(no_comments: ModuleType) -> None:
    assert python_lines(no_comments, "x = '# not a comment'\n") == []


@pytest.mark.parametrize(
    "source",
    [
        '"""Module docstring."""\nx = 1\n',
        'def f():\n    """Function docstring."""\n    return 1\n',
        'class A:\n    """Class docstring."""\n',
        'async def g():\n    """Async docstring."""\n',
    ],
)
def test_python_docstrings_count_as_comments(no_comments: ModuleType, source: str) -> None:
    assert len(python_lines(no_comments, source)) == 1


def test_python_plain_strings_are_not_comments(no_comments: ModuleType) -> None:
    assert python_lines(no_comments, 'x = """multi\nline"""\ndef f():\n    return "a"\n') == []


def test_ts_line_and_block_comments_are_found(no_comments: ModuleType) -> None:
    source = "const a = 1\n// note\nconst b = 2 /* inline */\n/**\n * doc\n */\n"
    assert ts_lines(no_comments, source) == [2, 3, 4]


def test_ts_comment_markers_inside_strings_are_ignored(no_comments: ModuleType) -> None:
    source = (
        "const url = 'http://example.com'\n"
        'const glob = "src/**/*.ts"\n'
        "const t = `a // b ${'/* c */'} d`\n"
        "const n = `x ${`y ${1}`} // z`\n"
    )
    assert ts_lines(no_comments, source) == []


def test_ts_escaped_quotes_do_not_end_strings(no_comments: ModuleType) -> None:
    assert ts_lines(no_comments, "const s = 'it\\'s // fine'\n") == []


def test_ts_comment_after_template_expression_is_found(no_comments: ModuleType) -> None:
    assert ts_lines(no_comments, "const t = `${a}`\n// after\n") == [2]


def test_scan_reports_files_and_skips_vendor_directories(
    no_comments: ModuleType, tmp_path: Path
) -> None:
    (tmp_path / "clean.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "dirty.py").write_text("# bad\n", encoding="utf-8")
    (tmp_path / "view.tsx").write_text("// bad\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("# heading\n", encoding="utf-8")
    vendor = tmp_path / "node_modules" / "pkg"
    vendor.mkdir(parents=True)
    (vendor / "index.ts").write_text("// vendor\n", encoding="utf-8")

    findings = no_comments.scan([tmp_path])

    assert sorted(f.path.name for f in findings) == ["dirty.py", "view.tsx"]


def test_main_exit_code_reflects_findings(no_comments: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "clean.py").write_text("x = 1\n", encoding="utf-8")
    assert no_comments.main([str(tmp_path)]) == 0
    (tmp_path / "dirty.py").write_text("x = 1  # bad\n", encoding="utf-8")
    assert no_comments.main([str(tmp_path)]) == 1
