from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from ecommerce.ordering.application.checkout import (
    CardDetails,
    Checkout,
    CheckoutCommand,
    GetOrder,
    fingerprint,
)
from ecommerce.ordering.application.errors import IdempotencyKeyReused
from ecommerce.ordering.domain.errors import (
    NotEnoughStock,
    OrderNotFound,
    ProductsNotSellable,
    ShortItem,
    UnsellableItem,
)
from ecommerce.ordering.domain.order import OrderId, RequestedLine
from ecommerce.ordering.domain.value_objects import Customer, OrderStatus
from ecommerce.shared_kernel.domain.errors import DomainValidationError
from ecommerce.shared_kernel.domain.money import Money
from fakes import SequenceClock
from ordering_fakes import (
    FlakyErrors,
    InMemoryOrderingState,
    RecordingPaymentGateway,
    sale_product,
)

NOW = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
KEY = UUID("6f1c2a00-0000-4000-8000-000000000001")
OTHER_KEY = UUID("6f1c2a00-0000-4000-8000-000000000002")
VISA = CardDetails(number="4242 4242 4242 4242", expiry_month=12, expiry_year=2030, cvc="123")
DECLINED = CardDetails(number="4000 0000 0000 0002", expiry_month=12, expiry_year=2030, cvc="123")


class Deadlock(Exception):
    pass


def command(
    *lines: tuple[str, int],
    card: CardDetails | None = VISA,
    key: UUID = KEY,
    email: str = "ana@example.com",
) -> CheckoutCommand:
    return CheckoutCommand(
        idempotency_key=key,
        customer_name="Ana Souza",
        customer_email=email,
        lines=lines or (("RS-001", 2),),
        card=card,
    )


def checkout(
    state: InMemoryOrderingState,
    payments: RecordingPaymentGateway | None = None,
    clock: SequenceClock | None = None,
    transient: FlakyErrors | None = None,
) -> Checkout:
    return Checkout(
        state,
        payments or RecordingPaymentGateway(),
        clock or SequenceClock(NOW),
        transient=transient,
    )


def shop() -> InMemoryOrderingState:
    return InMemoryOrderingState(
        sale_product("RS-001", "89.99", 10),
        sale_product("YM-015", "25.00", 3),
        sale_product("GF-002", "0.00", 20),
        sale_product("MB-001", "15.00", 5, active=False),
        sale_product("CT-005", "199.99", 0),
    )


async def test_an_approved_card_pays_the_order_from_database_prices_and_takes_the_stock() -> None:
    state = shop()
    payments = RecordingPaymentGateway()

    result = await checkout(state, payments).execute(command(("rs-001", 1), ("RS-001", 1)))

    order = result.order
    assert result.replayed is False
    assert order.status is OrderStatus.PAID
    assert order.total == Money.of("179.98")
    assert [(line.sku, line.quantity, line.unit_price) for line in order.lines] == [
        ("RS-001", 2, Money.of("89.99"))
    ]
    assert (order.card_last4, order.payment_reference) == ("4242", "fake_1")
    assert [(charge.amount, charge.last4) for charge in payments.charges] == [
        (Money.of("179.98"), "4242")
    ]
    assert state.decreases == [("RS-001", 2, str(order.id))]
    assert state.products["RS-001"].stock == 8
    assert state.orders[order.id] is order


async def test_a_declined_card_stores_a_failed_order_and_keeps_the_stock() -> None:
    state = shop()

    result = await checkout(state).execute(command(card=DECLINED))

    assert result.order.status is OrderStatus.PAYMENT_FAILED
    assert result.order.decline_reason == "card_declined"
    assert result.order.card_last4 == "0002"
    assert state.decreases == []
    assert state.products["RS-001"].stock == 10
    assert result.order.id in state.orders


async def test_a_free_gift_order_is_paid_without_calling_the_gateway() -> None:
    state = shop()
    payments = RecordingPaymentGateway(fail_if_called=True)

    result = await checkout(state, payments).execute(command(("GF-002", 2), card=None))

    assert result.order.status is OrderStatus.PAID
    assert result.order.total == Money(Decimal("0"))
    assert (result.order.card_last4, result.order.payment_reference) == (None, None)
    assert state.decreases == [("GF-002", 2, str(result.order.id))]


async def test_a_paid_cart_without_a_card_is_refused_and_nothing_is_written() -> None:
    state = shop()

    with pytest.raises(DomainValidationError) as error:
        await checkout(state).execute(command(card=None))

    assert [(issue.field, issue.code) for issue in error.value.issues] == [("payment", "required")]
    assert state.orders == {}
    assert state.keys == {}


async def test_every_unsellable_product_is_reported_at_once_and_nothing_is_written() -> None:
    state = shop()
    payments = RecordingPaymentGateway()

    with pytest.raises(ProductsNotSellable) as error:
        await checkout(state, payments).execute(
            command(("ZZ-999", 1), ("MB-001", 1), ("CT-005", 1), ("RS-001", 1))
        )

    assert error.value.items == (
        UnsellableItem("CT-005", "out_of_stock"),
        UnsellableItem("MB-001", "archived"),
        UnsellableItem("ZZ-999", "unknown"),
    )
    assert payments.charges == []
    assert state.orders == {}
    assert state.keys == {}


