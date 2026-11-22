from pathlib import Path
from types import ModuleType

import pytest


def lines(no_comments: ModuleType, finder: str, source: str) -> list[int]:
    return [finding.line for finding in getattr(no_comments, finder)(source)]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("# whole line\nkey: value\n", [1]),
        ("key: value  # trailing\n", [1]),
        ("  # indented\n", [1]),
        ("services:\n  db:\n    image: postgres\n", []),
        ("color: \"#fff\"\nname: 'a # b'\n", []),
        ("url: http://a/b#anchor\n", []),
        ("add_header X \"default-src 'self'\";\n", []),
        ("value: ${{ github.sha }}\n", []),
    ],
)
def test_hash_comments_are_found_outside_quotes(
    no_comments: ModuleType, source: str, expected: list[int]
) -> None:
    assert lines(no_comments, "find_hash_comments", source) == expected


def test_ini_files_also_use_semicolon_comments(no_comments: ModuleType) -> None:
    assert lines(no_comments, "find_ini_comments", "[alembic]\n; note\nkey = a;b\n# other\n") == [
        2,
        4,
    ]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("/* block */\n.a { color: red; }\n", [1]),
        (".a {\n  color: red; /* why */\n}\n", [2]),
        (".a { background: url(http://example.com/x.png); }\n", []),
        ('.a::before { content: "/* not */"; }\n', []),
    ],
)
def test_css_block_comments_are_found(
    no_comments: ModuleType, source: str, expected: list[int]
) -> None:
    assert lines(no_comments, "find_css_comments", source) == expected


def test_html_comments_are_found(no_comments: ModuleType) -> None:
    source = '<html>\n<!-- note -->\n<a href="#top">top</a>\n</html>\n'
    assert lines(no_comments, "find_html_comments", source) == [2]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("-- why\nCREATE DATABASE a;\n", [1]),
        ("SELECT 1; /* block */\n", [1]),
        ("SELECT '-- not a comment', 'a /* b */';\n", []),
        ("CREATE DATABASE ecommerce_test;\n", []),
    ],
)
def test_sql_comments_are_found(no_comments: ModuleType, source: str, expected: list[int]) -> None:
    assert lines(no_comments, "find_sql_comments", source) == expected


def test_json_comments_are_found_but_not_urls_in_strings(no_comments: ModuleType) -> None:
    source = '{\n  // strict mode\n  "homepage": "https://example.com"\n}\n'
    assert lines(no_comments, "find_ts_comments", source) == [2]


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_scan_covers_every_kind_of_code_and_config_file(
    no_comments: ModuleType, tmp_path: Path
) -> None:
    dirty = {
        "Dockerfile": "# base image\nFROM python\n",
        "docker-compose.yml": "services: {}  # all\n",
        "workflow.yaml": "# job\non: push\n",
        "nginx.conf": "# proxy\nserver {}\n",
        "pyproject.toml": "# project\n[project]\n",
        "alembic.ini": "; config\n[alembic]\n",
        "init.sql": "-- database\nSELECT 1;\n",
        "start.sh": "# start\nexit 0\n",
        "style.css": "/* style */\n",
        "index.html": "<!-- page -->\n",
        "tsconfig.json": "{ // strict\n}\n",
    }
    for name, text in dirty.items():
        write(tmp_path, name, text)

    findings = no_comments.scan([tmp_path])

    assert sorted(finding.path.name for finding in findings) == sorted(dirty)


def test_scan_skips_lock_files_and_generated_folders(
    no_comments: ModuleType, tmp_path: Path
) -> None:
    write(tmp_path, "package-lock.json", '{ "a": 1 } // generated\n')
    write(tmp_path, "uv.lock", "# generated\n")
    write(tmp_path, "coverage/index.html", "<!-- report -->\n")
    write(tmp_path, "results/report/index.html", "<!-- report -->\n")
    write(tmp_path, ".mypy_cache/x.json", "// cache\n")
    write(tmp_path, ".gitignore", "# ignore list\n")
    write(tmp_path, "notes.md", "# heading\n")

    assert no_comments.scan([tmp_path]) == []


def test_main_skips_a_root_that_does_not_exist(
    no_comments: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path, "clean.py", "x = 1\n")
    missing = tmp_path / "not-here"

    assert no_comments.main([str(tmp_path), str(missing)]) == 0
    assert f"Skipped {missing}: not found." in capsys.readouterr().out


def test_the_runner_checks_the_whole_project(runner: ModuleType) -> None:
    command = runner.COMMANDS["nocomments"]()[0].command
    assert command[-6:] == [
        "backend",
        "frontend",
        "testing",
        "docker",
        "docker-compose.yml",
        ".github",
    ]
