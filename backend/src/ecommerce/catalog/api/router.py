from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from ecommerce.catalog.api.schemas import (
    AuditEntryResponse,
    CategoriesResponse,
    ProductCreateRequest,
    ProductHistoryResponse,
    ProductPageResponse,
    ProductResponse,
    ProductUpdateRequest,
)
from ecommerce.catalog.application.get_product_history import GetProductHistory
from ecommerce.catalog.application.products import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    ArchiveProduct,
    CreateProduct,
    GetProduct,
    ListCategories,
    ProductQueries,
    ProductQuery,
    ProductSort,
    RestoreProduct,
    SearchProducts,
    StatusFilter,
    UpdateProduct,
)
from ecommerce.catalog.application.unit_of_work import CatalogUnitOfWorkFactory
from ecommerce.catalog.domain.value_objects import ProductTag
from ecommerce.shared_kernel.api.access import (
    ADMIN_ONLY_RESPONSES,
    SessionToken,
    admin_of,
    require_actor,
    require_admin,
)
from ecommerce.shared_kernel.api.validation import InvalidParameters
from ecommerce.shared_kernel.application.ports import Clock
from ecommerce.shared_kernel.domain.actor import Actor
from ecommerce.shared_kernel.domain.errors import ValidationIssue

MAX_QUERY_TEXT = 200
MAX_PAGE = 100_000

Responses = dict[int | str, dict[str, Any]]

router = APIRouter(prefix="/products", tags=["products"])
categories_router = APIRouter(prefix="/categories", tags=["products"])

NOT_FOUND: Responses = {status.HTTP_404_NOT_FOUND: {"description": "The product was not found."}}
VERSION_CONFLICT: Responses = {
    status.HTTP_409_CONFLICT: {"description": "Someone else saved the product first."}
}
DUPLICATE_SKU: Responses = {status.HTTP_409_CONFLICT: {"description": "The SKU is already taken."}}
ADMIN_ONLY: Responses = ADMIN_ONLY_RESPONSES

ActorName = Annotated[Actor, Depends(require_actor)]


def catalog_of(request: Request) -> CatalogUnitOfWorkFactory:
    catalog: CatalogUnitOfWorkFactory = request.app.state.catalog_unit_of_work
    return catalog


def clock_of(request: Request) -> Clock:
    clock: Clock = request.app.state.clock
    return clock


def queries_of(request: Request) -> ProductQueries:
    queries: ProductQueries = request.app.state.catalog_queries
    return queries


def get_create_product(request: Request) -> CreateProduct:
    return CreateProduct(catalog_of(request), clock_of(request))


def get_update_product(request: Request) -> UpdateProduct:
    return UpdateProduct(catalog_of(request), clock_of(request))


def get_archive_product(request: Request) -> ArchiveProduct:
    return ArchiveProduct(catalog_of(request), clock_of(request))


def get_restore_product(request: Request) -> RestoreProduct:
    return RestoreProduct(catalog_of(request), clock_of(request))


def get_get_product(request: Request) -> GetProduct:
    return GetProduct(catalog_of(request))


def get_search_products(request: Request) -> SearchProducts:
    return SearchProducts(queries_of(request))


def get_list_categories(request: Request) -> ListCategories:
    return ListCategories(queries_of(request))


def get_product_history(request: Request) -> GetProductHistory:
    return GetProductHistory(catalog_of(request))


