from typing import Any
from uuid import uuid4

import httpx
from live import ANTONIO, ORDERS, PRODUCTS, product_body
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

APPROVED = "4242 4242 4242 4242"
DECLINED = "4000 0000 0000 0002"
CARD_DIGITS = ("4242424242424242", "4000000000000002", "4242424242424241")


def card(number: str = APPROVED, **overrides: Any) -> dict[str, Any]:
    return {
        "card_number": number,
        "expiry_month": 12,
        "expiry_year": 2030,
        "cvc": "123",
        **overrides,
    }


def order_body(
    *lines: tuple[str, int], payment: dict[str, Any] | None = None, **extra: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "customer": {"name": "Ana Souza", "email": "Ana@Example.com"},
        "lines": [{"sku": sku, "quantity": quantity} for sku, quantity in lines or [("RS-001", 2)]],
        "payment": card() if payment is None else payment,
        **extra,
    }
    return body


async def place(
    client: httpx.AsyncClient, body: dict[str, Any], key: str | None = None
) -> httpx.Response:
    return await client.post(ORDERS, json=body, headers={"Idempotency-Key": key or str(uuid4())})


async def add_product(client: httpx.AsyncClient, **overrides: Any) -> dict[str, Any]:
    response = await client.post(PRODUCTS, json=product_body(**overrides), headers=ANTONIO)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


async def stock_of(client: httpx.AsyncClient, product: dict[str, Any]) -> int:
    response = await client.get(f"{PRODUCTS}/{product['id']}")
    stock: int = response.json()["stock"]
    return stock


async def count(engine: AsyncEngine, statement: str) -> int:
    async with engine.connect() as connection:
        return int(await connection.scalar(text(statement)) or 0)


async def audit(engine: AsyncEngine, event: str) -> list[dict[str, Any]]:
    async with engine.connect() as connection:
        rows = await connection.execute(
            text("SELECT actor, entity_id, sku, context FROM audit_log WHERE event = :event"),
            {"event": event},
        )
        return [dict(row) for row in rows.mappings()]
