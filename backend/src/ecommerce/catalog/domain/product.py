from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import NewType, Self, TypedDict
from uuid import UUID, uuid4

from ecommerce.catalog.domain.errors import InsufficientStock, InvalidProduct, ProductNotSellable
from ecommerce.catalog.domain.events import (
    AuditValue,
    FieldChange,
    ProductArchived,
    ProductChanged,
    ProductCreated,
    ProductEvent,
    ProductRestored,
    StockDecreased,
)
from ecommerce.catalog.domain.value_objects import (
    Category,
    Description,
    Price,
    ProductName,
    ProductTag,
    Sku,
    StockQuantity,
    Weight,
)
from ecommerce.shared_kernel.domain.errors import IssueCollector, ValidationIssue

ProductId = NewType("ProductId", UUID)
Amount = Decimal | int | str
INITIAL_VERSION = 1

ZERO_PRICE_MESSAGES = {
    "price": "A price of 0 must be confirmed as a gift.",
    "gift": "A product priced at 0 must stay a gift. Set a price above 0 first.",
}


class EventBase(TypedDict):
    product_id: UUID
    sku: str
    occurred_at: datetime


def new_product_id() -> ProductId:
    return ProductId(uuid4())


class ProductStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


def zero_price_issue(field: str) -> ValidationIssue:
    return ValidationIssue(field, "zero_price_requires_gift", ZERO_PRICE_MESSAGES[field])


def breaks_gift_rule(price: Price, tags: frozenset[ProductTag]) -> bool:
    return price.is_zero and ProductTag.GIFT not in tags


def tags_with_gift(tags: frozenset[ProductTag], gift: bool) -> frozenset[ProductTag]:
    return tags | {ProductTag.GIFT} if gift else tags - {ProductTag.GIFT}


def whole_quantity(quantity: int) -> int:
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise TypeError("Quantities must be whole numbers.")
    return quantity


def keep_if_equal[T](parsed: T | None, current: T) -> T | None:
    return current if parsed == current else parsed


@dataclass(frozen=True)
class ProductDetails:
    name: ProductName
    description: Description
    category: Category
    price: Price
    stock: StockQuantity
    weight: Weight
    tags: frozenset[ProductTag]

    def __post_init__(self) -> None:
        if breaks_gift_rule(self.price, self.tags):
            raise InvalidProduct([zero_price_issue("price")])

    def snapshot(self) -> dict[str, AuditValue]:
        return {
            "name": self.name.value,
            "description": self.description.value,
            "category": self.category.value,
            "price": str(self.price.amount),
            "stock": self.stock.value,
            "weight_kg": str(self.weight.kg),
            "tags": tuple(sorted(tag.value for tag in self.tags)),
        }


