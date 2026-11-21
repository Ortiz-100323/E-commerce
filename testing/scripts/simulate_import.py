import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from ecommerce.catalog.application.importing import ImportFileRejected
from ecommerce.catalog.domain.importing.classification import Classification, RowOutcome, classify
from ecommerce.catalog.domain.importing.policies import ImportPolicies
from ecommerce.catalog.infrastructure.csv_reader import CsvImportReader
from ecommerce.shared_kernel.domain.errors import Severity


def simulate(content: bytes, policies: ImportPolicies) -> Classification:
    imported = CsvImportReader().read(content, "text/csv", policies.max_rows)
    return classify(imported.header, imported.rows, {}, policies)


def report(classification: Classification) -> str:
    lines = ["Outcomes on an empty catalog:"]
    lines.extend(f"  {outcome}: {count}" for outcome, count in classification.counts.items())
    lines.append(f"  total: {len(classification.rows)}")
    lines.append(f"Warnings: {len(classification.warnings)}")
    lines.extend(f"  line {line}: {found.code}" for line, found in classification.warnings)
    for outcome in (RowOutcome.REJECTED, RowOutcome.NEEDS_REVIEW, RowOutcome.SUPERSEDED):
        rows = [row for row in classification.rows if row.outcome is outcome]
        lines.append(f"{outcome.value} ({len(rows)}):")
        for row in rows:
            codes = [found.code for found in row.issues if found.severity is not Severity.WARNING]
            detail = (
                f"replaced by line {row.superseded_by}" if row.superseded_by else ", ".join(codes)
            )
            lines.append(f"  line {row.line} {row.values.get('sku', '')}: {detail}")
    return "\n".join(lines)


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="Classify a CSV file as the importer would.")
    parser.add_argument("file", type=Path)
    arguments = parser.parse_args(argv)
    try:
        classification = simulate(arguments.file.read_bytes(), ImportPolicies())
    except ImportFileRejected as rejected:
        print(f"File rejected: {rejected.code}: {rejected.message}")
        return 1
    print(report(classification))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
