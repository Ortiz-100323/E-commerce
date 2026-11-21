from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from live import ANTONIO, MARIA, PRODUCTS, live_api, product_body, update_body
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.main import create_app
from fakes import FIXED_NOW, SequenceClock, dependencies_factory
from problems import assert_problem

UNKNOWN = "00000000-0000-4000-8000-000000000099"
LATER = FIXED_NOW + timedelta(hours=1)


def url(product_id: str, suffix: str = "") -> str:
    return f"{PRODUCTS}/{product_id}{suffix}"


async def create(client: httpx.AsyncClient, **overrides: Any) -> dict[str, Any]:
    response = await client.post(PRODUCTS, json=product_body(**overrides), headers=ANTONIO)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def history_events(client: httpx.AsyncClient, product_id: str) -> list[tuple[str, str]]:
    response = await client.get(url(product_id, "/history"))
    assert response.status_code == 200, response.text
    return [(entry["event"], entry["actor"]) for entry in response.json()["entries"]]


def field_codes(body: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(error["location"], error["field"], error["code"]) for error in body["errors"]]


async def test_full_crud_over_http(engine: AsyncEngine) -> None:
    async with live_api(engine, SequenceClock(FIXED_NOW, LATER)) as client:
        created = await client.post(PRODUCTS, json=product_body(), headers=ANTONIO)
        assert created.status_code == 201, created.text
        product = created.json()
        product_id = product["id"]
        assert created.headers["location"] == url(product_id)

        read = await client.get(url(product_id))
        updated = await client.put(
            url(product_id),
            json=update_body(1, name="Trail Shoes", price="119.5", stock=3),
            headers=MARIA,
        )
        archived = await client.delete(url(product_id), headers=MARIA)
        read_archived = await client.get(url(product_id))
        restored = await client.post(url(product_id, "/restore"), headers=ANTONIO)
        history = await history_events(client, product_id)

    assert read.json() == product
    assert {key: product[key] for key in ("sku", "price", "currency", "weight_kg", "tags")} == {
        "sku": "RS-001",
        "price": "89.99",
        "currency": "USD",
        "weight_kg": "0.800",
        "tags": [],
    }
    assert (product["version"], product["status"], product["is_sellable"]) == (1, "ACTIVE", True)
    assert updated.status_code == 200, updated.text
    assert (updated.json()["name"], updated.json()["price"], updated.json()["version"]) == (
        "Trail Shoes",
        "119.50",
        2,
    )
    assert archived.status_code == 200
    assert (archived.json()["status"], archived.json()["is_sellable"]) == ("ARCHIVED", False)
    assert read_archived.json()["status"] == "ARCHIVED"
    assert (restored.json()["status"], restored.json()["version"]) == ("ACTIVE", 4)
    assert history == [
        ("product.created", "Antonio"),
        ("product.changed", "Maria"),
        ("product.archived", "Maria"),
        ("product.restored", "Antonio"),
    ]


