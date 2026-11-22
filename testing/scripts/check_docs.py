import argparse
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

README_SECTIONS = [
    "What was built",
    "Quick start",
    "Running without Docker",
    "Running the tests",
    "The sample CSV",
    "Architecture",
    "Approach",
    "Decisions and alternatives",
    "Out of scope",
    "Next steps",
    "How AI was used",
]
ADR_SECTIONS = ["Context", "Decision", "Alternatives discarded", "Consequences"]
ADR_NAME = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
LABELLED_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
JOURNAL_ENTRY = re.compile(r"^### (D-\d{3}):", re.MULTILINE)
JOURNAL_ROW = re.compile(r"^\| Journal \|(.*)\|\s*$", re.MULTILINE)
CITATION = re.compile(r"D-\d{3}")
EXTERNAL = ("http://", "https://", "mailto:")


@dataclass(frozen=True)
class Problem:
    path: Path
    message: str


def anchor_of(heading: str) -> str:
    text = heading.strip().lower().replace("`", "")
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def prose_of(text: str) -> str:
    return INLINE_CODE.sub("", FENCE.sub("", text))


def headings_of(text: str) -> list[str]:
    lines = FENCE.sub("", text).splitlines()
    return [match.group(1) for line in lines if (match := HEADING.match(line))]


def anchors_of(path: Path) -> set[str]:
    return {anchor_of(heading) for heading in headings_of(path.read_text(encoding="utf-8"))}


def link_targets(text: str) -> list[str]:
    return LINK.findall(prose_of(text))


def labelled_links(text: str) -> list[tuple[str, str]]:
    return LABELLED_LINK.findall(prose_of(text))


def names_a_real_test(label: str, path: Path) -> bool:
    name = label.partition("::")[2]
    content = path.read_text(encoding="utf-8")
    if name.isidentifier():
        return re.search(rf"\bdef {re.escape(name)}\(", content) is not None
    return name in content


def broken_links(root: Path, document: Path) -> list[Problem]:
    source = root / document
    problems = []
    for label, target in labelled_links(source.read_text(encoding="utf-8")):
        if target.startswith(EXTERNAL):
            continue
        location, _, anchor = target.partition("#")
        resolved = (source.parent / location).resolve() if location else source
        if not resolved.exists():
            problems.append(Problem(document, f"broken link: {target}"))
        elif anchor and resolved.suffix == ".md" and anchor not in anchors_of(resolved):
            problems.append(Problem(document, f"broken link: {target}"))
        elif "::" in label and resolved.is_file() and not names_a_real_test(label, resolved):
            problems.append(Problem(document, f"unknown test: {label}"))
    return problems


def linked_files(root: Path, document: Path) -> set[Path]:
    source = root / document
    return {
        (source.parent / target.partition("#")[0]).resolve()
        for target in link_targets(source.read_text(encoding="utf-8"))
        if not target.startswith(EXTERNAL) and target.partition("#")[0]
    }


def missing_sections(document: Path, text: str, required: Iterable[str]) -> list[Problem]:
    present = set(headings_of(text))
    return [
        Problem(document, f"{document.as_posix()} has no section: {section}")
        for section in required
        if section not in present
    ]


def adr_problems(root: Path, adr: Path, journal: set[str]) -> list[Problem]:
    text = (root / adr).read_text(encoding="utf-8")
    problems = missing_sections(adr, text, ADR_SECTIONS)
    row = JOURNAL_ROW.search(text)
    cited = CITATION.findall(row.group(1)) if row else []
    if not cited:
        problems.append(Problem(adr, f"{adr.as_posix()} cites no journal entry"))
    problems.extend(
        Problem(adr, f"{adr.as_posix()} cites unknown {entry}")
        for entry in cited
        if entry not in journal
    )
    return problems


def check(root: Path, extra_documents: Sequence[Path] = ()) -> list[Problem]:
    readme = Path("README.md")
    index = Path("docs/adr/README.md")
    adr_folder = root / "docs" / "adr"
    adrs = sorted(
        Path("docs/adr") / path.name for path in adr_folder.iterdir() if ADR_NAME.match(path.name)
    )
    journal = set(JOURNAL_ENTRY.findall((root / "docs" / "JOURNAL.md").read_text(encoding="utf-8")))

    problems: list[Problem] = []
    for document in [readme, index, *adrs, *extra_documents]:
        problems.extend(broken_links(root, document))
    problems.extend(
        missing_sections(readme, (root / readme).read_text(encoding="utf-8"), README_SECTIONS)
    )

    from_readme = linked_files(root, readme)
    from_index = linked_files(root, index)
    for adr in adrs:
        target = (root / adr).resolve()
        if target not in from_index:
            problems.append(Problem(index, f"{index.as_posix()} does not link {adr.name}"))
        if target not in from_readme:
            problems.append(Problem(readme, f"README.md does not link {adr.as_posix()}"))
        problems.extend(adr_problems(root, adr, journal))
    return problems


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="check_docs.py")
    parser.add_argument("--root", type=Path, default=REPO)
    parser.add_argument("extra", nargs="*", type=Path)
    arguments = parser.parse_args(argv)
    problems = check(arguments.root, arguments.extra)
    for problem in problems:
        print(f"{problem.path.as_posix()}: {problem.message}")
    if problems:
        print(f"{len(problems)} problem(s) found.")
        return 1
    print("Documents are consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
