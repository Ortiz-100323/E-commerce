from collections.abc import Iterator
from typing import Any

from ecommerce.main import create_app
from ecommerce.shared_kernel.api.validation import PYDANTIC_CODES
from fakes import dependencies_factory

TYPE_ERRORS = {
    "string": {"string_type"},
    "integer": {"int_type", "int_parsing", "int_from_float"},
    "number": {"float_type", "float_parsing", "decimal_type", "decimal_parsing"},
    "boolean": {"bool_type", "bool_parsing"},
    "array": {"list_type"},
    "object": {"model_type", "dict_type"},
}
KEYWORD_ERRORS = {
    "maxLength": {"string_too_long"},
    "minLength": {"string_too_short"},
    "pattern": {"string_pattern_mismatch"},
    "minimum": {"greater_than_equal"},
    "maximum": {"less_than_equal"},
    "exclusiveMinimum": {"greater_than"},
    "exclusiveMaximum": {"less_than"},
    "maxItems": {"too_long"},
    "minItems": {"too_short"},
    "enum": {"enum", "literal_error"},
    "const": {"literal_error"},
    "required": {"missing"},
}
FORMAT_ERRORS = {
    "uuid": {"uuid_type", "uuid_parsing"},
    "date-time": {"datetime_type", "datetime_parsing", "datetime_from_date_parsing"},
    "date": {"date_type", "date_parsing"},
}


def resolve(schema: dict[str, Any], components: dict[str, Any]) -> dict[str, Any]:
    reference = schema.get("$ref")
    if reference is None:
        return schema
    resolved: dict[str, Any] = components[reference.rsplit("/", 1)[-1]]
    return resolved


def walk(schema: dict[str, Any], components: dict[str, Any], seen: set[str]) -> Iterator[str]:
    reference = schema.get("$ref")
    if reference is not None:
        if reference in seen:
            return
        seen = seen | {reference}
    schema = resolve(schema, components)
    yield from TYPE_ERRORS.get(schema.get("type", ""), set())
    yield from FORMAT_ERRORS.get(schema.get("format", ""), set())
    for keyword, errors in KEYWORD_ERRORS.items():
        if keyword in schema:
            yield from errors
    if schema.get("additionalProperties") is False:
        yield "extra_forbidden"
    children = [*schema.get("properties", {}).values()]
    children += [schema["items"]] if isinstance(schema.get("items"), dict) else []
    for combinator in ("anyOf", "oneOf", "allOf"):
        children += schema.get(combinator, [])
    for child in children:
        yield from walk(child, components, seen)


def request_schemas(openapi: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for path_item in openapi["paths"].values():
        for operation in path_item.values():
            for parameter in operation.get("parameters", []):
                yield parameter["schema"]
                if parameter.get("required"):
                    yield {"required": [parameter["name"]]}
            body = operation.get("requestBody", {}).get("content", {})
            for media in body.values():
                yield media["schema"]


def test_every_pydantic_error_our_requests_can_raise_has_a_stable_code() -> None:
    openapi = create_app(dependencies_factory()).openapi()
    components = openapi.get("components", {}).get("schemas", {})

    possible = {
        error for schema in request_schemas(openapi) for error in walk(schema, components, set())
    }

    assert possible, "no request schemas were found"
    assert sorted(possible - PYDANTIC_CODES.keys()) == []
