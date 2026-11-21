from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from itertools import combinations
from uuid import UUID

from ecommerce.catalog.domain.importing.fields import COLUMNS, error, parse_fields, warning
from ecommerce.catalog.domain.importing.policies import (
    DuplicateSkuPolicy,
    ExistingSkuPolicy,
    ImportPolicies,
)
from ecommerce.catalog.domain.importing.similarity import same_product
from ecommerce.shared_kernel.domain.errors import Severity, ValidationIssue


class RowOutcome(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    UNCHANGED = "unchanged"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    BLANK = "blank"


@dataclass(frozen=True, kw_only=True)
class SourceRow:
    line: int
    raw: str
    fields: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class ExistingProduct:
    product_id: UUID
    version: int
    sku: str
    name: str
    description: str
    category: str
    price: Decimal
    stock: int
    weight_kg: Decimal
    gift: bool
    archived: bool


@dataclass(frozen=True)
class Change:
    before: str
    after: str


@dataclass(frozen=True, kw_only=True)
class ClassifiedRow:
    line: int
    raw: str
    values: Mapping[str, str]
    outcome: RowOutcome
    issues: tuple[ValidationIssue, ...]
    sku: str | None
    product: Mapping[str, object]
    changes: Mapping[str, Change]
    target: ExistingProduct | None
    needs_confirmation: bool
    superseded_by: int | None


@dataclass(frozen=True)
class Classification:
    rows: tuple[ClassifiedRow, ...]

    @property
    def counts(self) -> dict[str, int]:
        counts = {outcome.value: 0 for outcome in RowOutcome}
        for row in self.rows:
            counts[row.outcome.value] += 1
        return counts

    @property
    def warnings(self) -> list[tuple[int, ValidationIssue]]:
        return [
            (row.line, found)
            for row in self.rows
            for found in row.issues
            if found.severity is Severity.WARNING
        ]


@dataclass
class Draft:
    line: int
    raw: str
    values: dict[str, str]
    issues: list[ValidationIssue] = field(default_factory=list)
    product: dict[str, object] = field(default_factory=dict)
    outcome: RowOutcome | None = None
    target: ExistingProduct | None = None
    changes: dict[str, Change] = field(default_factory=dict)
    needs_confirmation: bool = False
    superseded_by: int | None = None

    @property
    def sku(self) -> str | None:
        sku = self.product.get("sku")
        return sku if isinstance(sku, str) else None

    @property
    def name(self) -> str | None:
        name = self.product.get("name")
        return name if isinstance(name, str) else None

    def add(self, found: ValidationIssue) -> None:
        self.issues.append(found)
        if found.severity is Severity.ERROR:
            self.outcome = RowOutcome.REJECTED

    def freeze(self) -> ClassifiedRow:
        return ClassifiedRow(
            line=self.line,
            raw=self.raw,
            values=dict(self.values),
            outcome=self.outcome or RowOutcome.CREATE,
            issues=tuple(self.issues),
            sku=self.sku,
            product=dict(self.product),
            changes=dict(self.changes),
            target=self.target,
            needs_confirmation=self.needs_confirmation,
            superseded_by=self.superseded_by,
        )


def outcome_of(issues: Sequence[ValidationIssue]) -> RowOutcome | None:
    severities = {found.severity for found in issues}
    if Severity.ERROR in severities:
        return RowOutcome.REJECTED
    if Severity.REVIEW in severities:
        return RowOutcome.NEEDS_REVIEW
    return None


def candidate_skus(header: Sequence[str], rows: Sequence[SourceRow]) -> set[str]:
    if "sku" not in header:
        return set()
    column = list(header).index("sku")
    return {
        row.fields[column].strip().upper()
        for row in rows
        if column < len(row.fields) and row.fields[column].strip()
    }


def draft_of(row: SourceRow, header: Sequence[str], policies: ImportPolicies) -> Draft:
    values = {
        name: row.fields[index] for index, name in enumerate(header) if index < len(row.fields)
    }
    draft = Draft(row.line, row.raw, values)
    if all(value.strip() == "" for value in row.fields):
        draft.outcome = RowOutcome.BLANK
        return draft
    if len(row.fields) != len(header):
        draft.add(
            error(
                "row",
                "wrong_field_count",
                f"This row has {len(row.fields)} values, but the header has {len(header)}.",
                expected=len(header),
                found=len(row.fields),
            )
        )
        return draft
    parsed = parse_fields({column: values.get(column, "") for column in COLUMNS}, policies)
    draft.issues.extend(parsed.issues)
    draft.product.update(parsed.values)
    draft.outcome = outcome_of(draft.issues)
    return draft


def lines_of(drafts: Sequence[Draft]) -> str:
    return ", ".join(str(draft.line) for draft in drafts)


def describe_same_product(drafts: Sequence[Draft], policies: ImportPolicies) -> bool:
    names = [draft.name for draft in drafts if draft.name is not None]
    return all(
        same_product(first, second, policies.sku_identity, policies.similarity_threshold)
        for first, second in combinations(names, 2)
    )


def resolve_duplicates(drafts: Sequence[Draft], policies: ImportPolicies) -> None:
    groups: dict[str, list[Draft]] = {}
    for draft in drafts:
        if draft.outcome is not RowOutcome.BLANK and draft.sku is not None:
            groups.setdefault(draft.sku, []).append(draft)
    for sku, group in groups.items():
        if len(group) < 2:
            continue
        lines = lines_of(group)
        if not describe_same_product(group, policies):
            for draft in group:
                draft.add(
                    error(
                        "sku",
                        "sku_conflict_in_file",
                        f"SKU {sku} is used for different products on lines {lines}.",
                        lines=lines,
                    )
                )
            continue
        if policies.duplicate_sku is DuplicateSkuPolicy.REJECT_ALL:
            for draft in group:
                draft.add(
                    error(
                        "sku",
                        "duplicate_sku_in_file",
                        f"SKU {sku} appears on lines {lines}; each SKU may appear only once.",
                        lines=lines,
                    )
                )
            continue
        winner = group[-1] if policies.duplicate_sku is DuplicateSkuPolicy.LAST_WINS else group[0]
        others = [draft for draft in group if draft is not winner]
        winner.issues.append(
            warning(
                "sku",
                "duplicate_sku_in_file",
                f"SKU {sku} also appears on line(s) {lines_of(others)}; this row is imported.",
                superseded=lines_of(others),
            )
        )
        for draft in others:
            draft.outcome = RowOutcome.SUPERSEDED
            draft.superseded_by = winner.line


def text_of(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def changes_between(target: ExistingProduct, product: Mapping[str, object]) -> dict[str, Change]:
    current: dict[str, object] = {
        "name": target.name,
        "description": target.description,
        "category": target.category,
        "price": target.price,
        "stock": target.stock,
        "weight_kg": target.weight_kg,
        "gift": target.gift,
    }
    changes: dict[str, Change] = {}
    for column, before in current.items():
        after = product[column]
        same = (
            str(before).casefold() == str(after).casefold()
            if column == "category"
            else before == after
        )
        if not same:
            changes[column] = Change(text_of(before), text_of(after))
    return changes


def compare_with_catalog(
    draft: Draft, existing: Mapping[str, ExistingProduct], policies: ImportPolicies
) -> None:
    sku = draft.sku
    if draft.outcome not in (None, RowOutcome.NEEDS_REVIEW) or sku is None or sku not in existing:
        return
    target = existing[sku]
    draft.target = target
    name = draft.name
    if name is not None and not same_product(
        target.name, name, policies.sku_identity, policies.similarity_threshold
    ):
        draft.add(
            error(
                "sku",
                "sku_belongs_to_different_product",
                f'SKU {sku} is "{target.name}" in the catalog, but this row describes "{name}". '
                "Use another SKU, or rename the product in the admin first.",
                catalog_name=target.name,
                row_name=name,
            )
        )
        return
    if policies.existing_sku is ExistingSkuPolicy.CREATE_ONLY:
        draft.add(
            error(
                "sku",
                "sku_already_exists",
                f"SKU {sku} already exists; this import only creates new products.",
            )
        )
        return
    if draft.outcome is RowOutcome.NEEDS_REVIEW:
        return
    draft.changes = changes_between(target, draft.product)
    if target.archived:
        draft.changes["status"] = Change("ARCHIVED", "ACTIVE")
        draft.issues.append(
            warning(
                "sku",
                "restores_archived_product",
                f"SKU {sku} belongs to an archived product; importing it restores the product.",
            )
        )
    if not draft.changes:
        draft.outcome = RowOutcome.UNCHANGED
        return
    draft.outcome = RowOutcome.UPDATE
    draft.needs_confirmation = policies.existing_sku is ExistingSkuPolicy.UPDATE_WITH_CONFIRMATION


def classify(
    header: Sequence[str],
    rows: Sequence[SourceRow],
    existing: Mapping[str, ExistingProduct],
    policies: ImportPolicies,
) -> Classification:
    drafts = [draft_of(row, header, policies) for row in rows]
    resolve_duplicates(drafts, policies)
    for draft in drafts:
        compare_with_catalog(draft, existing, policies)
    return Classification(tuple(draft.freeze() for draft in drafts))