async def test_quantities_above_the_stock_are_reported_at_once() -> None:
    state = shop()

    with pytest.raises(NotEnoughStock) as error:
        await checkout(state).execute(command(("YM-015", 5), ("RS-001", 11)))

    assert error.value.items == (ShortItem("RS-001", 11, 10), ShortItem("YM-015", 5, 3))
    assert state.orders == {}


async def test_products_are_locked_in_sku_order() -> None:
    state = shop()

    await checkout(state).execute(command(("YM-015", 1), ("RS-001", 1)))

    assert state.locked == [["RS-001", "YM-015"]]


async def test_bad_customer_lines_and_card_are_reported_together_before_any_lock() -> None:
    state = shop()
    bad_card = CardDetails(number="1234", expiry_month=1, expiry_year=2020, cvc="1")

    with pytest.raises(DomainValidationError) as error:
        await checkout(state).execute(command(("RS-001", 0), card=bad_card, email="nope"))

    assert [issue.field for issue in error.value.issues] == [
        "customer.email",
        "lines[0].quantity",
        "payment.card_number",
        "payment.expiry",
        "payment.cvc",
    ]
    assert state.locked == []


async def test_the_same_key_and_request_replays_the_first_order() -> None:
    state = shop()
    payments = RecordingPaymentGateway()
    use_case = checkout(state, payments, SequenceClock(NOW, NOW + timedelta(seconds=5)))

    first = await use_case.execute(command())
    second = await use_case.execute(command(("rs-001", 2)))

    assert second.replayed is True
    assert second.order.id == first.order.id
    assert len(state.orders) == 1
    assert len(payments.charges) == 1
    assert state.products["RS-001"].stock == 8


async def test_a_declined_checkout_is_replayed_with_the_same_key() -> None:
    state = shop()
    use_case = checkout(state)

    first = await use_case.execute(command(card=DECLINED))
    second = await use_case.execute(command(card=DECLINED))

    assert second.replayed is True
    assert second.order.id == first.order.id
    assert second.order.status is OrderStatus.PAYMENT_FAILED


async def test_the_same_key_with_a_different_request_is_refused() -> None:
    state = shop()
    use_case = checkout(state)
    await use_case.execute(command())

    with pytest.raises(IdempotencyKeyReused):
        await use_case.execute(command(("RS-001", 3)))

    assert len(state.orders) == 1
    assert state.products["RS-001"].stock == 8


async def test_a_key_is_free_again_after_a_refused_checkout() -> None:
    state = shop()
    use_case = checkout(state)
    with pytest.raises(NotEnoughStock):
        await use_case.execute(command(("RS-001", 11)))

    result = await use_case.execute(command(("RS-001", 1)))

    assert result.replayed is False
    assert result.order.status is OrderStatus.PAID


async def test_an_expired_key_starts_a_new_checkout() -> None:
    state = shop()
    use_case = checkout(state, clock=SequenceClock(NOW, NOW + timedelta(hours=24, seconds=1)))
    first = await use_case.execute(command())

    second = await use_case.execute(command())

    assert second.replayed is False
    assert second.order.id != first.order.id
    assert state.products["RS-001"].stock == 6


async def test_a_deadlock_is_retried_once() -> None:
    state = shop()
    state.failures.append(Deadlock())

    result = await checkout(state, transient=FlakyErrors(Deadlock)).execute(command())

    assert result.order.status is OrderStatus.PAID
    assert state.commits == 1


async def test_a_second_deadlock_is_not_retried_again() -> None:
    state = shop()
    state.failures.extend([Deadlock(), Deadlock()])

    with pytest.raises(Deadlock):
        await checkout(state, transient=FlakyErrors(Deadlock)).execute(command())

    assert state.orders == {}


async def test_other_errors_are_never_retried() -> None:
    state = shop()
    state.failures.extend([RuntimeError("boom")])

    with pytest.raises(RuntimeError):
        await checkout(state, transient=FlakyErrors(Deadlock)).execute(command())

    assert state.locked == []


def test_the_fingerprint_ignores_spelling_and_order_but_not_content() -> None:
    customer = Customer.of("Ana Souza", "ana@example.com")
    same_customer = Customer.of(" Ana Souza ", "ANA@example.com")
    lines = (RequestedLine("RS-001", 2), RequestedLine("YM-015", 1))

    base = fingerprint(customer, lines, "4242")

    assert fingerprint(same_customer, lines, "4242") == base
    assert fingerprint(customer, lines, "0002") != base
    assert fingerprint(customer, lines, None) != base
    assert fingerprint(customer, (RequestedLine("RS-001", 3),), "4242") != base
    assert len(base) == 64
    assert "4242424242424242" not in base


def test_card_details_never_show_the_number_or_code_when_printed() -> None:
    text = repr(VISA) + str(command())

    assert "4242 4242 4242 4242" not in text
    assert "123" not in text.replace("4242", "")


async def test_an_order_can_be_read_back() -> None:
    state = shop()
    placed = await checkout(state).execute(command())

    found = await GetOrder(state).execute(placed.order.id)

    assert found is placed.order


async def test_an_unknown_order_is_not_found() -> None:
    with pytest.raises(OrderNotFound):
        await GetOrder(shop()).execute(OrderId(OTHER_KEY))
