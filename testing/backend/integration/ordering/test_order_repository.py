from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ecommerce.ordering.domain.order import Order, OrderId, OrderLine, new_order_id
from ecommerce.ordering.domain.value_objects import Customer, OrderStatus
from ecommerce.ordering.infrastructure.idempotency_store import SqlAlchemyIdempotencyStore
from ecommerce.ordering.infrastructure.order_repository import SqlAlchemyOrderRepository
from ecommerce.shared_kernel.domain.money import Money
from ecommerce.shared_kernel.infrastructure.database import create_session_factory

AT = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
LATER = AT + timedelta(seconds=1)
SHOES = UUID("00000000-0000-4000-8000-000000000101")
GIFT = UUID("00000000-0000-4000-8000-000000000102")
KEY = UUID("6f1c2a00-0000-4000-8000-000000000001")


@pytest.fixture
def sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


def order_of(*lines: OrderLine) -> Order:
    return Order.place(
        order_id=new_order_id(),
        customer=Customer.of("Ana Souza", "ana@example.com"),
        lines=lines
        or (
            OrderLine(
                sku="RS-001",
                product_id=SHOES,
                name="Running Shoes",
                unit_price=Money.of("89.99"),
                quantity=2,
                gift=False,
            ),
            OrderLine(
                sku="GF-002",
                product_id=GIFT,
                name="Collar gift",
                unit_price=Money.of("0.00"),
                quantity=1,
                gift=True,
            ),
        ),
        at=AT,
    )


def state(order: Order) -> tuple[object, ...]:
    return (
        order.id,
        order.status,
        order.customer,
        order.lines,
        order.total,
        order.created_at,
        order.settled_at,
        order.payment_reference,
        order.card_last4,
        order.decline_reason,
    )


async def store(sessions: async_sessionmaker[AsyncSession], order: Order) -> None:
    async with sessions() as session:
        await SqlAlchemyOrderRepository(session).add(order)
        await session.commit()


async def load(sessions: async_sessionmaker[AsyncSession], order_id: OrderId) -> Order | None:
    async with sessions() as session:
        return await SqlAlchemyOrderRepository(session).get(order_id)


async def test_a_paid_order_round_trips_with_its_lines(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    order = order_of()
    order.mark_paid(payment_reference="fake_abc", card_last4="4242", at=LATER)

    await store(sessions, order)
    loaded = await load(sessions, order.id)

    assert loaded is not None
    assert state(loaded) == state(order)
    assert loaded.status is OrderStatus.PAID
    assert loaded.pull_events() == []


async def test_a_declined_order_round_trips(sessions: async_sessionmaker[AsyncSession]) -> None:
    order = order_of()
    order.mark_payment_failed(reason="card_declined", card_last4="0002", at=LATER)

    await store(sessions, order)
    loaded = await load(sessions, order.id)

    assert loaded is not None
    assert state(loaded) == state(order)


async def test_an_unknown_order_is_none(sessions: async_sessionmaker[AsyncSession]) -> None:
    assert await load(sessions, OrderId(uuid4())) is None


async def test_the_repository_hands_over_the_events_it_stored(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    order = order_of()
    order.mark_paid(payment_reference=None, card_last4=None, at=LATER)

    async with sessions() as session:
        repository = SqlAlchemyOrderRepository(session)
        await repository.add(order)
        events = repository.take_stored_events()
        assert repository.take_stored_events() == []

    assert [event.order_id for event in events] == [order.id]


@pytest.mark.parametrize(
    ("statement", "constraint"),
    [
        ("UPDATE orders SET status = 'SHIPPED'", "ck_orders_known_status"),
        ("UPDATE orders SET card_last4 = 'abcd'", "ck_orders_card_last4_digits"),
        ("UPDATE orders SET total = -1", "ck_orders_total_not_negative"),
        ("UPDATE order_lines SET quantity = 0", "ck_order_lines_quantity_positive"),
        ("UPDATE order_lines SET unit_price = -1", "ck_order_lines_price_not_negative"),
        ("UPDATE order_lines SET line_total = 1", "ck_order_lines_total_matches"),
    ],
)
async def test_the_database_refuses_impossible_orders(
    sessions: async_sessionmaker[AsyncSession], statement: str, constraint: str
) -> None:
    order = order_of()
    order.mark_paid(payment_reference="fake_abc", card_last4="4242", at=LATER)
    await store(sessions, order)

    async with sessions() as session:
        with pytest.raises(IntegrityError, match=constraint):
            await session.execute(text(statement))


async def test_a_new_key_is_claimed_and_its_outcome_recorded(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    order = order_of()
    order.mark_paid(payment_reference="fake_abc", card_last4="4242", at=LATER)
    async with sessions() as session:
        keys = SqlAlchemyIdempotencyStore(session)
        claimed = await keys.claim(KEY, "a" * 64, now=AT, expires_at=AT + timedelta(hours=24))
        await SqlAlchemyOrderRepository(session).add(order)
        await keys.record(KEY, order_id=order.id, response_status=201)
        await session.commit()

    async with sessions() as session:
        found = await SqlAlchemyIdempotencyStore(session).claim(
            KEY, "b" * 64, now=LATER, expires_at=LATER + timedelta(hours=24)
        )

    assert claimed is None
    assert found is not None
    assert (found.fingerprint, found.order_id, found.response_status) == ("a" * 64, order.id, 201)


async def test_a_key_that_was_never_committed_stays_free(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as session:
        await SqlAlchemyIdempotencyStore(session).claim(
            KEY, "a" * 64, now=AT, expires_at=AT + timedelta(hours=24)
        )
        await session.rollback()

    async with sessions() as session:
        found = await SqlAlchemyIdempotencyStore(session).claim(
            KEY, "b" * 64, now=AT, expires_at=AT + timedelta(hours=24)
        )

    assert found is None


async def test_an_expired_key_is_claimed_again(sessions: async_sessionmaker[AsyncSession]) -> None:
    first = order_of()
    first.mark_paid(payment_reference="fake_abc", card_last4="4242", at=LATER)
    async with sessions() as session:
        keys = SqlAlchemyIdempotencyStore(session)
        await keys.claim(KEY, "a" * 64, now=AT, expires_at=AT + timedelta(hours=24))
        await SqlAlchemyOrderRepository(session).add(first)
        await keys.record(KEY, order_id=first.id, response_status=201)
        await session.commit()

    after = AT + timedelta(hours=24, seconds=1)
    async with sessions() as session:
        keys = SqlAlchemyIdempotencyStore(session)
        claimed = await keys.claim(KEY, "b" * 64, now=after, expires_at=after + timedelta(hours=24))
        second = order_of()
        second.mark_paid(payment_reference="fake_def", card_last4="4242", at=after)
        await SqlAlchemyOrderRepository(session).add(second)
        await keys.record(KEY, order_id=second.id, response_status=201)
        await session.commit()

    async with sessions() as session:
        found = await SqlAlchemyIdempotencyStore(session).claim(
            KEY, "c" * 64, now=after, expires_at=after
        )

    assert claimed is None
    assert found is not None
    assert (found.fingerprint, found.order_id) == ("b" * 64, second.id)
