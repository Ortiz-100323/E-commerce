from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ecommerce.ordering.application.checkout import Quote, QuoteLine
from ecommerce.ordering.domain.order import Order, OrderLine
from ecommerce.ordering.domain.value_objects import MAX_LINES, OrderStatus

MAX_TEXT = 10_000
MAX_SKU = 64
MAX_CARD_NUMBER = 32


class CustomerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=MAX_TEXT, examples=["Ana Souza"])
    email: str = Field(max_length=MAX_TEXT, examples=["ana@example.com"])


class OrderLineRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sku: str = Field(max_length=MAX_SKU, examples=["RS-001"])
    quantity: int = Field(ge=1, examples=[2])


class PaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_number: str = Field(max_length=MAX_CARD_NUMBER, examples=["4242 4242 4242 4242"])
    expiry_month: int = Field(ge=1, le=12, examples=[12])
    expiry_year: int = Field(ge=2000, le=2100, examples=[2030])
    cvc: str = Field(max_length=4, examples=["123"])


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "description": (
                "Prices are never read from the request: every line is priced from the catalog. "
                "A payment is needed unless the order total is 0."
            )
        },
    )

    customer: CustomerRequest
    lines: list[OrderLineRequest] = Field(min_length=1, max_length=MAX_LINES)
    payment: PaymentRequest | None = None


class QuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[OrderLineRequest] = Field(min_length=1, max_length=MAX_LINES)


class QuoteLineResponse(BaseModel):
    sku: str
    product_id: UUID | None
    name: str | None
    unit_price: str | None
    quantity: int
    gift: bool
    available: int
    line_total: str | None
    problem: str | None

    @classmethod
    def of(cls, line: QuoteLine) -> Self:
        price = line.unit_price
        total = line.line_total
        return cls(
            sku=line.sku,
            product_id=None if line.product is None else line.product.product_id,
            name=line.name,
            unit_price=None if price is None else str(price.amount),
            quantity=line.quantity,
            gift=line.product is not None and line.product.gift,
            available=line.available,
            line_total=None if total is None else str(total.amount),
            problem=line.problem,
        )


class QuoteResponse(BaseModel):
    lines: list[QuoteLineResponse]
    total: str
    currency: str
    ready: bool
    payment_required: bool

    @classmethod
    def of(cls, quote: Quote) -> Self:
        return cls(
            lines=[QuoteLineResponse.of(line) for line in quote.lines],
            total=str(quote.total.amount),
            currency=quote.total.currency,
            ready=quote.ready,
            payment_required=quote.payment_required,
        )


class CustomerResponse(BaseModel):
    name: str
    email: str


class OrderLineResponse(BaseModel):
    sku: str
    product_id: UUID
    name: str
    unit_price: str
    quantity: int
    gift: bool
    line_total: str

    @classmethod
    def of(cls, line: OrderLine) -> Self:
        return cls(
            sku=line.sku,
            product_id=line.product_id,
            name=line.name,
            unit_price=str(line.unit_price.amount),
            quantity=line.quantity,
            gift=line.gift,
            line_total=str(line.line_total.amount),
        )


class OrderResponse(BaseModel):
    id: UUID
    status: OrderStatus
    customer: CustomerResponse
    lines: list[OrderLineResponse]
    total: str
    currency: str
    card_last4: str | None
    payment_reference: str | None
    decline_reason: str | None
    created_at: datetime
    settled_at: datetime | None

    @classmethod
    def of(cls, order: Order) -> Self:
        return cls(
            id=order.id,
            status=order.status,
            customer=CustomerResponse(name=order.customer.name, email=order.customer.email),
            lines=[OrderLineResponse.of(line) for line in order.lines],
            total=str(order.total.amount),
            currency=order.total.currency,
            card_last4=order.card_last4,
            payment_reference=order.payment_reference,
            decline_reason=order.decline_reason,
            created_at=order.created_at,
            settled_at=order.settled_at,
        )
