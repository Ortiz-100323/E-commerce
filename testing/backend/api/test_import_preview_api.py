from pathlib import Path
from typing import Any

import httpx
import pytest
from live import ANTONIO, IMPORT_PREVIEW, PRODUCTS, live_api, product_body
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.catalog.application.importing import MAX_FILE_BYTES
from ecommerce.catalog.domain.importing.policies import ImportPolicies, ZeroPricePolicy
from ecommerce.main import create_app
from fakes import dependencies_factory
from problems import assert_problem

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "csv"
SAMPLE = (FIXTURES / "sample-products.csv").read_bytes()
CSV = {"Content-Type": "text/csv"}
HEADER = b"name,sku,description,category,price,stock,weight_kg\n"


async def preview(
    client: httpx.AsyncClient, content: bytes, headers: dict[str, str] = CSV
) -> httpx.Response:
    return await client.post(IMPORT_PREVIEW, content=content, headers=headers)


async def stored(engine: AsyncEngine) -> tuple[int, int]:
    async with engine.connect() as connection:
        products = await connection.scalar(text("SELECT count(*) FROM products"))
        entries = await connection.scalar(text("SELECT count(*) FROM audit_log"))
    return int(products or 0), int(entries or 0)


def item(body: dict[str, Any], line: int) -> dict[str, Any]:
    found: dict[str, Any] = next(row for row in body["items"] if row["line"] == line)
    return found


async def test_the_sample_preview_matches_the_expected_report_and_stores_nothing(
    engine: AsyncEngine,
) -> None:
    async with live_api(engine) as client:
        response = await preview(client, SAMPLE)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"] == {
        "create": 84,
        "update": 0,
        "unchanged": 0,
        "needs_review": 6,
        "rejected": 2,
        "superseded": 3,
        "blank": 2,
    }
    assert (body["rows"], body["warnings"], body["size_bytes"]) == (97, 3, 8930)
    wallet = item(body, 4)
    assert wallet["issues"] == [
        {
            "field": "price",
            "code": "currency_symbol_stripped",
            "severity": "warning",
            "message": "The $ was removed; stored 29.99.",
            "params": {},
        }
    ]
    yoga = item(body, 7)
    assert (yoga["outcome"], yoga["sku"], yoga["name"]) == ("needs_review", "YM-015", "Yoga Mat")
    assert yoga["issues"][0]["params"] == {"suggestion": "gift"}
    assert item(body, 2)["superseded_by"] == 36
    assert item(body, 20)["raw"] == (
        "<script>alert('xss')</script>,XS-001,Totally normal product description,"
        "Electronics,19.99,100,0.1"
    )
    assert await stored(engine) == (0, 0)


async def test_existing_products_give_updates_unchanged_rows_and_conflicts(
    engine: AsyncEngine,
) -> None:
    content = HEADER + (
        b"Running Shoes,RS-001,Lightweight shoes.,Sports,94.99,10,0.8\n"
        b"Coffee Beans,CB-010,Roasted,Food,18.75,500,1.0\n"
        b"Wireless Mouse,WM-042,Ergonomic,Electronics,29.99,75,0.12\n"
        b"Brand New,NEW-1,Fresh,Misc,5.00,1,0.1\n"
    )
    async with live_api(engine) as client:
        await client.post(PRODUCTS, json=product_body(), headers=ANTONIO)
        await client.post(
            PRODUCTS, json=product_body(sku="CB-010", name="Yoga Mat"), headers=ANTONIO
        )
        mouse = await client.post(
            PRODUCTS,
            json=product_body(
                sku="WM-042",
                name="Wireless Mouse",
                description="Ergonomic",
                category="Electronics",
                price="29.99",
                stock=75,
                weight_kg="0.12",
            ),
            headers=ANTONIO,
        )
        await client.delete(f"{PRODUCTS}/{mouse.json()['id']}", headers=ANTONIO)
        before = await stored(engine)
        response = await preview(client, content)

    body = response.json()
    assert [row["outcome"] for row in body["items"]] == ["update", "rejected", "update", "create"]
    shoes = body["items"][0]
    assert shoes["changes"] == {"price": {"before": "89.99", "after": "94.99"}}
    assert shoes["needs_confirmation"] is True
    assert shoes["target_product_id"] is not None
    assert [issue["code"] for issue in body["items"][1]["issues"]] == [
        "sku_belongs_to_different_product"
    ]
    mouse_row = body["items"][2]
    assert mouse_row["changes"] == {"status": {"before": "ARCHIVED", "after": "ACTIVE"}}
    assert [issue["code"] for issue in mouse_row["issues"]] == ["restores_archived_product"]
    assert await stored(engine) == before


async def test_previewing_the_same_file_twice_gives_the_same_report(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        first = await preview(client, SAMPLE)
        second = await preview(client, SAMPLE)

    assert first.json() == second.json()


async def test_the_policies_given_to_the_app_change_the_report(engine: AsyncEngine) -> None:
    async with live_api(
        engine, policies=ImportPolicies(zero_price=ZeroPricePolicy.REJECT)
    ) as client:
        response = await preview(client, SAMPLE)

    summary = response.json()["summary"]
    assert (summary["rejected"], summary["needs_review"]) == (4, 4)


async def test_an_oversized_file_is_413_and_stores_nothing(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        response = await preview(client, HEADER + b"x" * MAX_FILE_BYTES)

    body = assert_problem(response, 413, "payload-too-large")
    assert body["max_bytes"] == MAX_FILE_BYTES
    assert await stored(engine) == (0, 0)


@pytest.mark.parametrize("content_type", ["application/json", "text/plain"])
async def test_a_file_that_is_not_csv_is_415(engine: AsyncEngine, content_type: str) -> None:
    async with live_api(engine) as client:
        response = await preview(client, SAMPLE, {"Content-Type": content_type})

    assert_problem(response, 415, "unsupported-media-type")


@pytest.mark.parametrize(
    ("content", "code"),
    [
        ((FIXTURES / "not-utf8.csv").read_bytes(), "invalid_encoding"),
        (b"", "empty_file"),
        ((FIXTURES / "missing-column.csv").read_bytes(), "missing_columns"),
        ((FIXTURES / "duplicate-column.csv").read_bytes(), "duplicate_columns"),
        ((FIXTURES / "unclosed-quote.csv").read_bytes(), "malformed_csv"),
    ],
)
async def test_an_unreadable_file_is_422_on_the_file_and_stores_nothing(
    engine: AsyncEngine, content: bytes, code: str
) -> None:
    async with live_api(engine) as client:
        response = await preview(client, content)

    body = assert_problem(response, 422, "validation-error")
    [error] = body["errors"]
    assert (error["location"], error["field"], error["code"]) == ("body", "file", code)
    assert error["message"]
    assert await stored(engine) == (0, 0)


async def test_too_many_rows_is_422_with_the_limit(engine: AsyncEngine) -> None:
    async with live_api(engine, policies=ImportPolicies(max_rows=50)) as client:
        response = await preview(client, SAMPLE)

    body = assert_problem(response, 422, "validation-error")
    assert body["errors"][0]["code"] == "too_many_rows"
    assert body["errors"][0]["params"] == {"max_rows": 50}


def test_swagger_offers_a_file_picker_for_the_csv() -> None:
    openapi = create_app(dependencies_factory()).openapi()
    operation = openapi["paths"]["/api/v1/imports/preview"]["post"]

    assert operation["requestBody"]["content"]["text/csv"]["schema"] == {
        "type": "string",
        "format": "binary",
    }
    assert {"413", "415", "422"} <= set(operation["responses"])