def product_query(
    q: Annotated[
        str | None,
        Query(max_length=MAX_QUERY_TEXT, description="Searches name, SKU and description."),
    ] = None,
    category: Annotated[str | None, Query(max_length=MAX_QUERY_TEXT)] = None,
    min_price: Annotated[Decimal | None, Query(ge=0)] = None,
    max_price: Annotated[Decimal | None, Query(ge=0)] = None,
    in_stock: Annotated[bool | None, Query()] = None,
    tag: Annotated[ProductTag | None, Query()] = None,
    status_filter: Annotated[
        StatusFilter,
        Query(alias="status", description="ACTIVE (the default), ARCHIVED or ALL."),
    ] = StatusFilter.ACTIVE,
    sort: Annotated[ProductSort, Query()] = ProductSort.NAME,
    page: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> ProductQuery:
    if min_price is not None and max_price is not None and min_price > max_price:
        raise InvalidParameters(
            "query",
            [
                ValidationIssue(
                    "max_price",
                    "invalid_range",
                    "The maximum price must not be below the minimum price.",
                    params={"min_price": str(min_price)},
                )
            ],
        )
    return ProductQuery(
        q=q,
        category=category,
        min_price=min_price,
        max_price=max_price,
        in_stock=in_stock,
        tag=tag,
        status=status_filter,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a product",
    responses={**DUPLICATE_SKU, **ADMIN_ONLY},
)
async def create_product(
    body: ProductCreateRequest,
    actor: ActorName,
    request: Request,
    response: Response,
    use_case: Annotated[CreateProduct, Depends(get_create_product)],
) -> ProductResponse:
    view = await use_case.execute(body.new_product(), actor)
    response.headers["Location"] = f"{request.url.path}/{view.id}"
    return ProductResponse.of(view)


@router.get(
    "",
    summary="Search products",
    description="Active products are public. `status=ARCHIVED` or `ALL` needs an admin's session.",
    responses=ADMIN_ONLY,
)
async def search_products(
    request: Request,
    token: SessionToken,
    query: Annotated[ProductQuery, Depends(product_query)],
    use_case: Annotated[SearchProducts, Depends(get_search_products)],
) -> ProductPageResponse:
    if query.status is not StatusFilter.ACTIVE:
        await admin_of(request, token)
    return ProductPageResponse.of(await use_case.execute(query))


@router.get("/{product_id}", summary="Read a product", responses=NOT_FOUND)
async def get_product(
    product_id: UUID,
    use_case: Annotated[GetProduct, Depends(get_get_product)],
) -> ProductResponse:
    return ProductResponse.of(await use_case.execute(product_id))


@router.put(
    "/{product_id}",
    summary="Replace a product's details (send the version you read)",
    responses={**NOT_FOUND, **VERSION_CONFLICT, **ADMIN_ONLY},
)
async def update_product(
    product_id: UUID,
    body: ProductUpdateRequest,
    actor: ActorName,
    use_case: Annotated[UpdateProduct, Depends(get_update_product)],
) -> ProductResponse:
    view = await use_case.execute(product_id, body.version, body.fields(), actor)
    return ProductResponse.of(view)


@router.delete(
    "/{product_id}",
    summary="Archive a product (it is hidden from the shop, never deleted)",
    responses={**NOT_FOUND, **ADMIN_ONLY},
)
async def archive_product(
    product_id: UUID,
    actor: ActorName,
    use_case: Annotated[ArchiveProduct, Depends(get_archive_product)],
) -> ProductResponse:
    return ProductResponse.of(await use_case.execute(product_id, actor))


@router.post(
    "/{product_id}/restore",
    summary="Restore an archived product",
    responses={**NOT_FOUND, **ADMIN_ONLY},
)
async def restore_product(
    product_id: UUID,
    actor: ActorName,
    use_case: Annotated[RestoreProduct, Depends(get_restore_product)],
) -> ProductResponse:
    return ProductResponse.of(await use_case.execute(product_id, actor))


@router.get(
    "/{product_id}/history",
    summary="The product's audit timeline, oldest first",
    responses={**NOT_FOUND, **ADMIN_ONLY},
    dependencies=[Depends(require_admin)],
)
async def product_history(
    product_id: UUID,
    use_case: Annotated[GetProductHistory, Depends(get_product_history)],
) -> ProductHistoryResponse:
    entries = await use_case.execute(product_id)
    return ProductHistoryResponse(
        product_id=product_id,
        entries=[AuditEntryResponse.model_validate(entry) for entry in entries],
    )


@categories_router.get("", summary="Categories of active products")
async def list_categories(
    use_case: Annotated[ListCategories, Depends(get_list_categories)],
) -> CategoriesResponse:
    return CategoriesResponse(items=await use_case.execute())
