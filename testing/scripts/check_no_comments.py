import ast
import io
import sys
import tokenize
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

PYTHON_SUFFIXES = {".py"}
TS_SUFFIXES = {".ts", ".tsx"}
SKIPPED_DIRECTORIES = {
    "node_modules",
    ".venv",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
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


def iter_source_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        candidates = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in candidates:
            if any(part in SKIPPED_DIRECTORIES for part in path.parts):
                continue
            if path.is_file() and path.suffix in PYTHON_SUFFIXES | TS_SUFFIXES:
                yield path


def scan(roots: Iterable[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_source_files(roots):
        source = path.read_text(encoding="utf-8")
        finder = find_python_comments if path.suffix in PYTHON_SUFFIXES else find_ts_comments
        findings.extend(Finding(f.line, f.kind, path) for f in finder(source))
    return findings


def main(argv: Sequence[str]) -> int:
    findings = scan(Path(argument) for argument in argv)
    for finding in findings:
        print(f"{finding.path}:{finding.line}: {finding.kind} found")
    if findings:
        print(f"{len(findings)} comment(s) found. Code must not contain comments (CC-10).")
        return 1
    print("No comments found.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
