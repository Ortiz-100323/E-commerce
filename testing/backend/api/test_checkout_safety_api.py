import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from live import ANTONIO, ORDERS, PRODUCTS, live_api, update_body
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from checkout_support import DECLINED, add_product, card, count, order_body, place, stock_of
from ecommerce.ordering.application.ports import PaymentResult
from ecommerce.ordering.domain.payment import PaymentCard
from ecommerce.shared_kernel.domain.money import Money
from ordering_fakes import MovableClock
from problems import assert_problem

REPLAYED = "idempotent-replayed"
WAIT_LIMIT = timedelta(seconds=10)


class LatchedPaymentGateway:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def charge(self, amount: Money, card: PaymentCard, reference: str) -> PaymentResult:
        self.calls += 1
        if self.calls == 1:
            self.entered.set()
            await self.release.wait()
        return PaymentResult(approved=True, reference=f"fake_latched_{self.calls}")


async def wait_until(condition: Callable[[], Awaitable[bool]]) -> None:
    deadline = datetime.now(UTC) + WAIT_LIMIT
    while not await condition():
        if datetime.now(UTC) > deadline:
            raise AssertionError("The condition was never met.")
        await asyncio.sleep(0.01)


def lock_waiters(engine: AsyncEngine) -> Callable[[], Awaitable[bool]]:
    async def waiting() -> bool:
        return (
            await count(
                engine,
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE wait_event_type = 'Lock' AND datname = current_database()",
            )
            > 0
        )

    return waiting


async def test_the_same_key_and_body_gives_one_order_and_an_identical_replay(
    engine: AsyncEngine,
) -> None:
    key = str(uuid4())
    async with live_api(engine) as client:
        shoes = await add_product(client)
        first = await place(client, order_body(), key)
        second = await place(client, order_body(), key)
        stock = await stock_of(client, shoes)

    assert first.status_code == second.status_code == 201
    assert second.json() == first.json()
    assert second.headers[REPLAYED] == "true"
    assert REPLAYED not in first.headers
    assert second.headers["location"] == first.headers["location"]
    assert stock == 8
    assert await count(engine, "SELECT count(*) FROM orders") == 1
    stock_entries = "SELECT count(*) FROM audit_log WHERE event = 'product.stock_decreased'"
    assert await count(engine, stock_entries) == 1


async def test_the_same_key_with_another_body_is_refused_and_changes_nothing(
    engine: AsyncEngine,
) -> None:
    key = str(uuid4())
    async with live_api(engine) as client:
        shoes = await add_product(client)
        first = await place(client, order_body(), key)
        second = await place(client, order_body(("RS-001", 3)), key)
        stock = await stock_of(client, shoes)

    assert first.status_code == 201
    assert_problem(second, 422, "idempotency-key-reused")
    assert first.json()["id"] not in second.text
    assert stock == 8
    assert await count(engine, "SELECT count(*) FROM orders") == 1


@pytest.mark.parametrize(
    ("headers", "slug"),
    [
        ({}, "idempotency-key-missing"),
        ({"Idempotency-Key": ""}, "idempotency-key-missing"),
        ({"Idempotency-Key": "not-a-uuid"}, "idempotency-key-invalid"),
    ],
)
async def test_a_missing_or_malformed_key_is_refused_before_anything_happens(
    engine: AsyncEngine, headers: dict[str, str], slug: str
) -> None:
    async with live_api(engine) as client:
        shoes = await add_product(client)
        response = await client.post(ORDERS, json=order_body(), headers=headers)
        stock = await stock_of(client, shoes)

    assert_problem(response, 400, slug)
    assert stock == 10
    assert await count(engine, "SELECT count(*) FROM orders") == 0


async def test_ten_parallel_requests_with_one_key_create_exactly_one_order(
    engine: AsyncEngine,
) -> None:
    key = str(uuid4())
    async with live_api(engine) as client:
        shoes = await add_product(client)
        responses = await asyncio.gather(*(place(client, order_body(), key) for _ in range(10)))
        stock = await stock_of(client, shoes)

    assert [response.status_code for response in responses] == [201] * 10
    assert len({response.json()["id"] for response in responses}) == 1
    assert sum(REPLAYED in response.headers for response in responses) == 9
    assert stock == 8
    assert await count(engine, "SELECT count(*) FROM orders") == 1


async def test_twenty_parallel_checkouts_for_the_last_unit_sell_it_once(
    engine: AsyncEngine,
) -> None:
    async with live_api(engine) as client:
        shoes = await add_product(client, stock=1)
        responses = await asyncio.gather(
            *(place(client, order_body(("RS-001", 1))) for _ in range(20))
        )
        stock = await stock_of(client, shoes)

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [201] + [409] * 19
    for response in responses:
        if response.status_code == 409:
            body = assert_problem(response, 409, "product-not-sellable")
            assert body["items"] == [{"sku": "RS-001", "reason": "out_of_stock"}]
    assert stock == 0
    stock_entries = "SELECT count(*) FROM audit_log WHERE event = 'product.stock_decreased'"
    assert await count(engine, stock_entries) == 1


