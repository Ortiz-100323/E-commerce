from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ecommerce.catalog.application.products import (
    NewProduct,
    ProductFields,
    ProductPage,
    ProductView,
)

MAX_TEXT = 10_000

StrictInt = Annotated[int, Field(strict=True)]
StrictBool = Annotated[bool, Field(strict=True)]


class ProductFieldsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=MAX_TEXT, examples=["Running Shoes"])
    description: str = Field(default="", max_length=MAX_TEXT, examples=["Lightweight shoes."])
    category: str = Field(max_length=MAX_TEXT, examples=["Sports"])
    price: Decimal = Field(examples=["89.99"], description="In USD, at most 2 decimal places.")
    stock: StrictInt = Field(examples=[10])
    weight_kg: Decimal = Field(examples=["0.800"], description="At most 3 decimal places.")
    gift: StrictBool = Field(
        default=False, description="Required to confirm a price of 0 as a free gift."
    )

    def fields(self) -> ProductFields:
        return ProductFields(
            name=self.name,
            description=self.description,
            category=self.category,
            price=self.price,
            stock=self.stock,
            weight_kg=self.weight_kg,
            gift=self.gift,
        )


class ProductCreateRequest(ProductFieldsRequest):
    sku: str = Field(max_length=MAX_TEXT, examples=["RS-001"])

    def new_product(self) -> NewProduct:
        return NewProduct(sku=self.sku, **vars(self.fields()))


class ProductUpdateRequest(ProductFieldsRequest):
    version: StrictInt = Field(ge=1, examples=[1], description="The version you read.")


class ProductResponse(BaseModel):
    id: UUID
    sku: str
    name: str
    description: str
    category: str
    price: str = Field(examples=["89.99"])
    currency: str = Field(examples=["USD"])
    stock: int
    weight_kg: str = Field(examples=["0.800"])
    gift: bool
    tags: list[str]
    status: str = Field(examples=["ACTIVE"])
    is_sellable: bool
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, view: ProductView) -> Self:
        return cls(
            id=view.id,
            sku=view.sku,
            name=view.name,
            description=view.description,
            category=view.category,
            price=str(view.price),
            currency=view.currency,
            stock=view.stock,
            weight_kg=str(view.weight_kg),
            gift=view.gift,
            tags=list(view.tags),
            status=view.status,
            is_sellable=view.is_sellable,
            version=view.version,
            created_at=view.created_at,
            updated_at=view.updated_at,
        )


class ProductPageResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int

    @classmethod
    def of(cls, page: ProductPage) -> Self:
        return cls(
            items=[ProductResponse.of(view) for view in page.items],
            total=page.total,
            page=page.page,
            page_size=page.page_size,
        )


class CategoriesResponse(BaseModel):
    items: list[str] = Field(examples=[["Electronics", "Sports"]])


class AuditEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event: str
    occurred_at: datetime
    actor: str
    sku: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    context: dict[str, Any]


class ProductHistoryResponse(BaseModel):
    product_id: UUID
    entries: list[AuditEntryResponse]
