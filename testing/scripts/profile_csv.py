import csv
import io
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

BOM = b"\xef\xbb\xbf"


@dataclass
class Profile:
    size_bytes: int
    encoding: str
    has_bom: bool
    line_endings: str
    ends_with_newline: bool
    header: list[str]
    data_rows: int
    blank_rows: list[int] = field(default_factory=list)
    duplicate_skus: dict[str, list[int]] = field(default_factory=dict)
    wrong_field_counts: list[int] = field(default_factory=list)


def line_endings(content: bytes) -> str:
    crlf = content.count(b"\r\n")
    lf = content.count(b"\n") - crlf
    if crlf and lf:
        return "mixed"
    if crlf:
        return "CRLF"
    if lf:
        return "LF"
    return "none"


def profile(content: bytes) -> Profile:
    has_bom = content.startswith(BOM)
    try:
        text = content.decode("utf-8-sig")
        encoding = "UTF-8"
    except UnicodeDecodeError:
        text = content.decode("latin-1")
        encoding = "not UTF-8"
    rows = list(csv.reader(io.StringIO(text, newline="")))
    header = rows[0] if rows else []
    data = rows[1:]
    sku_column = (
        [name.strip().lower() for name in header].index("sku")
        if "sku" in [name.strip().lower() for name in header]
        else None
    )
    lines_by_sku: dict[str, list[int]] = {}
    result = Profile(
        size_bytes=len(content),
        encoding=encoding,
        has_bom=has_bom,
        line_endings=line_endings(content),
        ends_with_newline=content.endswith(b"\n"),
        header=header,
        data_rows=len(data),
    )
    for offset, values in enumerate(data, start=2):
        if all(value.strip() == "" for value in values):
            result.blank_rows.append(offset)
            continue
        if len(values) != len(header):
            result.wrong_field_counts.append(offset)
        if sku_column is not None and sku_column < len(values):
            sku = values[sku_column].strip().upper()
            if sku:
                lines_by_sku.setdefault(sku, []).append(offset)
    result.duplicate_skus = {sku: lines for sku, lines in lines_by_sku.items() if len(lines) > 1}
    return result


def report(result: Profile) -> str:
    counts = Counter(len(lines) for lines in result.duplicate_skus.values())
    lines = [
        f"Size: {result.size_bytes} bytes",
        f"Encoding: {result.encoding}{' with BOM' if result.has_bom else ', no BOM'}",
        f"Line endings: {result.line_endings}",
        f"Ends with a newline: {'yes' if result.ends_with_newline else 'no'}",
        f"Header: {', '.join(result.header)}",
        f"Data rows: {result.data_rows}",
        f"Blank rows (file lines): {result.blank_rows or 'none'}",
        f"Rows with the wrong number of fields: {result.wrong_field_counts or 'none'}",
        f"Duplicated SKUs: {len(result.duplicate_skus)} "
        f"({', '.join(f'{times}x: {number}' for times, number in sorted(counts.items()))})",
    ]
    lines.extend(f"  {sku}: lines {found}" for sku, found in sorted(result.duplicate_skus.items()))
    return "\n".join(lines)


def main(argv: Sequence[str]) -> int:
    if len(argv) != 1:
        print("Usage: profile_csv.py <file.csv>")
        return 2
    print(report(profile(Path(argv[0]).read_bytes())))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