async def test_an_archived_product_is_hidden_from_the_default_search(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        product = await create(client)
        before = (await client.get(PRODUCTS)).json()
        await client.delete(url(product["id"]), headers=MARIA)
        default = (await client.get(PRODUCTS)).json()
        archived = (await client.get(PRODUCTS, params={"status": "ARCHIVED"})).json()

    assert [item["sku"] for item in before["items"]] == ["RS-001"]
    assert (default["items"], default["total"]) == ([], 0)
    assert [item["sku"] for item in archived["items"]] == ["RS-001"]


async def test_a_price_of_zero_without_the_gift_flag_is_refused(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        response = await client.post(PRODUCTS, json=product_body(price="0"), headers=ANTONIO)
        listed = (await client.get(PRODUCTS)).json()

    body = assert_problem(response, 422, "validation-error")
    assert field_codes(body) == [("body", "price", "zero_price_requires_gift")]
    assert listed["total"] == 0


async def test_a_price_of_zero_confirmed_as_a_gift_is_accepted(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        product = await create(client, price="0", gift=True)

    assert (product["price"], product["gift"], product["tags"]) == ("0.00", True, ["GIFT"])


async def test_removing_the_gift_flag_from_a_free_product_is_refused(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        product = await create(client, price="0", gift=True)
        response = await client.put(
            url(product["id"]), json=update_body(1, price="0", gift=False), headers=MARIA
        )

    body = assert_problem(response, 422, "validation-error")
    assert [code for _, _, code in field_codes(body)] == ["zero_price_requires_gift"]


async def test_a_put_with_a_stale_version_is_a_conflict(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        product = await create(client)
        first = await client.put(
            url(product["id"]), json=update_body(1, name="Trail Shoes"), headers=MARIA
        )
        second = await client.put(
            url(product["id"]), json=update_body(1, price="79.99"), headers=ANTONIO
        )
        stored = (await client.get(url(product["id"]))).json()
        history = await history_events(client, product["id"])

    assert first.status_code == 200
    body = assert_problem(second, 409, "version-conflict")
    assert body["current_version"] == 2
    assert body["detail"] == "You edited version 1, but the product is now at version 2."
    assert (stored["name"], stored["price"], stored["version"]) == ("Trail Shoes", "89.99", 2)
    assert history == [("product.created", "Antonio"), ("product.changed", "Maria")]


async def test_a_duplicate_sku_is_a_conflict_in_any_letter_case(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        await create(client, sku="RS-001")
        response = await client.post(
            PRODUCTS, json=product_body(sku="rs-001", name="Other"), headers=MARIA
        )
        listed = (await client.get(PRODUCTS)).json()

    body = assert_problem(response, 409, "duplicate-sku")
    assert (body["sku"], body["detail"]) == ("RS-001", "SKU RS-001 is already taken.")
    assert listed["total"] == 1


async def test_the_same_create_sent_twice_stores_one_product(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        first = await client.post(PRODUCTS, json=product_body(), headers=ANTONIO)
        second = await client.post(PRODUCTS, json=product_body(), headers=ANTONIO)
        listed = (await client.get(PRODUCTS)).json()
        history = await history_events(client, first.json()["id"])

    assert first.status_code == 201
    assert_problem(second, 409, "duplicate-sku")
    assert listed["total"] == 1
    assert history == [("product.created", "Antonio")]


async def test_a_put_repeated_after_it_succeeded_returns_the_current_product(
    engine: AsyncEngine,
) -> None:
    async with live_api(engine) as client:
        product = await create(client)
        body = update_body(1, name="Trail Shoes")
        first = await client.put(url(product["id"]), json=body, headers=MARIA)
        repeated = await client.put(url(product["id"]), json=body, headers=MARIA)
        history = await history_events(client, product["id"])

    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == first.json()
    assert repeated.json()["version"] == 2
    assert history == [("product.created", "Antonio"), ("product.changed", "Maria")]


async def test_a_put_that_changes_nothing_keeps_the_version(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        product = await create(client)
        response = await client.put(url(product["id"]), json=update_body(1), headers=MARIA)
        history = await history_events(client, product["id"])

    assert response.status_code == 200
    assert response.json() == product
    assert history == [("product.created", "Antonio")]


async def test_archiving_twice_and_restoring_an_active_product_change_nothing_more(
    engine: AsyncEngine,
) -> None:
    async with live_api(engine) as client:
        product = await create(client)
        restored_active = await client.post(url(product["id"], "/restore"), headers=MARIA)
        first = await client.delete(url(product["id"]), headers=MARIA)
        second = await client.delete(url(product["id"]), headers=MARIA)
        history = await history_events(client, product["id"])

    assert restored_active.json() == product
    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json() == first.json()
    assert first.json()["version"] == 2
    assert history == [("product.created", "Antonio"), ("product.archived", "Maria")]


async def test_two_admins_saving_the_same_version_keep_only_the_first_change(
    engine: AsyncEngine,
) -> None:
    async with live_api(engine) as client:
        product = await create(client)
        maria = await client.put(url(product["id"]), json=update_body(1, stock=5), headers=MARIA)
        antonio = await client.put(
            url(product["id"]), json=update_body(1, stock=50), headers=ANTONIO
        )
        stored = (await client.get(url(product["id"]))).json()

    assert maria.status_code == 200
    assert_problem(antonio, 409, "version-conflict")
    assert stored["stock"] == 5


@pytest.mark.parametrize(
    ("method", "suffix"),
    [("GET", ""), ("PUT", ""), ("DELETE", ""), ("POST", "/restore"), ("GET", "/history")],
)
async def test_an_unknown_product_is_404_on_every_endpoint(
    engine: AsyncEngine, method: str, suffix: str
) -> None:
    body = update_body(1) if method == "PUT" else None
    async with live_api(engine) as client:
        response = await client.request(method, url(UNKNOWN, suffix), json=body, headers=MARIA)

    problem = assert_problem(response, 404, "not-found")
    assert problem["detail"] == "Product not found."


@pytest.mark.parametrize(
    ("method", "suffix"),
    [("GET", ""), ("PUT", ""), ("DELETE", ""), ("POST", "/restore"), ("GET", "/history")],
)
async def test_an_id_that_is_not_a_uuid_is_422(
    engine: AsyncEngine, method: str, suffix: str
) -> None:
    body = update_body(1) if method == "PUT" else None
    async with live_api(engine) as client:
        response = await client.request(method, url("abc", suffix), json=body, headers=MARIA)

    problem = assert_problem(response, 422, "validation-error")
    assert ("path", "product_id", "not_a_uuid") in field_codes(problem)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"colour": "red"}, [("body", "colour", "unknown_field")]),
        (
            {"name": None, "price": None},
            [("body", "name", "required"), ("body", "price", "required")],
        ),
        ({"stock": "10"}, [("body", "stock", "not_an_integer")]),
        ({"stock": 1.5}, [("body", "stock", "not_an_integer")]),
        ({"stock": True}, [("body", "stock", "not_an_integer")]),
        ({"gift": "yes"}, [("body", "gift", "not_a_boolean")]),
        ({"price": "abc"}, [("body", "price", "not_a_number")]),
        ({"price": "NaN"}, [("body", "price", "not_a_number")]),
        ({"weight_kg": "Infinity"}, [("body", "weight_kg", "not_a_number")]),
        ({"price": "1.234"}, [("body", "price", "too_many_decimal_places")]),
        ({"stock": -1}, [("body", "stock", "too_small")]),
        ({"name": "x" * 10_001}, [("body", "name", "too_long")]),
    ],
)
async def test_bad_create_bodies_are_422_with_a_code_per_field(
    engine: AsyncEngine, overrides: dict[str, Any], expected: list[tuple[str, str, str]]
) -> None:
    async with live_api(engine) as client:
        response = await client.post(PRODUCTS, json=product_body(**overrides), headers=ANTONIO)

    body = assert_problem(response, 422, "validation-error")
    assert field_codes(body) == expected


async def test_every_broken_rule_is_reported_at_once(engine: AsyncEngine) -> None:
    body = product_body(sku="bad sku!", name="<b>Shoes</b>", price="-1", weight_kg="0.0001")
    async with live_api(engine) as client:
        response = await client.post(PRODUCTS, json=body, headers=ANTONIO)

    problem = assert_problem(response, 422, "validation-error")
    assert {(field, code) for _, field, code in field_codes(problem)} == {
        ("sku", "invalid_sku_format"),
        ("name", "markup_not_allowed"),
        ("price", "too_small"),
        ("weight_kg", "too_many_decimal_places"),
    }


async def test_the_sku_cannot_be_changed_by_a_put(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        product = await create(client)
        response = await client.put(
            url(product["id"]), json={**update_body(1), "sku": "NEW-1"}, headers=MARIA
        )

    body = assert_problem(response, 422, "validation-error")
    assert field_codes(body) == [("body", "sku", "unknown_field")]


@pytest.mark.parametrize("method", ["POST", "PUT"])
async def test_a_body_that_is_not_json_is_400(engine: AsyncEngine, method: str) -> None:
    target = PRODUCTS if method == "POST" else url(UNKNOWN)
    async with live_api(engine) as client:
        response = await client.request(
            method,
            target,
            content=b'{"name":',
            headers={**MARIA, "content-type": "application/json"},
        )

    assert_problem(response, 400, "malformed-request")


async def test_a_change_without_an_actor_is_422_and_stores_nothing(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        response = await client.post(PRODUCTS, json=product_body())
        listed = (await client.get(PRODUCTS)).json()

    body = assert_problem(response, 422, "validation-error")
    assert field_codes(body) == [("header", "X-Actor-Name", "required")]
    assert listed["total"] == 0


class UnreachableCatalog:
    def __call__(self, actor: object = None) -> Any:
        raise OperationalError("SELECT 1", {}, ConnectionError("the database is down"))


def test_the_database_being_down_is_503_with_retry_after() -> None:
    app = create_app(dependencies_factory(catalog=UnreachableCatalog()))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(url(UNKNOWN))

    assert_problem(response, 503, "service-unavailable")
    assert response.headers["retry-after"] == "1"


async def test_created_at_comes_from_the_clock(engine: AsyncEngine) -> None:
    moment = datetime(2026, 11, 21, 14, 2, 11, tzinfo=UTC)
    async with live_api(engine, SequenceClock(moment)) as client:
        product = await create(client)

    assert product["created_at"] == "2026-11-21T14:02:11Z"
