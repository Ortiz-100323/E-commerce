import logging
from typing import Any
from uuid import uuid4

import pytest
from live import ANTONIO, ORDERS, PRODUCTS, live_api
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from checkout_support import (
    CARD_DIGITS,
    DECLINED,
    add_product,
    audit,
    card,
    count,
    order_body,
    place,
    stock_of,
)
from ordering_fakes import RecordingPaymentGateway
from problems import assert_problem


async def test_lines_are_priced_from_the_database_and_client_prices_are_ignored(
    engine: AsyncEngine,
) -> None:
    async with live_api(engine) as client:
        await add_product(client)
        body = order_body()
        body["lines"][0].update({"unit_price": "0.01", "price": "0.01", "total": "0.02"})
        response = await place(client, body)

    assert response.status_code == 201, response.text
    order = response.json()
    assert order["total"] == "179.98"
    assert order["currency"] == "USD"
    assert order["lines"] == [
        {
            "sku": "RS-001",
            "product_id": order["lines"][0]["product_id"],
            "name": "Running Shoes",
            "unit_price": "89.99",
            "quantity": 2,
            "gift": False,
            "line_total": "179.98",
        }
    ]


async def test_an_approved_card_pays_the_order_and_takes_the_stock_with_an_audit_entry(
    engine: AsyncEngine,
) -> None:
    async with live_api(engine) as client:
        shoes = await add_product(client)
        response = await place(client, order_body())
        order = response.json()
        fetched = await client.get(f"{ORDERS}/{order['id']}")
        stock = await stock_of(client, shoes)

    assert response.status_code == 201, response.text
    assert response.headers["location"] == f"{ORDERS}/{order['id']}"
    assert order["status"] == "PAID"
    assert order["customer"] == {"name": "Ana Souza", "email": "ana@example.com"}
    assert order["card_last4"] == "4242"
    assert order["payment_reference"].startswith("fake_")
    assert order["decline_reason"] is None
    assert fetched.status_code == 200
    assert fetched.json() == order
    assert stock == 8
    decreased = await audit(engine, "product.stock_decreased")
    assert len(decreased) == 1
    assert decreased[0]["actor"] == "Shop checkout"
    assert decreased[0]["entity_id"] == shoes["id"]
    assert decreased[0]["context"]["order_reference"] == order["id"]
    paid = await audit(engine, "order.paid")
    assert [(entry["entity_id"], entry["actor"]) for entry in paid] == [
        (order["id"], "Shop checkout")
    ]


async def test_a_declined_card_returns_402_stores_a_failed_order_and_keeps_the_stock(
    engine: AsyncEngine,
) -> None:
    async with live_api(engine) as client:
        shoes = await add_product(client)
        response = await place(client, order_body(payment=card(DECLINED)))
        body = assert_problem(response, 402, "payment-declined")
        fetched = await client.get(f"{ORDERS}/{body['order_id']}")
        stock = await stock_of(client, shoes)

    assert body["order"]["status"] == "PAYMENT_FAILED"
    assert body["order"]["decline_reason"] == "card_declined"
    assert body["order"]["card_last4"] == "0002"
    assert body["order"]["id"] == body["order_id"]
    assert fetched.json() == body["order"]
    assert stock == 10
    assert await audit(engine, "product.stock_decreased") == []
    assert len(await audit(engine, "order.payment_failed")) == 1


async def test_a_free_gift_order_is_paid_without_calling_the_gateway(engine: AsyncEngine) -> None:
    payments = RecordingPaymentGateway(fail_if_called=True)
    async with live_api(engine, payments=payments) as client:
        gift = await add_product(client, sku="GF-002", name="Collar gift", price="0", gift=True)
        body = order_body(("GF-002", 2))
        del body["payment"]
        response = await place(client, body)
        stock = await stock_of(client, gift)

    assert response.status_code == 201, response.text
    order = response.json()
    assert (order["status"], order["total"], order["card_last4"]) == ("PAID", "0.00", None)
    assert order["lines"][0]["gift"] is True
    assert stock == 8