async def test_parallel_checkouts_never_sell_more_than_the_stock(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        shoes = await add_product(client, stock=3)
        responses = await asyncio.gather(
            *(place(client, order_body(("RS-001", 2))) for _ in range(20))
        )
        stock = await stock_of(client, shoes)

    assert sorted(response.status_code for response in responses) == [201] + [409] * 19
    for response in responses:
        if response.status_code == 409:
            body = assert_problem(response, 409, "insufficient-stock")
            assert body["items"] == [{"sku": "RS-001", "requested": 2, "available": 1}]
    assert stock == 1


async def test_carts_in_opposite_order_both_succeed_without_a_deadlock(
    engine: AsyncEngine,
) -> None:
    async with live_api(engine) as client:
        first = await add_product(client, sku="AA-001", name="First")
        second = await add_product(client, sku="BB-001", name="Second")
        responses = await asyncio.gather(
            *(
                place(client, order_body(*lines))
                for _ in range(5)
                for lines in ((("AA-001", 1), ("BB-001", 1)), (("BB-001", 1), ("AA-001", 1)))
            )
        )
        stocks = (await stock_of(client, first), await stock_of(client, second))

    assert [response.status_code for response in responses] == [201] * 10
    assert stocks == (0, 0)


async def test_a_second_checkout_waits_for_the_first_and_then_finds_no_stock(
    engine: AsyncEngine,
) -> None:
    payments = LatchedPaymentGateway()
    async with live_api(engine, payments=payments) as client:
        await add_product(client, stock=1)
        first = asyncio.create_task(place(client, order_body(("RS-001", 1))))
        await asyncio.wait_for(payments.entered.wait(), WAIT_LIMIT.total_seconds())
        second = asyncio.create_task(place(client, order_body(("RS-001", 1))))
        await wait_until(lock_waiters(engine))

        assert not second.done()
        payments.release.set()
        results = await asyncio.gather(first, second)

    assert results[0].status_code == 201
    assert_problem(results[1], 409, "product-not-sellable")
    assert payments.calls == 1


async def test_a_checkout_that_waits_too_long_for_a_lock_gets_503(engine: AsyncEngine) -> None:
    payments = LatchedPaymentGateway()
    async with live_api(engine, payments=payments, lock_timeout_ms=200) as client:
        await add_product(client, stock=5)
        first = asyncio.create_task(place(client, order_body(("RS-001", 1))))
        await asyncio.wait_for(payments.entered.wait(), WAIT_LIMIT.total_seconds())
        second = await place(client, order_body(("RS-001", 1)))
        payments.release.set()
        done = await first

    assert done.status_code == 201
    assert_problem(second, 503, "service-unavailable")
    assert second.headers["retry-after"] == "1"
    assert await count(engine, "SELECT count(*) FROM orders") == 1


async def test_an_admin_edit_made_before_a_checkout_is_refused_afterwards(
    engine: AsyncEngine,
) -> None:
    async with live_api(engine) as client:
        shoes = await add_product(client)
        await place(client, order_body(("RS-001", 1)))
        response = await client.put(
            f"{PRODUCTS}/{shoes['id']}",
            json=update_body(shoes["version"], name="Renamed"),
            headers=ANTONIO,
        )

    body = assert_problem(response, 409, "version-conflict")
    assert body["current_version"] == shoes["version"] + 1


async def test_a_key_can_be_used_again_after_a_refused_checkout(engine: AsyncEngine) -> None:
    key = str(uuid4())
    async with live_api(engine) as client:
        await add_product(client, stock=3)
        refused = await place(client, order_body(("RS-001", 5)), key)
        accepted = await place(client, order_body(("RS-001", 1)), key)

    assert_problem(refused, 409, "insufficient-stock")
    assert accepted.status_code == 201
    assert REPLAYED not in accepted.headers


async def test_a_declined_payment_is_replayed_with_the_same_key(engine: AsyncEngine) -> None:
    key = str(uuid4())
    body: dict[str, Any] = order_body(payment=card(DECLINED))
    async with live_api(engine) as client:
        await add_product(client)
        first = await place(client, body, key)
        second = await place(client, body, key)

    first_body = assert_problem(first, 402, "payment-declined")
    second_body = assert_problem(second, 402, "payment-declined")
    assert second.headers[REPLAYED] == "true"
    assert {**second_body, "request_id": None} == {**first_body, "request_id": None}
    assert await count(engine, "SELECT count(*) FROM orders") == 1


async def test_an_expired_key_starts_a_new_checkout(engine: AsyncEngine) -> None:
    key = str(uuid4())
    clock = MovableClock(datetime(2026, 11, 22, 10, 0, tzinfo=UTC))
    async with live_api(engine, clock=clock) as client:
        shoes = await add_product(client)
        first = await place(client, order_body(("RS-001", 1)), key)
        clock.advance(timedelta(hours=24, seconds=1))
        second = await place(client, order_body(("RS-001", 1)), key)
        stock = await stock_of(client, shoes)

    assert first.status_code == second.status_code == 201
    assert second.json()["id"] != first.json()["id"]
    assert REPLAYED not in second.headers
    assert stock == 8


async def test_the_database_refuses_negative_stock(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        await add_product(client)

    async with engine.connect() as connection:
        with pytest.raises(Exception, match="ck_products_stock_not_negative"):
            await connection.execute(text("UPDATE products SET stock = -1"))
