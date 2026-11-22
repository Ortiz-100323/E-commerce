import hashlib
import hmac
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from http import HTTPStatus
from uuid import UUID

from ecommerce.ordering.application.errors import IdempotencyKeyReused
from ecommerce.ordering.application.ports import (
    PaymentGateway,
    SaleProduct,
    TransientErrors,
)
from ecommerce.ordering.application.unit_of_work import (
    OrderingUnitOfWork,
    OrderingUnitOfWorkFactory,
)
from ecommerce.ordering.domain.errors import (
    NotEnoughStock,
    OrderNotFound,
    ProductsNotSellable,
    ShortItem,
    UnsellableItem,
)
from ecommerce.ordering.domain.order import (
    Order,
    OrderId,
    OrderLine,
    RequestedLine,
    merge_lines,
    new_order_id,
)
from ecommerce.ordering.domain.payment import PaymentCard
from ecommerce.ordering.domain.value_objects import Customer, OrderStatus
from ecommerce.shared_kernel.application.ports import Clock
from ecommerce.shared_kernel.domain.errors import (
    DomainValidationError,
    IssueCollector,
    ValidationIssue,
)
from ecommerce.shared_kernel.domain.money import Money

UNKNOWN = "unknown"
ARCHIVED = "archived"
OUT_OF_STOCK = "out_of_stock"
INSUFFICIENT_STOCK = "insufficient_stock"
KEY_LIFETIME = timedelta(hours=24)
DEFAULT_DECLINE_REASON = "card_declined"
ATTEMPTS = 2


@dataclass(frozen=True, kw_only=True, repr=False)
class CardDetails:
    number: str
    expiry_month: int
    expiry_year: int
    cvc: str

    def __repr__(self) -> str:
        return "CardDetails(****)"


@dataclass(frozen=True, kw_only=True)
class CheckoutCommand:
    idempotency_key: UUID
    customer_name: str
    customer_email: str
    lines: tuple[tuple[str, int], ...]
    card: CardDetails | None = field(default=None)


@dataclass(frozen=True, kw_only=True)
class CheckoutResult:
    order: Order
    replayed: bool


@dataclass(frozen=True, kw_only=True)
class PreparedCheckout:
    customer: Customer
    lines: tuple[RequestedLine, ...]
    card: PaymentCard | None


def response_status(order: Order) -> int:
    if order.status is OrderStatus.PAYMENT_FAILED:
        return HTTPStatus.PAYMENT_REQUIRED
    return HTTPStatus.CREATED


def fingerprint(
    customer: Customer,
    lines: Sequence[RequestedLine],
    card: PaymentCard | None,
    secret: bytes,
) -> str:
    canonical = {
        "customer": {"email": customer.email.strip().lower(), "name": customer.name.strip()},
        "lines": [[line.sku, line.quantity] for line in lines],
        "payment": None
        if card is None
        else {
            "card_number": card.number,
            "cvc": card.cvc,
            "expiry_month": card.expiry_month,
            "expiry_year": card.expiry_year,
        },
    }
    text = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return "v2:" + hmac.new(secret, text.encode(), hashlib.sha256).hexdigest()


def legacy_fingerprint(
    customer: Customer, lines: Sequence[RequestedLine], last4: str | None
) -> str:
    canonical = {
        "card_last4": last4,
        "customer": {"email": customer.email.strip().lower(), "name": customer.name.strip()},
        "lines": [[line.sku, line.quantity] for line in lines],
    }
    text = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def prepare(command: CheckoutCommand, today: date) -> PreparedCheckout:
    collector = IssueCollector()
    customer = collector.attempt(
        lambda raw: Customer.of(raw[0], raw[1]), (command.customer_name, command.customer_email)
    )
    lines = collector.attempt(merge_lines, command.lines)
    card = None
    details = command.card
    if details is not None:
        card = collector.attempt(
            lambda raw: PaymentCard.of(
                raw.number, raw.expiry_month, raw.expiry_year, raw.cvc, today=today
            ),
            details,
        )
    if collector.issues:
        raise DomainValidationError(collector.issues)
    assert customer is not None and lines is not None
    return PreparedCheckout(customer=customer, lines=lines, card=card)


def line_problem(line: RequestedLine, product: SaleProduct | None) -> str | None:
    if product is None:
        return UNKNOWN
    if not product.active:
        return ARCHIVED
    if product.stock == 0:
        return OUT_OF_STOCK
    if line.quantity > product.stock:
        return INSUFFICIENT_STOCK
    return None


def check_sellable(lines: Sequence[RequestedLine], products: dict[str, SaleProduct]) -> None:
    unsellable: list[UnsellableItem] = []
    short: list[ShortItem] = []
    for line in lines:
        product = products.get(line.sku)
        problem = line_problem(line, product)
        if problem == INSUFFICIENT_STOCK and product is not None:
            short.append(ShortItem(line.sku, line.quantity, product.stock))
        elif problem is not None:
            unsellable.append(UnsellableItem(line.sku, problem))
    if unsellable:
        raise ProductsNotSellable(unsellable)
    if short:
        raise NotEnoughStock(short)


def payment_required(total: Money) -> DomainValidationError:
    return DomainValidationError(
        [
            ValidationIssue(
                "payment",
                "required",
                f"This order costs {total.amount} {total.currency}. Enter a card to pay.",
                params={"total": str(total.amount)},
            )
        ]
    )


