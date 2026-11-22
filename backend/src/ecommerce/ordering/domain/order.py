from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import NewType, Self
from uuid import UUID, uuid4

from ecommerce.ordering.domain.errors import OrderAlreadySettled
from ecommerce.ordering.domain.events import OrderEvent, OrderPaid, OrderPaymentFailed
from ecommerce.ordering.domain.value_objects import (
    MAX_LINES,
    MAX_QUANTITY,
    Customer,
    OrderStatus,
)
from ecommerce.shared_kernel.domain.errors import DomainValidationError, ValidationIssue
from ecommerce.shared_kernel.domain.money import Money

OrderId = NewType("OrderId", UUID)


def new_order_id() -> OrderId:
    return OrderId(uuid4())


@dataclass(frozen=True)
class RequestedLine:
    sku: str
    quantity: int


def line_issues(index: int, sku: str, quantity: int) -> list[ValidationIssue]:
    issues = []
    if not sku.strip():
        issues.append(ValidationIssue(f"lines[{index}].sku", "required", "Enter a SKU."))
    if quantity < 1:
        issues.append(
            ValidationIssue(
                f"lines[{index}].quantity", "too_small", "The quantity must be at least 1."
            )
        )
    elif quantity > MAX_QUANTITY:
        issues.append(
            ValidationIssue(
                f"lines[{index}].quantity",
                "too_large",
                f"The quantity must be at most {MAX_QUANTITY}.",
                params={"max": MAX_QUANTITY},
            )
        )
    return issues


def merge_lines(lines: Iterable[tuple[str, int]]) -> tuple[RequestedLine, ...]:
    requested = list(lines)
    if not requested:
        raise DomainValidationError([ValidationIssue("lines", "required", "Add at least 1 item.")])
    if len(requested) > MAX_LINES:
        raise DomainValidationError(
            [
                ValidationIssue(
                    "lines",
                    "too_many_lines",
                    f"An order can have at most {MAX_LINES} lines.",
                    params={"max": MAX_LINES},
                )
            ]
        )
    issues = [
        issue
        for index, (sku, quantity) in enumerate(requested)
        for issue in line_issues(index, sku, quantity)
    ]
    if issues:
        raise DomainValidationError(issues)
    merged: dict[str, int] = {}
    for sku, quantity in requested:
        key = sku.strip().upper()
        merged[key] = merged.get(key, 0) + quantity
    too_large = [
        ValidationIssue(
            "lines",
            "quantity_too_large",
            f"The quantity of {sku} must be at most {MAX_QUANTITY}.",
            params={"sku": sku, "max": MAX_QUANTITY},
        )
        for sku, quantity in sorted(merged.items())
        if quantity > MAX_QUANTITY
    ]
    if too_large:
        raise DomainValidationError(too_large)
    return tuple(RequestedLine(sku, quantity) for sku, quantity in sorted(merged.items()))


@dataclass(frozen=True, kw_only=True)
class OrderLine:
    sku: str
    product_id: UUID
    name: str
    unit_price: Money
    quantity: int
    gift: bool

    @property
    def line_total(self) -> Money:
        return self.unit_price * self.quantity


class Order:
    def __init__(
        self,
        *,
        order_id: OrderId,
        customer: Customer,
        lines: Sequence[OrderLine],
        status: OrderStatus,
        created_at: datetime,
        settled_at: datetime | None = None,
        payment_reference: str | None = None,
        card_last4: str | None = None,
        decline_reason: str | None = None,
    ) -> None:
        if not lines:
            raise DomainValidationError(
                [ValidationIssue("lines", "required", "Add at least 1 item.")]
            )
        skus = [line.sku for line in lines]
        if len(set(skus)) != len(skus):
            raise ValueError("Each SKU may appear only once in an order.")
        self._id = order_id
        self._customer = customer
        self._lines = tuple(sorted(lines, key=lambda line: line.sku))
        self._status = status
        self._created_at = created_at
        self._settled_at = settled_at
        self._payment_reference = payment_reference
        self._card_last4 = card_last4
        self._decline_reason = decline_reason
        self._events: list[OrderEvent] = []

    @classmethod
    def place(
        cls,
        *,
        order_id: OrderId,
        customer: Customer,
        lines: Sequence[OrderLine],
        at: datetime,
    ) -> Self:
        return cls(
            order_id=order_id,
            customer=customer,
            lines=lines,
            status=OrderStatus.PENDING,
            created_at=at,
        )

    @property
    def id(self) -> OrderId:
        return self._id

    @property
    def customer(self) -> Customer:
        return self._customer

    @property
    def lines(self) -> tuple[OrderLine, ...]:
        return self._lines

    @property
    def status(self) -> OrderStatus:
        return self._status

    @property
    def total(self) -> Money:
        total = Money.zero()
        for line in self._lines:
            total = total + line.line_total
        return total

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def settled_at(self) -> datetime | None:
        return self._settled_at

    @property
    def payment_reference(self) -> str | None:
        return self._payment_reference

    @property
    def card_last4(self) -> str | None:
        return self._card_last4

    @property
    def decline_reason(self) -> str | None:
        return self._decline_reason

    def mark_paid(
        self, *, payment_reference: str | None, card_last4: str | None, at: datetime
    ) -> None:
        self._settle(at, card_last4)
        self._status = OrderStatus.PAID
        self._payment_reference = payment_reference
        self._events.append(
            OrderPaid(
                order_id=self._id,
                occurred_at=at,
                total=str(self.total.amount),
                card_last4=card_last4,
                lines=tuple(
                    (line.sku, line.quantity, str(line.unit_price.amount)) for line in self._lines
                ),
                payment_reference=payment_reference,
            )
        )

    def mark_payment_failed(self, *, reason: str, card_last4: str | None, at: datetime) -> None:
        self._settle(at, card_last4)
        self._status = OrderStatus.PAYMENT_FAILED
        self._decline_reason = reason
        self._events.append(
            OrderPaymentFailed(
                order_id=self._id,
                occurred_at=at,
                total=str(self.total.amount),
                card_last4=card_last4,
                reason=reason,
            )
        )

    def pull_events(self) -> list[OrderEvent]:
        events, self._events = self._events, []
        return events

    def _settle(self, at: datetime, card_last4: str | None) -> None:
        if self._status is not OrderStatus.PENDING:
            raise OrderAlreadySettled(self._id, self._status.value)
        self._settled_at = at
        self._card_last4 = card_last4