class Product:
    def __init__(
        self,
        *,
        product_id: ProductId,
        sku: Sku,
        details: ProductDetails,
        status: ProductStatus,
        version: int,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        self._id = product_id
        self._sku = sku
        self._details = details
        self._status = status
        self._version = version
        self._created_at = created_at
        self._updated_at = updated_at
        self._events: list[ProductEvent] = []

    @classmethod
    def create(
        cls,
        *,
        product_id: ProductId,
        sku: str,
        name: str,
        description: str,
        category: str,
        price: Amount,
        stock: int,
        weight_kg: Amount,
        gift: bool,
        at: datetime,
    ) -> Self:
        collector = IssueCollector()
        parsed_sku = collector.attempt(Sku, sku)
        parsed_name = collector.attempt(ProductName, name)
        parsed_description = collector.attempt(Description, description)
        parsed_category = collector.attempt(Category, category)
        parsed_price = collector.attempt(Price.of, price)
        parsed_stock = collector.attempt(StockQuantity, stock)
        parsed_weight = collector.attempt(Weight.of, weight_kg)
        tags = tags_with_gift(frozenset(), gift)
        if parsed_price is not None and breaks_gift_rule(parsed_price, tags):
            collector.add(zero_price_issue("price"))
        if (
            parsed_sku is None
            or parsed_name is None
            or parsed_description is None
            or parsed_category is None
            or parsed_price is None
            or parsed_stock is None
            or parsed_weight is None
            or collector.issues
        ):
            raise InvalidProduct(collector.issues)

        product = cls(
            product_id=product_id,
            sku=parsed_sku,
            details=ProductDetails(
                name=parsed_name,
                description=parsed_description,
                category=parsed_category,
                price=parsed_price,
                stock=parsed_stock,
                weight=parsed_weight,
                tags=tags,
            ),
            status=ProductStatus.ACTIVE,
            version=INITIAL_VERSION,
            created_at=at,
            updated_at=at,
        )
        product._record(ProductCreated(**product._event_base(at), snapshot=product.snapshot()))
        return product

    @property
    def id(self) -> ProductId:
        return self._id

    @property
    def sku(self) -> Sku:
        return self._sku

    @property
    def name(self) -> ProductName:
        return self._details.name

    @property
    def description(self) -> Description:
        return self._details.description

    @property
    def category(self) -> Category:
        return self._details.category

    @property
    def price(self) -> Price:
        return self._details.price

    @property
    def stock(self) -> StockQuantity:
        return self._details.stock

    @property
    def weight(self) -> Weight:
        return self._details.weight

    @property
    def tags(self) -> frozenset[ProductTag]:
        return self._details.tags

    @property
    def is_gift(self) -> bool:
        return ProductTag.GIFT in self._details.tags

    @property
    def status(self) -> ProductStatus:
        return self._status

    @property
    def version(self) -> int:
        return self._version

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def is_sellable(self) -> bool:
        return self._status is ProductStatus.ACTIVE and not self.stock.is_empty

    def snapshot(self) -> dict[str, AuditValue]:
        return {"sku": self._sku.value, **self._details.snapshot(), "status": self._status.value}

    def pull_events(self) -> list[ProductEvent]:
        events, self._events = self._events, []
        return events

    def revise(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        category: str | None = None,
        price: Amount | None = None,
        stock: int | None = None,
        weight_kg: Amount | None = None,
        gift: bool | None = None,
        at: datetime,
    ) -> None:
        current = self._details
        collector = IssueCollector()
        new_name = (
            current.name
            if name is None
            else keep_if_equal(collector.attempt(ProductName, name), current.name)
        )
        new_description = (
            current.description
            if description is None
            else keep_if_equal(collector.attempt(Description, description), current.description)
        )
        new_category = (
            current.category
            if category is None
            else keep_if_equal(collector.attempt(Category, category), current.category)
        )
        new_price = (
            current.price
            if price is None
            else keep_if_equal(collector.attempt(Price.of, price), current.price)
        )
        new_stock = (
            current.stock
            if stock is None
            else keep_if_equal(collector.attempt(StockQuantity, stock), current.stock)
        )
        new_weight = (
            current.weight
            if weight_kg is None
            else keep_if_equal(collector.attempt(Weight.of, weight_kg), current.weight)
        )
        tags = current.tags if gift is None else tags_with_gift(current.tags, gift)
        if new_price is not None and breaks_gift_rule(new_price, tags):
            collector.add(zero_price_issue("price" if price is not None else "gift"))
        if (
            new_name is None
            or new_description is None
            or new_category is None
            or new_price is None
            or new_stock is None
            or new_weight is None
            or collector.issues
        ):
            raise InvalidProduct(collector.issues)

        self._apply(
            ProductDetails(
                name=new_name,
                description=new_description,
                category=new_category,
                price=new_price,
                stock=new_stock,
                weight=new_weight,
                tags=tags,
            ),
            at,
        )

    def rename(self, name: str, *, at: datetime) -> None:
        self.revise(name=name, at=at)

    def reprice(self, price: Amount, *, at: datetime) -> None:
        self.revise(price=price, at=at)

    def recategorize(self, category: str, *, at: datetime) -> None:
        self.revise(category=category, at=at)

    def restock(self, quantity: int, *, at: datetime) -> None:
        if whole_quantity(quantity) < 1:
            raise InvalidProduct(
                [
                    ValidationIssue(
                        "quantity", "too_small", "Restock at least 1 unit.", params={"min": 1}
                    )
                ]
            )
        self.revise(stock=self.stock.value + quantity, at=at)

    def mark_as_gift(self, *, at: datetime) -> None:
        self.revise(gift=True, at=at)

    def unmark_gift(self, *, at: datetime) -> None:
        self.revise(gift=False, at=at)

    def decrease_stock(self, quantity: int, *, order_reference: str, at: datetime) -> None:
        if whole_quantity(quantity) < 1:
            raise ValueError("The quantity to decrease must be at least 1.")
        if self._status is ProductStatus.ARCHIVED:
            raise ProductNotSellable(self._sku.value, "archived")
        before = self.stock.value
        if quantity > before:
            raise InsufficientStock(self._sku.value, quantity, before)
        self._details = replace(self._details, stock=StockQuantity(before - quantity))
        self._updated_at = at
        self._record(
            StockDecreased(
                **self._event_base(at),
                quantity=quantity,
                stock_before=before,
                stock_after=before - quantity,
                order_reference=order_reference,
            )
        )

    def archive(self, *, at: datetime) -> None:
        if self._status is ProductStatus.ARCHIVED:
            return
        self._status = ProductStatus.ARCHIVED
        self._updated_at = at
        self._record(ProductArchived(**self._event_base(at)))

    def restore(self, *, at: datetime) -> None:
        if self._status is ProductStatus.ACTIVE:
            return
        self._status = ProductStatus.ACTIVE
        self._updated_at = at
        self._record(ProductRestored(**self._event_base(at)))

    def _apply(self, details: ProductDetails, at: datetime) -> None:
        before = self._details.snapshot()
        after = details.snapshot()
        changes = {
            field: FieldChange(before[field], after[field])
            for field in after
            if before[field] != after[field]
        }
        if not changes:
            return
        self._details = details
        self._updated_at = at
        self._record(ProductChanged(**self._event_base(at), changes=changes))

    def _event_base(self, at: datetime) -> EventBase:
        return {"product_id": self._id, "sku": self._sku.value, "occurred_at": at}

    def _record(self, event: ProductEvent) -> None:
        self._events.append(event)
