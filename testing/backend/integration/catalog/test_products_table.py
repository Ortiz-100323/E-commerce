from typing import Any

import pytest
from psycopg import errors
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

VALID_ROW: dict[str, Any] = {
    "id": "00000000-0000-4000-8000-000000000001",
    "sku": "RS-001",
    "name": "Running Shoes",
    "description": "",
    "category": "Sports",
    "price": "89.99",
    "stock": 10,
    "weight_kg": "0.800",
    "tags": [],
    "status": "ACTIVE",
    "version": 1,
}

INSERT = text(
    "INSERT INTO products (id, sku, name, description, category, price, stock, weight_kg, "
    "tags, status, version, created_at, updated_at) VALUES (:id, :sku, :name, :description, "
    ":category, :price, :stock, :weight_kg, :tags, :status, :version, now(), now())"
)


async def insert_row(engine: AsyncEngine, **overrides: Any) -> None:
    async with engine.begin() as connection:
        await connection.execute(INSERT, {**VALID_ROW, **overrides})


def constraint_of(error: IntegrityError) -> str | None:
    assert isinstance(error.orig, errors.IntegrityError)
    return error.orig.diag.constraint_name


async def test_a_valid_row_is_accepted(engine: AsyncEngine) -> None:
    await insert_row(engine)
    await insert_row(
        engine, id="00000000-0000-4000-8000-000000000002", sku="GF-1", price="0", tags=["GIFT"]
    )


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"price": "-0.01"}, "ck_products_price_not_negative"),
        ({"stock": -1}, "ck_products_stock_not_negative"),
        ({"weight_kg": "-0.001"}, "ck_products_weight_not_negative"),
        ({"price": "0", "tags": []}, "ck_products_gift_if_and_only_if_free"),
        ({"price": "55.00", "tags": ["GIFT"]}, "ck_products_gift_if_and_only_if_free"),
        ({"tags": ["SALE"]}, "ck_products_known_tags"),
        ({"status": "DELETED"}, "ck_products_known_status"),
        ({"version": 0}, "ck_products_version_positive"),
    ],
)
async def test_the_database_rejects_rows_that_break_the_domain_rules(
    engine: AsyncEngine, overrides: dict[str, Any], constraint: str
) -> None:
    with pytest.raises(IntegrityError) as raised:
        await insert_row(engine, **overrides)

    assert isinstance(raised.value.orig, errors.CheckViolation)
    assert constraint_of(raised.value) == constraint


async def test_the_database_rejects_a_duplicate_sku(engine: AsyncEngine) -> None:
    await insert_row(engine)

    with pytest.raises(IntegrityError) as raised:
        await insert_row(engine, id="00000000-0000-4000-8000-000000000002")

    assert isinstance(raised.value.orig, errors.UniqueViolation)
    assert constraint_of(raised.value) == "uq_products_sku"


async def test_the_database_rejects_an_update_that_breaks_a_rule(engine: AsyncEngine) -> None:
    await insert_row(engine)

    with pytest.raises(IntegrityError) as raised:
        async with engine.begin() as connection:
            await connection.execute(text("UPDATE products SET stock = stock - 11"))

    assert constraint_of(raised.value) == "ck_products_stock_not_negative"


async def test_search_indexes_use_trigrams(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        result = await connection.execute(
            text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'products'")
        )
        definitions = {name: definition for name, definition in result}

    for column in ("name", "sku", "description"):
        definition = definitions[f"ix_products_{column}_trgm"]
        assert "USING gin" in definition
        assert "gin_trgm_ops" in definition
