from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import httpx
import pytest
from live import ANTONIO, CATEGORIES, PRODUCTS, live_api, product_body
from sqlalchemy.ext.asyncio import AsyncEngine

from fakes import FIXED_NOW, SequenceClock
from problems import assert_problem

CATALOG = [
    {"sku": "RS-001", "name": "Running Shoes", "category": "Sports", "price": "89.99"},
    {"sku": "TS-002", "name": "Trail Shoes", "category": "Sports", "price": "120.00", "stock": 0},
    {
        "sku": "GK-088",
        "name": "Gaming Keyboard",
        "category": "Electronics",
        "price": "129.99",
        "stock": 45,
        "description": "Mechanical, 100% RGB.",
    },
    {"sku": "GC-001", "name": "Gift Card", "category": "Gifts", "price": "0", "gift": True},
    {"sku": "SW-1", "name": "Smart_Watch", "category": "electronics", "price": "199.99"},
]


@pytest.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    moments = [FIXED_NOW + timedelta(minutes=minute) for minute in range(len(CATALOG) + 1)]
    async with live_api(engine, SequenceClock(*moments)) as api:
        ids = {}
        for item in CATALOG:
            body = product_body(**{"description": "", "stock": 10, **item})
            response = await api.post(PRODUCTS, json=body, headers=ANTONIO)
            assert response.status_code == 201, response.text
            ids[item["sku"]] = response.json()["id"]
        archived = await api.delete(f"{PRODUCTS}/{ids['SW-1']}", headers=ANTONIO)
        assert archived.status_code == 200
        yield api


async def skus(client: httpx.AsyncClient, **params: Any) -> list[str]:
    response = await client.get(PRODUCTS, params=params, headers=ANTONIO)
    assert response.status_code == 200, response.text
    return [item["sku"] for item in response.json()["items"]]


async def test_the_default_search_lists_active_products_by_name(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(PRODUCTS)

    body = response.json()
    assert [item["name"] for item in body["items"]] == [
        "Gaming Keyboard",
        "Gift Card",
        "Running Shoes",
        "Trail Shoes",
    ]
    assert (body["total"], body["page"], body["page_size"]) == (4, 1, 20)
    assert body["items"][2]["price"] == "89.99"
    assert body["items"][2]["currency"] == "USD"


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("shoes", ["RS-001", "TS-002"]),
        ("  SHOES  ", ["RS-001", "TS-002"]),
        ("gk-088", ["GK-088"]),
        ("mechanical", ["GK-088"]),
        ("100%", ["GK-088"]),
        ("%", ["GK-088"]),
        ("_", []),
        ("\\", []),
        ("", ["GK-088", "GC-001", "RS-001", "TS-002"]),
        ("no such thing", []),
    ],
)
async def test_q_searches_name_sku_and_description_literally(
    client: httpx.AsyncClient, q: str, expected: list[str]
) -> None:
    assert await skus(client, q=q) == expected


async def test_an_underscore_matches_only_a_real_underscore(client: httpx.AsyncClient) -> None:
    assert await skus(client, q="_", status="ALL") == ["SW-1"]
    assert await skus(client, q="t_", status="ALL") == ["SW-1"]


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"category": "sports"}, ["RS-001", "TS-002"]),
        ({"category": "ELECTRONICS", "status": "ALL"}, ["GK-088", "SW-1"]),
        ({"min_price": "100"}, ["GK-088", "TS-002"]),
        ({"max_price": "0"}, ["GC-001"]),
        ({"min_price": "89.99", "max_price": "89.99"}, ["RS-001"]),
        ({"in_stock": "true"}, ["GK-088", "GC-001", "RS-001"]),
        ({"in_stock": "false"}, ["TS-002"]),
        ({"tag": "GIFT"}, ["GC-001"]),
        ({"status": "ARCHIVED"}, ["SW-1"]),
        ({"status": "ALL"}, ["GK-088", "GC-001", "RS-001", "SW-1", "TS-002"]),
        ({"q": "shoes", "category": "Sports", "in_stock": "true"}, ["RS-001"]),
    ],
)
async def test_every_filter_narrows_the_results(
    client: httpx.AsyncClient, params: dict[str, str], expected: list[str]
) -> None:
    assert await skus(client, **params) == expected


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        ("name", ["GK-088", "GC-001", "RS-001", "TS-002"]),
        ("-name", ["TS-002", "RS-001", "GC-001", "GK-088"]),
        ("price", ["GC-001", "RS-001", "TS-002", "GK-088"]),
        ("-price", ["GK-088", "TS-002", "RS-001", "GC-001"]),
        ("created_at", ["RS-001", "TS-002", "GK-088", "GC-001"]),
        ("-created_at", ["GC-001", "GK-088", "TS-002", "RS-001"]),
    ],
)
async def test_results_can_be_sorted(
    client: httpx.AsyncClient, sort: str, expected: list[str]
) -> None:
    assert await skus(client, sort=sort) == expected


async def test_pages_split_the_results_without_overlap(client: httpx.AsyncClient) -> None:
    pages = [
        (await client.get(PRODUCTS, params={"page": page, "page_size": 3})).json()
        for page in (1, 2, 3)
    ]

    assert [[item["sku"] for item in page["items"]] for page in pages] == [
        ["GK-088", "GC-001", "RS-001"],
        ["TS-002"],
        [],
    ]
    assert {page["total"] for page in pages} == {4}
    assert [page["page"] for page in pages] == [1, 2, 3]


async def test_categories_lists_active_categories_once_each(client: httpx.AsyncClient) -> None:
    response = await client.get(CATEGORIES)

    assert response.status_code == 200
    assert response.json() == {"items": ["Electronics", "Gifts", "Sports"]}


@pytest.mark.parametrize(
    ("params", "field", "code"),
    [
        ({"page_size": "0"}, "page_size", "too_small"),
        ({"page_size": "101"}, "page_size", "too_large"),
        ({"page": "0"}, "page", "too_small"),
        ({"page": "abc"}, "page", "not_an_integer"),
        ({"min_price": "-1"}, "min_price", "too_small"),
        ({"max_price": "abc"}, "max_price", "not_a_number"),
        ({"sort": "colour"}, "sort", "not_allowed"),
        ({"status": "DELETED"}, "status", "not_allowed"),
        ({"tag": "SALE"}, "tag", "not_allowed"),
        ({"in_stock": "maybe"}, "in_stock", "not_a_boolean"),
        ({"q": "x" * 201}, "q", "too_long"),
        ({"min_price": "10", "max_price": "5"}, "max_price", "invalid_range"),
    ],
)
async def test_bad_search_parameters_are_422_in_the_query(
    client: httpx.AsyncClient, params: dict[str, str], field: str, code: str
) -> None:
    response = await client.get(PRODUCTS, params=params, headers=ANTONIO)

    body = assert_problem(response, 422, "validation-error")
    assert [(error["location"], error["field"], error["code"]) for error in body["errors"]] == [
        ("query", field, code)
    ]
