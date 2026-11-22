from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from psycopg import errors
from sqlalchemy.exc import IntegrityError, OperationalError

from ecommerce.ordering.application.audit import SHOP_ACTOR, order_audit_entries
from ecommerce.ordering.domain.order import Order, OrderLine, new_order_id
from ecommerce.ordering.domain.payment import PaymentCard
from ecommerce.ordering.domain.value_objects import Customer
from ecommerce.ordering.infrastructure.payment_gateway import FakePaymentGateway
from ecommerce.ordering.infrastructure.transient import DatabaseTransientErrors
from ecommerce.shared_kernel.domain.money import Money

AT = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
TODAY = date(2026, 11, 22)


def card(number: str) -> PaymentCard:
    return PaymentCard.of(number, 12, 2030, "123", today=TODAY)


@pytest.mark.parametrize(
    ("number", "approved"),
    [
        ("4242 4242 4242 4242", True),
        ("4000 0000 0000 0002", False),
        ("5555 5555 5555 4444", True),
    ],
)
async def test_the_fake_gateway_follows_the_test_card_numbers(number: str, approved: bool) -> None:
    result = await FakePaymentGateway().charge(Money.of("10.00"), card(number), "order-1")

    assert result.approved is approved
    if approved:
        assert result.reference.startswith("fake_")
        assert result.decline_reason is None
    else:
        assert result.decline_reason == "card_declined"


async def test_the_fake_gateway_gives_every_payment_its_own_reference() -> None:
    gateway = FakePaymentGateway()
    visa = card("4242 4242 4242 4242")

    first = await gateway.charge(Money.of("10.00"), visa, "order-1")
    second = await gateway.charge(Money.of("10.00"), visa, "order-2")

    assert first.reference != second.reference


def wrapped(error: Exception) -> OperationalError:
    return OperationalError("SELECT 1", {}, error)


def test_only_a_deadlock_counts_as_a_transient_database_error() -> None:
    transient = DatabaseTransientErrors()

    assert transient.is_transient(wrapped(errors.DeadlockDetected("deadlock detected")))
    assert not transient.is_transient(wrapped(errors.LockNotAvailable("lock timeout")))
    assert not transient.is_transient(IntegrityError("INSERT", {}, errors.UniqueViolation("x")))
    assert not transient.is_transient(RuntimeError("boom"))


def test_order_events_become_audit_entries_without_customer_details() -> None:
    order = Order.place(
        order_id=new_order_id(),
        customer=Customer.of("Ana Souza", "ana@example.com"),
        lines=(
            OrderLine(
                sku="RS-001",
                product_id=UUID(int=1),
                name="Running Shoes",
                unit_price=Money.of("89.99"),
                quantity=2,
                gift=False,
            ),
        ),
        at=AT,
    )
    order.mark_paid(payment_reference="fake_abc", card_last4="4242", at=AT)
    other = Order.place(order_id=new_order_id(), customer=order.customer, lines=order.lines, at=AT)
    other.mark_payment_failed(reason="card_declined", card_last4="0002", at=AT)

    entries = order_audit_entries([*order.pull_events(), *other.pull_events()], SHOP_ACTOR)

    assert [(entry.event, entry.entity, entry.entity_id) for entry in entries] == [
        ("order.paid", "order", str(order.id)),
        ("order.payment_failed", "order", str(other.id)),
    ]
    assert entries[0].after == {
        "status": "PAID",
        "total": "179.98",
        "lines": [{"sku": "RS-001", "quantity": 2, "unit_price": "89.99"}],
        "card_last4": "4242",
        "payment_reference": "fake_abc",
    }
    assert entries[1].after == {
        "status": "PAYMENT_FAILED",
        "total": "179.98",
        "decline_reason": "card_declined",
        "card_last4": "0002",
    }
    assert all(entry.actor == "Shop checkout" for entry in entries)
    assert all(entry.context == {"source": "checkout"} for entry in entries)
    text = str([entry.after for entry in entries])
    assert "Ana" not in text
    assert "example.com" not in text
