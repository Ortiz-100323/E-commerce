from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from ecommerce.ordering.domain.errors import OrderAlreadySettled
from ecommerce.ordering.domain.events import OrderPaid, OrderPaymentFailed
from ecommerce.ordering.domain.order import (
    Order,
    OrderLine,
    RequestedLine,
    merge_lines,
    new_order_id,
)
from ecommerce.ordering.domain.value_objects import MAX_QUANTITY, Customer, OrderStatus
from ecommerce.shared_kernel.domain.errors import DomainValidationError
from ecommerce.shared_kernel.domain.money import Money

AT = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
LATER = datetime(2026, 11, 22, 10, 0, 1, tzinfo=UTC)
SHOES = UUID("00000000-0000-4000-8000-000000000101")
MAT = UUID("00000000-0000-4000-8000-000000000102")
CUSTOMER = Customer.of("Ana Souza", "ana@example.com")


def line(sku: str, price: str, quantity: int, product_id: UUID = SHOES) -> OrderLine:
    return OrderLine(
        sku=sku,
        product_id=product_id,
        name=f"Product {sku}",
        unit_price=Money.of(price),
        quantity=quantity,
        gift=price == "0.00",
    )


def placed(*lines: OrderLine) -> Order:
    return Order.place(
        order_id=new_order_id(),
        customer=CUSTOMER,
        lines=lines or (line("RS-001", "89.99", 2),),
        at=AT,
    )


def issues_of(error: pytest.ExceptionInfo[DomainValidationError]) -> list[tuple[str, str]]:
    return [(issue.field, issue.code) for issue in error.value.issues]


def test_duplicate_skus_are_merged_and_lines_sorted_by_sku() -> None:
    merged = merge_lines([("rs-001", 1), ("YM-015", 2), (" RS-001 ", 3)])

    assert merged == (RequestedLine("RS-001", 4), RequestedLine("YM-015", 2))


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        ([], [("lines", "required")]),
        ([("", 1)], [("lines[0].sku", "required")]),
        ([("RS-001", 0)], [("lines[0].quantity", "too_small")]),
        ([("RS-001", 1), ("YM-015", -2)], [("lines[1].quantity", "too_small")]),
        ([("RS-001", MAX_QUANTITY + 1)], [("lines[0].quantity", "too_large")]),
        ([("RS-001", MAX_QUANTITY), ("rs-001", 1)], [("lines", "quantity_too_large")]),
        ([("RS-001", 1)] * 51, [("lines", "too_many_lines")]),
    ],
)
def test_requested_lines_report_every_problem(
    lines: list[tuple[str, int]], expected: list[tuple[str, str]]
) -> None:
    with pytest.raises(DomainValidationError) as error:
        merge_lines(lines)

    assert issues_of(error) == expected


def test_a_line_total_is_the_unit_price_times_the_quantity() -> None:
    assert line("RS-001", "89.99", 3).line_total == Money.of("269.97")


def test_a_placed_order_is_pending_and_totals_its_lines() -> None:
    order = placed(line("RS-001", "89.99", 2), line("YM-015", "0.00", 1, MAT))

    assert order.status is OrderStatus.PENDING
    assert order.total == Money.of("179.98")
    assert [item.sku for item in order.lines] == ["RS-001", "YM-015"]
    assert order.created_at == AT
    assert order.settled_at is None
    assert order.pull_events() == []


def test_an_order_needs_at_least_one_line() -> None:
    with pytest.raises(DomainValidationError) as error:
        Order.place(order_id=new_order_id(), customer=CUSTOMER, lines=(), at=AT)

    assert issues_of(error) == [("lines", "required")]


def test_an_order_refuses_two_lines_for_the_same_sku() -> None:
    with pytest.raises(ValueError, match="once"):
        placed(line("RS-001", "89.99", 1), line("RS-001", "89.99", 2))


def test_paying_an_order_records_the_payment_and_one_event() -> None:
    order = placed()

    order.mark_paid(payment_reference="fake_abc", card_last4="4242", at=LATER)

    assert order.status is OrderStatus.PAID
    assert (order.payment_reference, order.card_last4, order.settled_at) == (
        "fake_abc",
        "4242",
        LATER,
    )
    events = order.pull_events()
    assert len(events) == 1
    paid = events[0]
    assert isinstance(paid, OrderPaid)
    assert (paid.order_id, paid.total, paid.card_last4) == (order.id, "179.98", "4242")
    assert paid.lines == (("RS-001", 2, "89.99"),)
    assert order.pull_events() == []


def test_a_free_order_is_paid_without_a_card() -> None:
    order = placed(line("GF-002", "0.00", 3))

    order.mark_paid(payment_reference=None, card_last4=None, at=LATER)

    assert order.status is OrderStatus.PAID
    assert order.total == Money(Decimal("0"))


def test_a_declined_order_records_the_reason_and_one_event() -> None:
    order = placed()

    order.mark_payment_failed(reason="card_declined", card_last4="0002", at=LATER)

    assert order.status is OrderStatus.PAYMENT_FAILED
    assert (order.decline_reason, order.card_last4) == ("card_declined", "0002")
    events = order.pull_events()
    assert [type(event) for event in events] == [OrderPaymentFailed]
    failed = events[0]
    assert isinstance(failed, OrderPaymentFailed)
    assert failed.reason == "card_declined"


@pytest.mark.parametrize("first", ["paid", "failed"])
def test_a_settled_order_cannot_be_settled_again(first: str) -> None:
    order = placed()
    if first == "paid":
        order.mark_paid(payment_reference="fake_abc", card_last4="4242", at=LATER)
    else:
        order.mark_payment_failed(reason="card_declined", card_last4="0002", at=LATER)

    with pytest.raises(OrderAlreadySettled):
        order.mark_paid(payment_reference="fake_def", card_last4="4242", at=LATER)
    with pytest.raises(OrderAlreadySettled):
        order.mark_payment_failed(reason="card_declined", card_last4="0002", at=LATER)
