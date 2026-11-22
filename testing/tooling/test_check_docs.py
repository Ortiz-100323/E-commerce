from pathlib import Path
from types import ModuleType

import pytest

README_SECTIONS = [
    "What was built",
    "Quick start",
    "Running without Docker",
    "Running the tests",
    "The sample CSV",
    "Architecture",
    "Decisions and alternatives",
    "Out of scope",
    "Next steps",
    "How AI was used",
]

ADR = """# ADR-0001: First decision

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-001, D-002 |

## Context

Why.

## Decision

What.

## Alternatives discarded

- Another way.

## Consequences

- What follows. See [the journal](../JOURNAL.md#d-001-first).
"""

JOURNAL = """# Decision Journal

### D-001: First
- **Status:** Accepted

### D-002: Second
- **Status:** Accepted
"""


def readme(extra: str = "", sections: list[str] | None = None) -> str:
    chosen = README_SECTIONS if sections is None else sections
    body = "\n\n".join(f"## {section}\n\nText." for section in chosen)
    links = "[0001](docs/adr/0001-first.md) and [the index](docs/adr/README.md)"
    return f"# Shop\n\n{links}\n\n{body}\n\n{extra}\n"


def build(
    root: Path,
    *,
    readme_text: str | None = None,
    adr_text: str = ADR,
    index_text: str = "| [0001](0001-first.md) | First |\n",
) -> Path:
    (root / "docs" / "adr").mkdir(parents=True)
    (root / "README.md").write_text(readme() if readme_text is None else readme_text, "utf-8")
    (root / "docs" / "JOURNAL.md").write_text(JOURNAL, encoding="utf-8")
    (root / "docs" / "adr" / "README.md").write_text(index_text, encoding="utf-8")
    (root / "docs" / "adr" / "0001-first.md").write_text(adr_text, encoding="utf-8")
    return root


def messages(check_docs: ModuleType, root: Path) -> list[str]:
    return [problem.message for problem in check_docs.check(root)]


def test_a_complete_set_of_documents_passes(check_docs: ModuleType, tmp_path: Path) -> None:
    assert messages(check_docs, build(tmp_path)) == []


def test_a_link_to_a_missing_file_is_reported(check_docs: ModuleType, tmp_path: Path) -> None:
    root = build(tmp_path, readme_text=readme("[gone](docs/missing.md)"))
    assert messages(check_docs, root) == ["broken link: docs/missing.md"]


def test_a_link_to_a_missing_heading_is_reported(check_docs: ModuleType, tmp_path: Path) -> None:
    root = build(tmp_path, readme_text=readme("[gone](docs/JOURNAL.md#d-003-third)"))
    assert messages(check_docs, root) == ["broken link: docs/JOURNAL.md#d-003-third"]


def test_a_link_to_a_heading_in_the_same_file_is_checked(
    check_docs: ModuleType, tmp_path: Path
) -> None:
    root = build(tmp_path, readme_text=readme("[ok](#out-of-scope) [bad](#nowhere)"))
    assert messages(check_docs, root) == ["broken link: #nowhere"]


@pytest.mark.parametrize(
    ("heading", "anchor"),
    [
        (
            "11.3 Questions for the customer (business stakeholder)",
            "113-questions-for-the-customer-business-stakeholder",
        ),
        ("D-001: First `code` here", "d-001-first-code-here"),
        ("Don't stop", "dont-stop"),
    ],
)
def test_headings_become_github_anchors(check_docs: ModuleType, heading: str, anchor: str) -> None:
    assert check_docs.anchor_of(heading) == anchor


def test_web_and_mail_links_are_not_checked(check_docs: ModuleType, tmp_path: Path) -> None:
    extra = "[site](https://example.com/x) [mail](mailto:a@example.com) [local](http://localhost:3000/login)"
    assert messages(check_docs, build(tmp_path, readme_text=readme(extra))) == []


def test_links_inside_code_blocks_are_not_checked(check_docs: ModuleType, tmp_path: Path) -> None:
    extra = "```\n[not a link](nowhere.md)\n```\n\nInline `[nor](this.md)` either."
    assert messages(check_docs, build(tmp_path, readme_text=readme(extra))) == []


def test_a_missing_readme_section_is_reported(check_docs: ModuleType, tmp_path: Path) -> None:
    sections = [section for section in README_SECTIONS if section != "Next steps"]
    root = build(tmp_path, readme_text=readme(sections=sections))
    assert messages(check_docs, root) == ["README.md has no section: Next steps"]


def test_an_adr_missing_from_the_index_is_reported(check_docs: ModuleType, tmp_path: Path) -> None:
    root = build(tmp_path, index_text="Nothing listed yet.\n")
    assert messages(check_docs, root) == ["docs/adr/README.md does not link 0001-first.md"]


def test_an_adr_missing_from_the_readme_is_reported(check_docs: ModuleType, tmp_path: Path) -> None:
    text = readme().replace("[0001](docs/adr/0001-first.md) and ", "")
    root = build(tmp_path, readme_text=text)
    assert messages(check_docs, root) == ["README.md does not link docs/adr/0001-first.md"]


def test_an_adr_without_a_required_section_is_reported(
    check_docs: ModuleType, tmp_path: Path
) -> None:
    root = build(tmp_path, adr_text=ADR.replace("## Alternatives discarded", "## Options"))
    assert messages(check_docs, root) == [
        "docs/adr/0001-first.md has no section: Alternatives discarded"
    ]


def test_an_adr_citing_an_unknown_journal_entry_is_reported(
    check_docs: ModuleType, tmp_path: Path
) -> None:
    root = build(tmp_path, adr_text=ADR.replace("D-001, D-002", "D-001, D-099"))
    assert messages(check_docs, root) == ["docs/adr/0001-first.md cites unknown D-099"]


def test_an_adr_citing_no_journal_entry_is_reported(check_docs: ModuleType, tmp_path: Path) -> None:
    root = build(tmp_path, adr_text=ADR.replace("| Journal | D-001, D-002 |\n", ""))
    assert messages(check_docs, root) == ["docs/adr/0001-first.md cites no journal entry"]


def test_extra_documents_are_checked_for_broken_links(
    check_docs: ModuleType, tmp_path: Path
) -> None:
    root = build(tmp_path)
    (root / "docs" / "CHECK.md").write_text("[gone](../nowhere.py)\n", encoding="utf-8")
    problems = check_docs.check(root, extra_documents=[Path("docs/CHECK.md")])
    assert [(problem.path, problem.message) for problem in problems] == [
        (Path("docs/CHECK.md"), "broken link: ../nowhere.py")
    ]


def test_main_reports_each_problem_and_fails(
    check_docs: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = build(tmp_path, readme_text=readme("[gone](docs/missing.md)"))
    assert check_docs.main(["--root", str(root)]) == 1
    output = capsys.readouterr().out
    assert "README.md: broken link: docs/missing.md" in output
    assert "1 problem(s) found" in output


def test_main_passes_on_complete_documents(
    check_docs: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert check_docs.main(["--root", str(build(tmp_path))]) == 0
    assert "Documents are consistent." in capsys.readouterr().out


def test_the_runner_checks_the_documents_on_the_host(runner: ModuleType) -> None:
    steps = runner.COMMANDS["docs"]()
    assert [step.name for step in steps] == ["script check_docs"]
    assert "docs" not in runner.ALL_ORDER
