import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

SUFFIXES = {".ts", ".tsx"}
SKIPPED_DIRECTORIES = {"node_modules", "dist", "build", ".git"}
RAW_HTML = re.compile(
    r"\bdangerouslySetInnerHTML\b"
    r"|\.innerHTML\b"
    r"|\.outerHTML\b"
    r"|\binsertAdjacentHTML\b"
    r"|\bdocument\.write(?:ln)?\b"
    r"|\bcreateContextualFragment\b"
)


@dataclass(frozen=True)
class Finding:
    line: int
    match: str
    path: Path = Path()


def find_raw_html(source: str) -> list[Finding]:
    return [
        Finding(number, match.group(0))
        for number, text in enumerate(source.splitlines(), start=1)
        for match in RAW_HTML.finditer(text)
    ]


def files_under(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        candidates = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in candidates:
            if path.suffix in SUFFIXES and not SKIPPED_DIRECTORIES.intersection(path.parts):
                yield path


def scan(roots: Iterable[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in files_under(roots):
        source = path.read_text(encoding="utf-8")
        findings.extend(
            Finding(finding.line, finding.match, path) for finding in find_raw_html(source)
        )
    return findings


def main(argv: Sequence[str]) -> int:
    findings = scan(Path(argument) for argument in argv)
    for finding in findings:
        print(f"{finding.path}:{finding.line}: raw HTML is not allowed ({finding.match})")
    if findings:
        print(f"{len(findings)} place(s) inject raw HTML. Render text with JSX instead.")
        return 1
    print("OK: no raw HTML injection")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
