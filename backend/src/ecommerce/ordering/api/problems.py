from collections.abc import Mapping
from typing import Any

from ecommerce.ordering.application.errors import IdempotencyKeyReused
from ecommerce.ordering.domain.errors import NotEnoughStock, ProductsNotSellable
from ecommerce.shared_kernel.api.problem_details import ProblemMapping, ProblemType

PAYMENT_DECLINED = ProblemType("payment-declined", 402, "The card was declined.")
PRODUCT_NOT_SELLABLE = ProblemType(
    "product-not-sellable", 409, "Some products in the cart can't be bought right now."
)
INSUFFICIENT_STOCK = ProblemType(
    "insufficient-stock", 409, "Some items are no longer available in the requested quantity."
)
IDEMPOTENCY_KEY_MISSING = ProblemType(
    "idempotency-key-missing", 400, "The Idempotency-Key header is required."
)
IDEMPOTENCY_KEY_INVALID = ProblemType(
    "idempotency-key-invalid", 400, "The Idempotency-Key header must be a UUID."
)
IDEMPOTENCY_KEY_REUSED = ProblemType(
    "idempotency-key-reused",
    422,
    "This Idempotency-Key was already used for a different request.",
)

REASONS = {
    "unknown": "is not in the catalog",
    "archived": "is no longer sold",
    "out_of_stock": "is out of stock",
}


class IdempotencyKeyMissing(Exception):
    pass


class IdempotencyKeyInvalid(Exception):
    pass


def not_sellable_detail(error: Exception) -> str:
    assert isinstance(error, ProductsNotSellable)
    return "; ".join(f"{item.sku} {REASONS[item.reason]}" for item in error.items) + "."


def not_sellable_extra(error: Exception) -> Mapping[str, Any]:
    assert isinstance(error, ProductsNotSellable)
    return {"items": [{"sku": item.sku, "reason": item.reason} for item in error.items]}


def short_detail(error: Exception) -> str:
    assert isinstance(error, NotEnoughStock)
    return (
        "; ".join(
            f"{item.sku}: you asked for {item.requested}, {item.available} available"
            for item in error.items
        )
        + "."
    )


def short_extra(error: Exception) -> Mapping[str, Any]:
    assert isinstance(error, NotEnoughStock)
    return {
        "items": [
            {"sku": item.sku, "requested": item.requested, "available": item.available}
            for item in error.items
        ]
    }


ORDERING_PROBLEMS: Mapping[type[Exception], ProblemMapping] = {
    ProductsNotSellable: ProblemMapping(
        PRODUCT_NOT_SELLABLE, detail=not_sellable_detail, extra=not_sellable_extra
    ),
    NotEnoughStock: ProblemMapping(INSUFFICIENT_STOCK, detail=short_detail, extra=short_extra),
    IdempotencyKeyMissing: ProblemMapping(IDEMPOTENCY_KEY_MISSING),
    IdempotencyKeyInvalid: ProblemMapping(IDEMPOTENCY_KEY_INVALID),
    IdempotencyKeyReused: ProblemMapping(IDEMPOTENCY_KEY_REUSED),
}
