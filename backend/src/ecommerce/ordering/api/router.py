from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status

from ecommerce.ordering.api.problems import (
    PAYMENT_DECLINED,
    IdempotencyKeyInvalid,
    IdempotencyKeyMissing,
)
from ecommerce.ordering.api.schemas import CheckoutRequest, OrderResponse
from ecommerce.ordering.application.checkout import (
    CardDetails,
    Checkout,
    CheckoutCommand,
    GetOrder,
)
from ecommerce.ordering.application.ports import PaymentGateway, TransientErrors
from ecommerce.ordering.application.unit_of_work import OrderingUnitOfWorkFactory
from ecommerce.ordering.domain.value_objects import OrderStatus
from ecommerce.shared_kernel.api.problem_details import problem_response
from ecommerce.shared_kernel.application.ports import Clock

IDEMPOTENCY_HEADER = "Idempotency-Key"
REPLAYED_HEADER = "Idempotent-Replayed"

router = APIRouter(prefix="/orders", tags=["orders"])

CHECKOUT_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"description": "The Idempotency-Key is missing or not a UUID."},
    status.HTTP_402_PAYMENT_REQUIRED: {
        "description": "The card was declined. The failed order is in `order`."
    },
    status.HTTP_409_CONFLICT: {
        "description": "A product can't be sold (`product-not-sellable`) or there isn't enough "
        "stock (`insufficient-stock`)."
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "description": "The request is not valid, or the key was used for another request."
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Busy; retry with the same key."},
}


def idempotency_key(
    key: Annotated[
        str | None,
        Header(
            alias=IDEMPOTENCY_HEADER,
            description="A UUID, one per checkout attempt. Repeat it to retry safely.",
        ),
    ] = None,
) -> UUID:
    if key is None or not key.strip():
        raise IdempotencyKeyMissing()
    try:
        return UUID(key.strip())
    except ValueError as error:
        raise IdempotencyKeyInvalid() from error


def get_checkout(request: Request) -> Checkout:
    state = request.app.state
    ordering: OrderingUnitOfWorkFactory = state.ordering_unit_of_work
    payments: PaymentGateway = state.payment_gateway
    clock: Clock = state.clock
    transient: TransientErrors = state.transient_errors
    lifetime: timedelta = state.idempotency_key_lifetime
    return Checkout(ordering, payments, clock, key_lifetime=lifetime, transient=transient)


def get_get_order(request: Request) -> GetOrder:
    ordering: OrderingUnitOfWorkFactory = request.app.state.ordering_unit_of_work
    return GetOrder(ordering)


def command_of(body: CheckoutRequest, key: UUID) -> CheckoutCommand:
    payment = body.payment
    return CheckoutCommand(
        idempotency_key=key,
        customer_name=body.customer.name,
        customer_email=body.customer.email,
        lines=tuple((line.sku, line.quantity) for line in body.lines),
        card=None
        if payment is None
        else CardDetails(
            number=payment.card_number,
            expiry_month=payment.expiry_month,
            expiry_year=payment.expiry_year,
            cvc=payment.cvc,
        ),
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=OrderResponse,
    responses=CHECKOUT_RESPONSES,
    summary="Check out: price the cart, pay with a fake card and take the stock",
)
async def place_order(
    body: CheckoutRequest,
    request: Request,
    response: Response,
    key: Annotated[UUID, Depends(idempotency_key)],
    use_case: Annotated[Checkout, Depends(get_checkout)],
) -> Response | OrderResponse:
    result = await use_case.execute(command_of(body, key))
    order = OrderResponse.of(result.order)
    replayed = {REPLAYED_HEADER: "true"} if result.replayed else {}
    if result.order.status is OrderStatus.PAYMENT_FAILED:
        return problem_response(
            request,
            PAYMENT_DECLINED,
            detail="Nothing was charged and no stock was taken. Try another card.",
            extra={"order_id": str(order.id), "order": order.model_dump(mode="json")},
            headers=replayed,
        )
    response.headers["Location"] = f"{request.url.path}/{order.id}"
    response.headers.update(replayed)
    return order


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "The order was not found."}},
)
async def get_order(
    order_id: UUID, use_case: Annotated[GetOrder, Depends(get_get_order)]
) -> OrderResponse:
    return OrderResponse.of(await use_case.execute(order_id))
