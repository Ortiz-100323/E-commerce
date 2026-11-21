import dataclasses
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ecommerce.shared_kernel.domain.errors import ParamValue, ValidationIssue

FALLBACK_CODE = "invalid"
DROPPED_CONTEXT_KEYS = frozenset({"error"})

PYDANTIC_CODES: Mapping[str, str] = {
    "missing": "required",
    "extra_forbidden": "unknown_field",
    "string_type": "not_a_string",
    "string_too_long": "too_long",
    "string_too_short": "too_short",
    "string_pattern_mismatch": "invalid_format",
    "int_type": "not_an_integer",
    "int_parsing": "not_an_integer",
    "int_from_float": "not_an_integer",
    "float_type": "not_a_number",
    "float_parsing": "not_a_number",
    "decimal_type": "not_a_number",
    "decimal_parsing": "not_a_number",
    "decimal_max_places": "too_many_decimal_places",
    "decimal_max_digits": "too_many_digits",
    "decimal_whole_digits": "too_many_digits",
    "finite_number": "not_a_number",
    "greater_than": "too_small",
    "greater_than_equal": "too_small",
    "less_than": "too_large",
    "less_than_equal": "too_large",
    "bool_type": "not_a_boolean",
    "bool_parsing": "not_a_boolean",
    "uuid_type": "not_a_uuid",
    "uuid_parsing": "not_a_uuid",
    "datetime_type": "not_a_datetime",
    "datetime_parsing": "not_a_datetime",
    "datetime_from_date_parsing": "not_a_datetime",
    "date_type": "not_a_date",
    "date_parsing": "not_a_date",
    "enum": "not_allowed",
    "literal_error": "not_allowed",
    "list_type": "not_a_list",
    "too_long": "too_many_items",
    "too_short": "too_few_items",
    "dict_type": "not_an_object",
    "model_type": "not_an_object",
    "model_attributes_type": "not_an_object",
    "value_error": "invalid_value",
}


@dataclass(frozen=True)
class FieldError:
    location: str
    field: str
    code: str
    message: str
    params: Mapping[str, ParamValue] = dataclasses.field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "location": self.location,
            "field": self.field,
            "code": self.code,
            "message": self.message,
            "params": dict(self.params),
        }


def split_location(loc: Sequence[str | int]) -> tuple[str, str]:
    if not loc:
        return "body", ""
    location, *rest = loc
    path = ""
    for part in rest:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}" if path else part
    return str(location), path


def safe_params(context: Mapping[str, Any] | None) -> dict[str, ParamValue]:
    params: dict[str, ParamValue] = {}
    for key, value in (context or {}).items():
        if key in DROPPED_CONTEXT_KEYS:
            continue
        if isinstance(value, Decimal):
            params[key] = str(value)
        elif isinstance(value, str | int | float | bool):
            params[key] = value
    return params


def field_error_from_pydantic(error: Mapping[str, Any]) -> FieldError:
    location, path = split_location(error.get("loc", ()))
    error_type = str(error.get("type", ""))
    return FieldError(
        location=location,
        field=path,
        code=PYDANTIC_CODES.get(error_type, FALLBACK_CODE),
        message=str(error.get("msg", "The value is not valid.")),
        params=safe_params(error.get("ctx")),
    )


def field_error_from_issue(issue: ValidationIssue, location: str = "body") -> FieldError:
    return FieldError(
        location=location,
        field=issue.field,
        code=issue.code,
        message=issue.message,
        params=dict(issue.params),
    )


def describe(errors: Sequence[FieldError]) -> str:
    count = len(errors)
    return "1 field is not valid." if count == 1 else f"{count} fields are not valid."


class InvalidParameters(Exception):
    def __init__(self, location: str, issues: Iterable[ValidationIssue]) -> None:
        self.location = location
        self.issues = tuple(issues)
        super().__init__(f"{len(self.issues)} {location} issue(s)")
