from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from ecommerce.ordering.api.problems import (
    PAYMENT_DECLINED,
    IdempotencyKeyInvalid,
    IdempotencyKeyMissing,
)
from ecommerce.ordering.api.schemas import (
    AdminOrderResponse,
    AdminOrdersResponse,
    BuyerOrdersResponse,
    CheckoutRequest,
    OrderResponse,
    QuoteRequest,
    QuoteResponse,
)
from ecommerce.ordering.application.checkout import (
    MAX_ORDER_SEARCH,
    CardDetails,
    Checkout,
    CheckoutCommand,
    GetOrder,
    ListBuyerOrders,
    OrderSearch,
    QuoteCart,
    SearchOrders,
)
from ecommerce.ordering.application.errors import AdminCannotBuy
from ecommerce.ordering.application.ports import PaymentGateway, TransientErrors
from ecommerce.ordering.application.unit_of_work import OrderingUnitOfWorkFactory
from ecommerce.ordering.domain.value_objects import OrderStatus
from ecommerce.shared_kernel.api.access import (
    ADMIN_ONLY_RESPONSES,
    BUYER_ONLY_RESPONSES,
    optional_principal,
    require_admin,
    require_buyer,
)
from ecommerce.shared_kernel.api.problem_details import problem_response
from ecommerce.shared_kernel.application.ports import Clock
from ecommerce.shared_kernel.domain.principal import Principal

IDEMPOTENCY_HEADER = "Idempotency-Key"
REPLAYED_HEADER = "Idempotent-Replayed"

router = APIRouter(prefix="/orders", tags=["orders"])

CHECKOUT_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"description": "The Idempotency-Key is missing or not a UUID."},
    status.HTTP_402_PAYMENT_REQUIRED: {
        "description": "The card was declined. The failed order is in `order`."
    },
    status.HTTP_401_UNAUTHORIZED: {
        "description": "A session cookie was sent but has ended (`authentication-required`); "
        "nothing was charged."
    },
    status.HTTP_403_FORBIDDEN: {
        "description": "Administrator accounts can't place orders (`admin-cannot-buy`)."
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
    secret: bytes = state.checkout_fingerprint_secret
    return Checkout(
        ordering,
        payments,
        clock,
        fingerprint_secret=secret,
        key_lifetime=lifetime,
        transient=transient,
    )


def get_get_order(request: Request) -> GetOrder:
    ordering: OrderingUnitOfWorkFactory = request.app.state.ordering_unit_of_work
    return GetOrder(ordering)


def command_of(body: CheckoutRequest, key: UUID, buyer_id: UUID | None = None) -> CheckoutCommand:
    payment = body.payment
    return CheckoutCommand(
        idempotency_key=key,
        buyer_id=buyer_id,
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
    principal: Annotated[Principal | None, Depends(optional_principal)],
) -> Response | OrderResponse:
    if principal is not None and principal.is_admin:
        raise AdminCannotBuy()
    buyer_id = principal.account_id if principal is not None else None
    result = await use_case.execute(command_of(body, key, buyer_id))
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


def get_quote_cart(request: Request) -> QuoteCart:
    ordering: OrderingUnitOfWorkFactory = request.app.state.ordering_unit_of_work
    return QuoteCart(ordering)


@router.post(
    "/quote",
    response_model=QuoteResponse,
    summary="Price a cart from the catalog without buying anything",
)
async def quote_cart(
    body: QuoteRequest, use_case: Annotated[QuoteCart, Depends(get_quote_cart)]
) -> QuoteResponse:
    quote = await use_case.execute(tuple((line.sku, line.quantity) for line in body.lines))
    return QuoteResponse.of(quote)


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "The order was not found."}},
)
async def get_order(
    order_id: UUID, use_case: Annotated[GetOrder, Depends(get_get_order)]
) -> OrderResponse:
    return OrderResponse.of(await use_case.execute(order_id))


me_router = APIRouter(prefix="/me", tags=["orders"])

MAX_MY_ORDERS_PAGE = 10_000


def get_list_buyer_orders(request: Request) -> ListBuyerOrders:
    ordering: OrderingUnitOfWorkFactory = request.app.state.ordering_unit_of_work
    return ListBuyerOrders(ordering)


@me_router.get(
    "/orders",
    response_model=BuyerOrdersResponse,
    responses=BUYER_ONLY_RESPONSES,
    summary="My orders: the logged-in customer's own orders, newest first",
)
async def my_orders(
    buyer: Annotated[Principal, Depends(require_buyer)],
    use_case: Annotated[ListBuyerOrders, Depends(get_list_buyer_orders)],
    page: Annotated[int, Query(ge=1, le=MAX_MY_ORDERS_PAGE)] = 1,
) -> BuyerOrdersResponse:
    result = await use_case.execute(buyer.account_id, page)
    return BuyerOrdersResponse(
        items=[OrderResponse.of(order) for order in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


admin_orders_router = APIRouter(
    prefix="/admin/orders",
    tags=["orders"],
    dependencies=[Depends(require_admin)],
    responses=ADMIN_ONLY_RESPONSES,
)

MAX_ADMIN_ORDERS_PAGE = 100_000


def get_search_orders(request: Request) -> SearchOrders:
    ordering: OrderingUnitOfWorkFactory = request.app.state.ordering_unit_of_work
    return SearchOrders(ordering)


@admin_orders_router.get(
    "", response_model=AdminOrdersResponse, summary="Every order, newest first"
)
async def search_orders(
    use_case: Annotated[SearchOrders, Depends(get_search_orders)],
    q: Annotated[
        str | None,
        Query(max_length=MAX_ORDER_SEARCH, description="Customer name or email, or order number."),
    ] = None,
    status_filter: Annotated[OrderStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1, le=MAX_ADMIN_ORDERS_PAGE)] = 1,
) -> AdminOrdersResponse:
    result = await use_case.execute(OrderSearch(q=q, status=status_filter, page=page))
    return AdminOrdersResponse(
        items=[AdminOrderResponse.of_order(order) for order in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@admin_orders_router.get(
    "/{order_id}",
    response_model=AdminOrderResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "The order was not found."}},
    summary="One order in full",
)
async def admin_order(
    order_id: UUID, use_case: Annotated[GetOrder, Depends(get_get_order)]
) -> AdminOrderResponse:
    return AdminOrderResponse.of_order(await use_case.execute(order_id))
