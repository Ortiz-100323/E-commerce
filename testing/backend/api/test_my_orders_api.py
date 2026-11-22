from uuid import uuid4

import httpx
from live import ACCOUNTS, ANTONIO, BEA, MY_ORDERS, ORDERS, live_api
from sqlalchemy.ext.asyncio import AsyncEngine

from checkout_support import add_product, count, order_body, stock_of
from problems import assert_problem

STALE = {"Cookie": "session=an-ended-or-invented-session"}


async def checkout(
    client: httpx.AsyncClient,
    headers: dict[str, str] | None = None,
    key: str | None = None,
    quantity: int = 1,
) -> httpx.Response:
    return await client.post(
        ORDERS,
        json=order_body(("RS-001", quantity)),
        headers={"Idempotency-Key": key or str(uuid4()), **(headers or {})},
    )


async def test_a_buyers_order_appears_in_my_orders_and_a_guest_order_does_not(
    engine: AsyncEngine,
) -> None:
    async with live_api(engine) as client:
        await add_product(client)
        guest = await checkout(client)
        mine = await checkout(client, BEA, quantity=2)
        listed = await client.get(MY_ORDERS, headers=BEA)

    assert guest.status_code == mine.status_code == 201
    body = listed.json()
    assert [item["id"] for item in body["items"]] == [mine.json()["id"]]
    assert (body["total"], body["page"], body["page_size"]) == (1, 1, 10)


async def test_my_orders_are_newest_first_and_paged(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        await add_product(client, stock=100)
        placed = [(await checkout(client, BEA)).json()["id"] for _ in range(12)]
        first = (await client.get(MY_ORDERS, headers=BEA)).json()
        second = (await client.get(MY_ORDERS, params={"page": 2}, headers=BEA)).json()

    shown = [item["id"] for item in first["items"] + second["items"]]
    assert sorted(shown) == sorted(placed)
    created = [item["created_at"] for item in first["items"] + second["items"]]
    assert created == sorted(created, reverse=True)
    assert (len(first["items"]), len(second["items"]), first["total"]) == (10, 2, 12)


async def test_a_buyer_sees_only_their_own_orders(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        await add_product(client)
        await checkout(client, BEA)
        client.cookies.clear()
        await client.post(
            ACCOUNTS,
            json={"name": "Carla", "email": "carla@example.com", "password": "a long password!"},
        )
        carla = await client.get(MY_ORDERS)

    assert carla.json()["items"] == []


async def test_my_orders_is_for_customers_only(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        admin = await client.get(MY_ORDERS, headers=ANTONIO)
        visitor = await client.get(MY_ORDERS)

    assert_problem(admin, 403, "buyer-required")
    assert_problem(visitor, 401, "authentication-required")


async def test_an_admin_cannot_buy(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        await add_product(client)
        response = await checkout(client, ANTONIO)

    assert_problem(response, 403, "admin-cannot-buy")
    assert await count(engine, "SELECT count(*) FROM orders") == 0


async def test_an_ended_session_at_checkout_charges_nothing(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        shoes = await add_product(client)
        response = await checkout(client, STALE)
        stock = await stock_of(client, shoes)

    assert_problem(response, 401, "authentication-required")
    assert await count(engine, "SELECT count(*) FROM orders") == 0
    assert stock == 10


async def test_the_same_key_for_the_same_buyer_buys_once(engine: AsyncEngine) -> None:
    key = str(uuid4())
    async with live_api(engine) as client:
        shoes = await add_product(client)
        first = await checkout(client, BEA, key)
        second = await checkout(client, BEA, key)
        stock = await stock_of(client, shoes)

    assert first.json()["id"] == second.json()["id"]
    assert second.headers["idempotent-replayed"] == "true"
    assert stock == 9


async def test_the_same_key_for_two_buyers_makes_two_orders(engine: AsyncEngine) -> None:
    key = str(uuid4())
    async with live_api(engine) as client:
        shoes = await add_product(client)
        bea = await checkout(client, BEA, key)
        client.cookies.clear()
        await client.post(
            ACCOUNTS,
            json={"name": "Carla", "email": "carla@example.com", "password": "a long password!"},
        )
        carla = await checkout(client, key=key)
        stock = await stock_of(client, shoes)

    assert bea.status_code == carla.status_code == 201
    assert bea.json()["id"] != carla.json()["id"]
    assert stock == 8