async def place_order(
    work: OrderingUnitOfWork, prepared: PreparedCheckout, payments: PaymentGateway, now: datetime
) -> Order:
    products = await work.catalog.lock_for_sale([line.sku for line in prepared.lines])
    check_sellable(prepared.lines, products)
    order = Order.place(
        order_id=new_order_id(),
        customer=prepared.customer,
        lines=[
            OrderLine(
                sku=line.sku,
                product_id=products[line.sku].product_id,
                name=products[line.sku].name,
                unit_price=Money(products[line.sku].price),
                quantity=line.quantity,
                gift=products[line.sku].gift,
            )
            for line in prepared.lines
        ],
        at=now,
    )
    if order.total.is_zero:
        order.mark_paid(payment_reference=None, card_last4=None, at=now)
        await take_stock(work, order, now)
        return order
    card = prepared.card
    if card is None:
        raise payment_required(order.total)
    result = await payments.charge(order.total, card, str(order.id))
    if not result.approved:
        order.mark_payment_failed(
            reason=result.decline_reason or DEFAULT_DECLINE_REASON, card_last4=card.last4, at=now
        )
        return order
    await take_stock(work, order, now)
    order.mark_paid(payment_reference=result.reference, card_last4=card.last4, at=now)
    return order


async def take_stock(work: OrderingUnitOfWork, order: Order, now: datetime) -> None:
    for line in order.lines:
        await work.catalog.decrease_stock(
            line.sku, line.quantity, order_reference=str(order.id), at=now
        )


class Checkout:
    def __init__(
        self,
        ordering: OrderingUnitOfWorkFactory,
        payments: PaymentGateway,
        clock: Clock,
        *,
        fingerprint_secret: bytes,
        key_lifetime: timedelta = KEY_LIFETIME,
        transient: TransientErrors | None = None,
    ) -> None:
        self._ordering = ordering
        self._payments = payments
        self._clock = clock
        self._fingerprint_secret = fingerprint_secret
        self._key_lifetime = key_lifetime
        self._transient = transient

    async def execute(self, command: CheckoutCommand) -> CheckoutResult:
        now = self._clock.now()
        prepared = prepare(command, now.date())
        key_fingerprint = fingerprint(
            prepared.customer,
            prepared.lines,
            prepared.card,
            self._fingerprint_secret,
        )
        previous_fingerprint = legacy_fingerprint(
            prepared.customer,
            prepared.lines,
            None if prepared.card is None else prepared.card.last4,
        )
        attempt = 1
        while True:
            try:
                return await self._attempt(
                    command.idempotency_key,
                    key_fingerprint,
                    previous_fingerprint,
                    prepared,
                    now,
                )
            except Exception as error:
                if attempt >= ATTEMPTS or not self._is_transient(error):
                    raise
                attempt += 1

    def _is_transient(self, error: Exception) -> bool:
        return self._transient is not None and self._transient.is_transient(error)

    async def _attempt(
        self,
        key: UUID,
        key_fingerprint: str,
        previous_fingerprint: str,
        prepared: PreparedCheckout,
        now: datetime,
    ) -> CheckoutResult:
        async with self._ordering() as work:
            existing = await work.idempotency.claim(
                key, key_fingerprint, now=now, expires_at=now + self._key_lifetime
            )
            if existing is not None:
                if existing.fingerprint not in (key_fingerprint, previous_fingerprint):
                    raise IdempotencyKeyReused()
                stored = await work.orders.get(OrderId(existing.order_id))
                if stored is None:
                    raise OrderNotFound(existing.order_id)
                return CheckoutResult(order=stored, replayed=True)
            order = await place_order(work, prepared, self._payments, now)
            await work.orders.add(order)
            await work.idempotency.record(
                key, order_id=order.id, response_status=response_status(order)
            )
            await work.commit()
        return CheckoutResult(order=order, replayed=False)


class GetOrder:
    def __init__(self, ordering: OrderingUnitOfWorkFactory) -> None:
        self._ordering = ordering

    async def execute(self, order_id: UUID) -> Order:
        async with self._ordering() as work:
            order = await work.orders.get(OrderId(order_id))
        if order is None:
            raise OrderNotFound(order_id)
        return order


@dataclass(frozen=True, kw_only=True)
class QuoteLine:
    sku: str
    quantity: int
    product: SaleProduct | None
    problem: str | None

    @property
    def unit_price(self) -> Money | None:
        return None if self.product is None else Money(self.product.price)

    @property
    def line_total(self) -> Money | None:
        price = self.unit_price
        return None if price is None else price * self.quantity

    @property
    def name(self) -> str | None:
        return None if self.product is None else self.product.name

    @property
    def available(self) -> int:
        product = self.product
        if product is None or not product.active:
            return 0
        return product.stock


@dataclass(frozen=True, kw_only=True)
class Quote:
    lines: tuple[QuoteLine, ...]

    @property
    def total(self) -> Money:
        total = Money.zero()
        for line in self.lines:
            line_total = line.line_total
            if line.problem is None and line_total is not None:
                total = total + line_total
        return total

    @property
    def ready(self) -> bool:
        return all(line.problem is None for line in self.lines)

    @property
    def payment_required(self) -> bool:
        return not self.total.is_zero


class QuoteCart:
    def __init__(self, ordering: OrderingUnitOfWorkFactory) -> None:
        self._ordering = ordering

    async def execute(self, lines: tuple[tuple[str, int], ...]) -> Quote:
        requested = merge_lines(lines)
        async with self._ordering() as work:
            products = await work.catalog.products_for_sale([line.sku for line in requested])
        return Quote(
            lines=tuple(
                QuoteLine(
                    sku=line.sku,
                    quantity=line.quantity,
                    product=products.get(line.sku),
                    problem=line_problem(line, products.get(line.sku)),
                )
                for line in requested
            )
        )
