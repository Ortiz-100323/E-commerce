import csv
import hashlib
import io
from collections import Counter

from ecommerce.catalog.application.importing import MAX_FILE_BYTES, ImportFile, ImportFileRejected
from ecommerce.catalog.domain.importing.classification import SourceRow
from ecommerce.catalog.domain.importing.fields import COLUMNS, warning
from ecommerce.shared_kernel.domain.errors import ValidationIssue

ACCEPTED_MEDIA_TYPES = frozenset({"text/csv", "application/csv", "application/vnd.ms-excel"})


def media_type_of(value: str | None) -> str:
    return (value or "").split(";", 1)[0].strip().lower()


class CsvImportReader:
    def __init__(self, max_bytes: int = MAX_FILE_BYTES) -> None:
        self._max_bytes = max_bytes

    def read(self, content: bytes, media_type: str | None, max_rows: int) -> ImportFile:
        if len(content) > self._max_bytes:
            raise ImportFileRejected(
                "file_too_large",
                f"The file is larger than {self._max_bytes} bytes.",
                max_bytes=self._max_bytes,
            )
        if media_type_of(media_type) not in ACCEPTED_MEDIA_TYPES:
            raise ImportFileRejected(
                "unsupported_media_type",
                "Upload a .csv file (text/csv).",
                received=media_type_of(media_type),
            )
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as failure:
            raise ImportFileRejected(
                "invalid_encoding",
                'The file is not UTF-8. Save it as "CSV UTF-8" and upload it again.',
                byte=failure.start,
            ) from failure
        if text.strip() == "":
            raise ImportFileRejected(
                "empty_file", "The file is empty; it needs at least a header row."
            )
        lines = io.StringIO(text, newline="").readlines()
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        try:
            header = [name.strip().lower() for name in next(reader)]
        except csv.Error as failure:
            raise malformed(reader.line_num, failure) from failure
        if all(name == "" for name in header):
            raise ImportFileRejected("empty_file", "The first row must be the column names.")
        warnings = check_header(header)
        rows: list[SourceRow] = []
        start = reader.line_num
        try:
            for fields in reader:
                if len(rows) == max_rows:
                    raise ImportFileRejected(
                        "too_many_rows",
                        f"The file has more than {max_rows} rows.",
                        max_rows=max_rows,
                    )
                raw = "".join(lines[start : reader.line_num]).rstrip("\r\n")
                rows.append(SourceRow(line=start + 1, raw=raw, fields=tuple(fields)))
                start = reader.line_num
        except csv.Error as failure:
            raise malformed(start + 1, failure) from failure
        return ImportFile(
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            header=tuple(header),
            rows=tuple(rows),
            warnings=tuple(warnings),
        )


def malformed(line: int, failure: csv.Error) -> ImportFileRejected:
    return ImportFileRejected(
        "malformed_csv", f"The file is not valid CSV near line {line}: {failure}.", line=line
    )


def check_header(header: list[str]) -> list[ValidationIssue]:
    repeated = sorted(name for name, count in Counter(header).items() if count > 1 and name)
    if repeated:
        raise ImportFileRejected(
            "duplicate_columns",
            f"These columns appear more than once: {', '.join(repeated)}.",
            columns=", ".join(repeated),
        )
    missing = [column for column in COLUMNS if column not in header]
    if missing:
        raise ImportFileRejected(
            "missing_columns",
            f"These columns are missing: {', '.join(missing)}.",
            columns=", ".join(missing),
        )
    return [
        warning(
            "file",
            "unknown_column_ignored",
            f'The column "{name or "(no name)"}" is not used and was ignored.',
            column=name,
        )
        for name in header
        if name not in COLUMNS
    ]
