from typing import Any
from uuid import uuid4

import httpx
from live import ADMIN_ORDERS, ANTONIO, BEA, ORDERS, live_api
from sqlalchemy.ext.asyncio import AsyncEngine

from checkout_support import add_product, count, order_body, stock_of
from problems import assert_problem

DECLINED = "4000 0000 0000 0002"


async def checkout(
    client: httpx.AsyncClient,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> httpx.Response:
    return await client.post(
        ORDERS,
        json=body or order_body(("RS-001", 1)),
        headers={"Idempotency-Key": str(uuid4()), **(headers or {})},
    )


class TestAdminsDoNotShop:
    async def test_an_admins_checkout_is_refused_and_creates_nothing(
        self, engine: AsyncEngine
    ) -> None:
        async with live_api(engine) as client:
            shoes = await add_product(client)
            responses = [await checkout(client, ANTONIO) for _ in range(3)]
            stock = await stock_of(client, shoes)

        for response in responses:
            body = assert_problem(response, 403, "admin-cannot-buy")
            assert "Log out, or use a customer account" in body["title"]
        assert await count(engine, "SELECT count(*) FROM orders") == 0
        assert await count(engine, "SELECT count(*) FROM idempotency_keys") == 0
        assert stock == 10

    async def test_guests_and_customers_still_buy(self, engine: AsyncEngine) -> None:
        async with live_api(engine) as client:
            await add_product(client)
            guest = await checkout(client)
            customer = await checkout(client, BEA)

        assert guest.status_code == customer.status_code == 201


class TestAdminOrders:
    async def test_lists_every_order_newest_first_with_guest_or_account(
        self, engine: AsyncEngine
    ) -> None:
        async with live_api(engine) as client:
            await add_product(client, stock=50)
            guest = (await checkout(client)).json()
            customer = (await checkout(client, BEA)).json()
            listed = await client.get(ADMIN_ORDERS, headers=ANTONIO)

        body = listed.json()
        assert (body["total"], body["page"], body["page_size"]) == (2, 1, 20)
        by_id = {item["id"]: item for item in body["items"]}
        assert by_id[guest["id"]]["customer_account"] is False
        assert by_id[customer["id"]]["customer_account"] is True
        created = [item["created_at"] for item in body["items"]]
        assert created == sorted(created, reverse=True)

    async def test_searches_by_name_email_or_order_number(self, engine: AsyncEngine) -> None:
        async with live_api(engine) as client:
            await add_product(client, stock=50)
            ana = (await checkout(client)).json()
            carla_body = order_body(("RS-001", 1))
            carla_body["customer"] = {"name": "Carla Dias", "email": "carla@shop.example"}
            carla = (await checkout(client, body=carla_body)).json()

            async def found(**params: str) -> list[str]:
                response = await client.get(ADMIN_ORDERS, params=params, headers=ANTONIO)
                return [item["id"] for item in response.json()["items"]]

            by_name = await found(q="dias")
            by_email = await found(q="ANA@example")
            by_number = await found(q=carla["id"][:8].upper())
            nothing = await found(q="%_")

        assert by_name == [carla["id"]]
        assert by_email == [ana["id"]]
        assert by_number == [carla["id"]]
        assert nothing == []

    async def test_filters_by_status(self, engine: AsyncEngine) -> None:
        declined = order_body(("RS-001", 1))
        declined["payment"]["card_number"] = DECLINED
        async with live_api(engine) as client:
            await add_product(client)
            paid = (await checkout(client)).json()
            failed = (await checkout(client, body=declined)).json()["order"]
            only_paid = await client.get(ADMIN_ORDERS, params={"status": "PAID"}, headers=ANTONIO)
            only_failed = await client.get(
                ADMIN_ORDERS, params={"status": "PAYMENT_FAILED"}, headers=ANTONIO
            )

        assert [item["id"] for item in only_paid.json()["items"]] == [paid["id"]]
        assert [item["id"] for item in only_failed.json()["items"]] == [failed["id"]]
        assert only_failed.json()["items"][0]["decline_reason"] == "card_declined"

    async def test_pages_through_many_orders(self, engine: AsyncEngine) -> None:
        async with live_api(engine) as client:
            await add_product(client, stock=100)
            for _ in range(23):
                await checkout(client)
            first = (await client.get(ADMIN_ORDERS, headers=ANTONIO)).json()
            second = (await client.get(ADMIN_ORDERS, params={"page": 2}, headers=ANTONIO)).json()

        assert (len(first["items"]), len(second["items"]), first["total"]) == (20, 3, 23)
        assert not {item["id"] for item in first["items"]} & {
            item["id"] for item in second["items"]
        }

    async def test_shows_one_order_in_full(self, engine: AsyncEngine) -> None:
        async with live_api(engine) as client:
            await add_product(client)
            placed = (await checkout(client, BEA)).json()
            detail = await client.get(f"{ADMIN_ORDERS}/{placed['id']}", headers=ANTONIO)
            missing = await client.get(f"{ADMIN_ORDERS}/{uuid4()}", headers=ANTONIO)

        body = detail.json()
        assert body["id"] == placed["id"]
        assert body["customer_account"] is True
        assert body["lines"][0]["sku"] == "RS-001"
        assert body["payment_reference"] == placed["payment_reference"]
        assert_problem(missing, 404, "not-found")

    async def test_customers_and_visitors_are_refused(self, engine: AsyncEngine) -> None:
        async with live_api(engine) as client:
            customer = await client.get(ADMIN_ORDERS, headers=BEA)
            visitor = await client.get(ADMIN_ORDERS)
            detail = await client.get(f"{ADMIN_ORDERS}/{uuid4()}", headers=BEA)

        assert_problem(customer, 403, "admin-required")
        assert_problem(visitor, 401, "authentication-required")
        assert_problem(detail, 403, "admin-required")