async def test_archived_out_of_stock_and_unknown_products_are_not_sellable(
    engine: AsyncEngine,
) -> None:
    async with live_api(engine) as client:
        await add_product(client)
        archived = await add_product(client, sku="MB-001", name="Mystery Box")
        await client.delete(f"{PRODUCTS}/{archived['id']}", headers=ANTONIO)
        await add_product(client, sku="CT-005", name="Camping Tent", stock=0)
        response = await place(
            client, order_body(("RS-001", 1), ("MB-001", 1), ("CT-005", 1), ("ZZ-999", 1))
        )

    body = assert_problem(response, 409, "product-not-sellable")
    assert body["items"] == [
        {"sku": "CT-005", "reason": "out_of_stock"},
        {"sku": "MB-001", "reason": "archived"},
        {"sku": "ZZ-999", "reason": "unknown"},
    ]
    assert await count(engine, "SELECT count(*) FROM orders") == 0
    assert await count(engine, "SELECT count(*) FROM idempotency_keys") == 0


async def test_quantities_above_the_stock_are_refused_with_what_is_available(
    engine: AsyncEngine,
) -> None:
    async with live_api(engine) as client:
        shoes = await add_product(client, stock=3)
        response = await place(client, order_body(("rs-001", 2), ("RS-001", 3)))
        stock = await stock_of(client, shoes)

    body = assert_problem(response, 409, "insufficient-stock")
    assert body["items"] == [{"sku": "RS-001", "requested": 5, "available": 3}]
    assert stock == 3
    assert await count(engine, "SELECT count(*) FROM orders") == 0


@pytest.mark.parametrize(
    ("change", "field", "code"),
    [
        ({"payment": None}, "payment", "required"),
        (
            {"customer": {"name": "Ana", "email": "ana.example.com"}},
            "customer.email",
            "invalid_email",
        ),
        ({"lines": []}, "lines", "too_few_items"),
        ({"lines": [{"sku": "RS-001", "quantity": 0}]}, "lines[0].quantity", "too_small"),
        ({"lines": [{"sku": "RS-001", "quantity": 1}] * 51}, "lines", "too_many_items"),
        ({"coupon": "FREE"}, "coupon", "unknown_field"),
        ({"payment": card(expiry_month=1, expiry_year=2020)}, "payment.expiry", "card_expired"),
        ({"payment": card("4242 4242 4242 4241")}, "payment.card_number", "invalid_card_number"),
        ({"payment": card(cvc="12")}, "payment.cvc", "invalid_cvc"),
    ],
)
async def test_invalid_checkouts_are_refused_and_nothing_is_written(
    engine: AsyncEngine, change: dict[str, Any], field: str, code: str
) -> None:
    async with live_api(engine) as client:
        shoes = await add_product(client)
        body = {**order_body(), **change}
        if body.get("payment") is None:
            del body["payment"]
        response = await place(client, body)
        stock = await stock_of(client, shoes)

    problem = assert_problem(response, 422, "validation-error")
    assert (field, code) in [(error["field"], error["code"]) for error in problem["errors"]]
    assert stock == 10
    assert await count(engine, "SELECT count(*) FROM orders") == 0


async def test_an_unknown_order_is_not_found(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        response = await client.get(f"{ORDERS}/{uuid4()}")

    assert_problem(response, 404, "not-found")


async def test_the_full_card_number_is_stored_returned_and_logged_nowhere(
    engine: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    async with live_api(engine) as client:
        await add_product(client)
        responses = [
            await place(client, order_body(("RS-001", 1))),
            await place(client, order_body(("RS-001", 1), payment=card(DECLINED))),
            await place(client, order_body(("RS-001", 1), payment=card("4242424242424241"))),
            await place(client, order_body(("RS-001", 1), payment=card(cvc="99999"))),
        ]
        fetched = [
            await client.get(f"{ORDERS}/{response.json().get('id') or response.json()['order_id']}")
            for response in responses[:2]
        ]

    assert [response.status_code for response in responses] == [201, 402, 422, 422]
    texts = [response.text for response in [*responses, *fetched]]
    stored = await every_text_value(engine)
    for digits in CARD_DIGITS:
        spaced = " ".join(digits[index : index + 4] for index in range(0, 16, 4))
        for value in (digits, spaced):
            assert all(value not in body for body in texts)
            assert value not in caplog.text
            assert value not in stored
    assert "99999" not in "".join(texts)


async def every_text_value(engine: AsyncEngine) -> str:
    async with engine.connect() as connection:
        columns = (
            await connection.execute(
                text(
                    "SELECT table_name, column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND data_type IN ('text', 'character varying', 'jsonb', 'ARRAY')"
                )
            )
        ).all()
        values = []
        for table, column in columns:
            rows = await connection.execute(text(f'SELECT "{column}"::text FROM "{table}"'))
            values.extend(str(value) for (value,) in rows)
    return "\n".join(values)
