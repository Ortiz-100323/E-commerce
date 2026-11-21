import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from ecommerce.catalog.domain.importing.policies import (
    CurrencySymbolPolicy,
    EmptyFieldPolicy,
    ImportPolicies,
    ZeroPricePolicy,
    ZeroWeightPolicy,
)
from ecommerce.catalog.domain.value_objects import (
    Category,
    Description,
    Price,
    ProductName,
    Sku,
    StockQuantity,
    Weight,
    has_control_characters,
)
from ecommerce.shared_kernel.domain.errors import (
    DomainValidationError,
    ParamValue,
    Severity,
    ValidationIssue,
)

COLUMNS = ("name", "sku", "description", "category", "price", "stock", "weight_kg")
REQUIRED_COLUMNS = ("name", "sku", "category", "price", "stock", "weight_kg")

NUMBER = re.compile(r"^[+-]?\d+(\.\d+)?$")
WHOLE = re.compile(r"^[+-]?\d+(\.0+)?$")
FOREIGN_CURRENCY = re.compile(r"^[€£¥₹₩₽¢]|[€£¥₹]$|^[A-Za-z]{3}\s*[+-]?\d|\d\s*[A-Za-z]{3}$")

IMPORT_CODES = {
    "required": "empty_required_field",
    "too_long": "value_too_long",
    "markup_not_allowed": "markup_in_name",
    "control_characters_not_allowed": "control_characters",
    "invalid_sku_format": "invalid_sku_format",
    "too_small": "negative_value",
    "too_large": "value_out_of_range",
    "value_out_of_range": "value_out_of_range",
    "too_many_decimal_places": "too_many_decimal_places",
    "not_a_number": "invalid_number",
}

LABELS = {
    "name": "name",
    "sku": "SKU",
    "description": "description",
    "category": "category",
    "price": "price",
    "stock": "stock",
    "weight_kg": "weight",
}


def warning(column: str, code: str, message: str, /, **params: ParamValue) -> ValidationIssue:
    return ValidationIssue(column, code, message, Severity.WARNING, params)


def review(column: str, code: str, message: str, /, **params: ParamValue) -> ValidationIssue:
    return ValidationIssue(column, code, message, Severity.REVIEW, params)


def error(column: str, code: str, message: str, /, **params: ParamValue) -> ValidationIssue:
    return ValidationIssue(column, code, message, Severity.ERROR, params)


def flagged(
    column: str, code: str, message: str, as_error: bool, /, **params: ParamValue
) -> ValidationIssue:
    return (error if as_error else review)(column, code, message, **params)


@dataclass
class ParsedFields:
    values: dict[str, object] = field(default_factory=dict)
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return all(column in self.values for column in COLUMNS)


def translated(column: str, failure: DomainValidationError) -> list[ValidationIssue]:
    return [
        error(column, IMPORT_CODES.get(found.code, "invalid_value"), found.message, **found.params)
        for found in failure.issues
    ]


def checked[V, T](column: str, factory: Callable[[V], T], raw: V, parsed: ParsedFields) -> T | None:
    try:
        return factory(raw)
    except DomainValidationError as failure:
        parsed.issues.extend(translated(column, failure))
        return None


def empty_issue(column: str, policies: ImportPolicies) -> ValidationIssue:
    return flagged(
        column,
        "empty_required_field",
        f"The {LABELS[column]} is empty.",
        policies.empty_field is EmptyFieldPolicy.REJECT,
    )


def parse_text(
    column: str, raw: str, factory: Callable[[str], object], policies: ImportPolicies
) -> tuple[object | None, list[ValidationIssue]]:
    parsed = ParsedFields()
    if column in REQUIRED_COLUMNS and raw.strip() == "":
        return None, [empty_issue(column, policies)]
    allowed = "\n" if column == "description" else ""
    if has_control_characters(raw, allowed):
        return None, [
            error(
                column,
                "control_characters",
                f"The {LABELS[column]} contains a tab, line break or other control character.",
            )
        ]
    value = checked(column, factory, raw, parsed)
    return value, parsed.issues


def parse_sku(raw: str, policies: ImportPolicies) -> tuple[str | None, list[ValidationIssue]]:
    value, issues = parse_text("sku", raw, Sku, policies)
    if not isinstance(value, Sku):
        return None, issues
    if value.value != raw.strip():
        issues.append(
            warning(
                "sku", "sku_normalized", f"The SKU was stored as {value.value}.", to=value.value
            )
        )
    return value.value, issues


def parse_name(raw: str, policies: ImportPolicies) -> tuple[str | None, list[ValidationIssue]]:
    value, issues = parse_text("name", raw, ProductName, policies)
    return (value.value if isinstance(value, ProductName) else None), issues


