import ast
import io
import sys
import tokenize
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

PYTHON_SUFFIXES = {".py"}
TS_SUFFIXES = {".ts", ".tsx", ".json"}
HASH_SUFFIXES = {".yml", ".yaml", ".toml", ".conf", ".sh"}
HASH_NAMES = {"Dockerfile"}
SKIPPED_FILES = {"package-lock.json", "uv.lock"}
SKIPPED_DIRECTORIES = {
    "node_modules",
    ".venv",
    "dist",
    "build",
    "coverage",
    "results",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".hypothesis",
    ".git",
}


@dataclass(frozen=True)
class Finding:
    line: int
    kind: str
    path: Path = Path()


def find_python_comments(source: str) -> list[Finding]:
    findings = [
        Finding(token.start[0], "comment")
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    ]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = node.body[0] if node.body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                findings.append(Finding(first.lineno, "docstring"))
    return sorted(findings, key=lambda finding: finding.line)


def find_ts_comments(source: str) -> list[Finding]:
    findings: list[Finding] = []
    template_depths: list[int] = []
    brace_depth = 0
    line = 1
    index = 0
    length = len(source)
    in_template = False

    while index < length:
        char = source[index]
        following = source[index + 1] if index + 1 < length else ""

        if in_template:
            if char == "\\":
                index += 2
                continue
            if char == "`":
                in_template = False
            elif char == "$" and following == "{":
                template_depths.append(brace_depth)
                brace_depth += 1
                in_template = False
                index += 2
                continue
            elif char == "\n":
                line += 1
            index += 1
            continue

        if char == "\n":
            line += 1
            index += 1
        elif char in "'\"":
            index += 1
            while index < length and source[index] != char and source[index] != "\n":
                index += 2 if source[index] == "\\" else 1
            index += 1
        elif char == "`":
            in_template = True
            index += 1
        elif char == "{":
            brace_depth += 1
            index += 1
        elif char == "}":
            brace_depth -= 1
            if template_depths and template_depths[-1] == brace_depth:
                template_depths.pop()
                in_template = True
            index += 1
        elif char == "/" and following == "/":
            findings.append(Finding(line, "comment"))
            while index < length and source[index] != "\n":
                index += 1
        elif char == "/" and following == "*":
            findings.append(Finding(line, "comment"))
            end = source.find("*/", index + 2)
            end = length if end == -1 else end + 2
            line += source.count("\n", index, end)
            index = end
        else:
            index += 1

    return findings


def skip_quoted(source: str, index: int) -> int:
    quote = source[index]
    index += 1
    while index < len(source) and source[index] != quote and source[index] != "\n":
        index += 2 if source[index] == "\\" else 1
    return index + 1


def find_hash_comments(source: str) -> list[Finding]:
    findings: list[Finding] = []
    for number, text in enumerate(source.splitlines(), start=1):
        index = 0
        while index < len(text):
            char = text[index]
            if char in "'\"":
                index = skip_quoted(text, index)
            elif char == "#" and (index == 0 or text[index - 1] in " \t"):
                findings.append(Finding(number, "comment"))
                break
            else:
                index += 1
    return findings


def find_ini_comments(source: str) -> list[Finding]:
    semicolons = [
        Finding(number, "comment")
        for number, text in enumerate(source.splitlines(), start=1)
        if text.lstrip().startswith(";")
    ]
    return sorted([*semicolons, *find_hash_comments(source)], key=lambda finding: finding.line)


def find_delimited_comments(
    source: str, markers: Sequence[tuple[str, str]], quotes: str
) -> list[Finding]:
    findings: list[Finding] = []
    line = 1
    index = 0
    while index < len(source):
        char = source[index]
        opened = next((pair for pair in markers if source.startswith(pair[0], index)), None)
        if opened is not None:
            findings.append(Finding(line, "comment"))
            end = source.find(opened[1], index + len(opened[0]))
            end = len(source) if end == -1 else end + len(opened[1])
            line += source.count("\n", index, end)
            index = end
        elif char in quotes:
            end = skip_quoted(source, index)
            line += source.count("\n", index, end)
            index = end
        else:
            line += char == "\n"
            index += 1
    return findings


def find_css_comments(source: str) -> list[Finding]:
    return find_delimited_comments(source, [("/*", "*/")], "'\"")


def find_html_comments(source: str) -> list[Finding]:
    return find_delimited_comments(source, [("<!--", "-->")], "")


def find_sql_comments(source: str) -> list[Finding]:
    return find_delimited_comments(source, [("--", "\n"), ("/*", "*/")], "'")


def finder_for(path: Path) -> Callable[[str], list[Finding]] | None:
    if path.name in SKIPPED_FILES:
        return None
    if path.name in HASH_NAMES or path.suffix in HASH_SUFFIXES:
        return find_hash_comments
    finders: dict[str, Callable[[str], list[Finding]]] = {
        ".ini": find_ini_comments,
        ".css": find_css_comments,
        ".html": find_html_comments,
        ".sql": find_sql_comments,
    }
    if path.suffix in PYTHON_SUFFIXES:
        return find_python_comments
    if path.suffix in TS_SUFFIXES:
        return find_ts_comments
    return finders.get(path.suffix)


def iter_source_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        candidates = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in candidates:
            if any(part in SKIPPED_DIRECTORIES for part in path.parts):
                continue
            if path.is_file() and finder_for(path) is not None:
                yield path


def scan(roots: Iterable[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_source_files(roots):
        finder = finder_for(path)
        if finder is None:
            continue
        source = path.read_text(encoding="utf-8")
        findings.extend(Finding(f.line, f.kind, path) for f in finder(source))
    return findings


def main(argv: Sequence[str]) -> int:
    roots = [Path(argument) for argument in argv]
    for root in roots:
        if not root.exists():
            print(f"Skipped {root}: not found.")
    findings = scan(root for root in roots if root.exists())
    for finding in findings:
        print(f"{finding.path}:{finding.line}: {finding.kind} found")
    if findings:
        print(f"{len(findings)} comment(s) found. Code must not contain comments (CC-10).")
        return 1
    print("No comments found.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
