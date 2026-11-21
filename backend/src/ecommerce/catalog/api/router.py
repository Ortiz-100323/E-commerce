from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from ecommerce.catalog.api.schemas import AuditEntryResponse, ProductHistoryResponse
from ecommerce.catalog.application.get_product_history import GetProductHistory
from ecommerce.catalog.application.unit_of_work import CatalogUnitOfWorkFactory

router = APIRouter(prefix="/products", tags=["products"])


def get_product_history(request: Request) -> GetProductHistory:
    unit_of_work: CatalogUnitOfWorkFactory = request.app.state.catalog_unit_of_work
    return GetProductHistory(unit_of_work)


@router.get(
    "/{product_id}/history",
    summary="The product's audit timeline, oldest first",
    responses={status.HTTP_404_NOT_FOUND: {"description": "The product was not found."}},
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