def parse_description(
    raw: str, policies: ImportPolicies
) -> tuple[str | None, list[ValidationIssue]]:
    value, issues = parse_text("description", raw, Description, policies)
    return (value.value if isinstance(value, Description) else None), issues


def parse_category(raw: str, policies: ImportPolicies) -> tuple[str | None, list[ValidationIssue]]:
    value, issues = parse_text("category", raw, Category, policies)
    return (value.value if isinstance(value, Category) else None), issues


def parse_price(
    raw: str, policies: ImportPolicies
) -> tuple[Decimal | None, bool, list[ValidationIssue]]:
    text = raw.strip()
    issues: list[ValidationIssue] = []
    if text == "":
        return None, False, [empty_issue("price", policies)]
    if text.casefold() == "free":
        text = "0"
    elif text.startswith("$"):
        if policies.currency_symbol is CurrencySymbolPolicy.REJECT:
            return (
                None,
                False,
                [
                    error(
                        "price",
                        "unsupported_currency",
                        "Write the price without a currency symbol.",
                    )
                ],
            )
        text = text[1:].strip()
        issues.append(
            warning("price", "currency_symbol_stripped", f"The $ was removed; stored {text}.")
        )
    if FOREIGN_CURRENCY.search(text):
        return (
            None,
            False,
            [error("price", "unsupported_currency", "Only US dollars are accepted.")],
        )
    if not NUMBER.match(text):
        return (
            None,
            False,
            [error("price", "invalid_number", "The price is not a number like 19.99.")],
        )
    parsed = ParsedFields()
    price = checked("price", Price.of, text, parsed)
    issues.extend(parsed.issues)
    if price is None:
        return None, False, issues
    if not price.is_zero:
        return price.amount, False, issues
    if policies.zero_price is ZeroPricePolicy.ACCEPT_AS_GIFT:
        issues.append(
            warning("price", "zero_price_accepted_as_gift", "A price of 0 was imported as a gift.")
        )
        return price.amount, True, issues
    issues.append(
        flagged(
            "price",
            "zero_price",
            "The price is 0. Confirm the product as a free gift, or correct the price.",
            policies.zero_price is ZeroPricePolicy.REJECT,
            suggestion="gift",
        )
    )
    return price.amount, False, issues


def parse_stock(raw: str, policies: ImportPolicies) -> tuple[int | None, list[ValidationIssue]]:
    text = raw.strip()
    if text == "":
        return None, [empty_issue("stock", policies)]
    if not NUMBER.match(text):
        return None, [error("stock", "invalid_number", "The stock is not a whole number.")]
    if not WHOLE.match(text):
        return None, [error("stock", "not_an_integer", "The stock must be a whole number.")]
    issues: list[ValidationIssue] = []
    if "." in text:
        issues.append(
            warning(
                "stock", "integer_normalized", f"The stock {text} was stored as a whole number."
            )
        )
    parsed = ParsedFields()
    stock = checked("stock", StockQuantity, int(Decimal(text)), parsed)
    issues.extend(parsed.issues)
    return (stock.value if stock is not None else None), issues


def parse_weight(
    raw: str, policies: ImportPolicies
) -> tuple[Decimal | None, list[ValidationIssue]]:
    text = raw.strip()
    if text == "":
        return None, [empty_issue("weight_kg", policies)]
    if not NUMBER.match(text):
        return None, [
            error("weight_kg", "invalid_number", "The weight is not a number like 0.250.")
        ]
    parsed = ParsedFields()
    weight = checked("weight_kg", Weight.of, text, parsed)
    if weight is None:
        return None, parsed.issues
    if weight.kg == 0 and policies.zero_weight is not ZeroWeightPolicy.ACCEPT:
        return weight.kg, [
            flagged(
                "weight_kg",
                "zero_weight",
                "The weight is 0. Confirm the product has no physical weight, or correct it.",
                policies.zero_weight is ZeroWeightPolicy.REJECT,
            )
        ]
    return weight.kg, []


def parse_fields(raw: Mapping[str, str], policies: ImportPolicies) -> ParsedFields:
    values = {column: raw.get(column, "").replace("\r\n", "\n") for column in COLUMNS}
    parsed = ParsedFields()

    def keep(column: str, result: tuple[object | None, list[ValidationIssue]]) -> None:
        value, issues = result
        parsed.issues.extend(issues)
        if value is not None:
            parsed.values[column] = value

    keep("name", parse_name(values["name"], policies))
    keep("sku", parse_sku(values["sku"], policies))
    keep("description", parse_description(values["description"], policies))
    keep("category", parse_category(values["category"], policies))
    price, gift, price_issues = parse_price(values["price"], policies)
    keep("price", (price, price_issues))
    keep("stock", parse_stock(values["stock"], policies))
    keep("weight_kg", parse_weight(values["weight_kg"], policies))
    parsed.values["gift"] = gift
    return parsed
