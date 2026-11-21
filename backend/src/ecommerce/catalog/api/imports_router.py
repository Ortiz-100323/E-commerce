from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status

from ecommerce.catalog.api.import_schemas import ImportPreviewResponse
from ecommerce.catalog.application.importing import (
    MAX_FILE_BYTES,
    ExistingProducts,
    ImportFileReader,
    ImportFileRejected,
    PreviewImport,
)
from ecommerce.catalog.domain.importing.policies import ImportPolicies
from ecommerce.shared_kernel.api.exception_handlers import validation_problem
from ecommerce.shared_kernel.api.problem_details import (
    PAYLOAD_TOO_LARGE,
    UNSUPPORTED_MEDIA_TYPE,
    problem_response,
)
from ecommerce.shared_kernel.api.validation import FieldError

router = APIRouter(prefix="/imports", tags=["imports"])

CSV_BODY: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "description": "The CSV file itself, sent as the request body (at most 5 MB, UTF-8).",
        "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
    }
}

RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_413_CONTENT_TOO_LARGE: {"description": "The file is larger than 5 MB."},
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"description": "The file is not a CSV."},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "description": "The file cannot be read: encoding, header, row limit or CSV syntax."
    },
}


def get_preview_import(request: Request) -> PreviewImport:
    state = request.app.state
    reader: ImportFileReader = state.import_reader
    products: ExistingProducts = state.existing_products
    policies: ImportPolicies = state.import_policies
    return PreviewImport(reader, products, policies)


async def read_body(request: Request, limit: int) -> bytes:
    received = bytearray()
    async for chunk in request.stream():
        received.extend(chunk)
        if len(received) > limit:
            raise ImportFileRejected(
                "file_too_large", f"The file is larger than {limit} bytes.", max_bytes=limit
            )
    return bytes(received)


async def handle_import_file_rejected(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, ImportFileRejected)
    if exc.code == "file_too_large":
        return problem_response(
            request,
            PAYLOAD_TOO_LARGE,
            detail=exc.message,
            extra={"max_bytes": exc.params["max_bytes"]},
        )
    if exc.code == "unsupported_media_type":
        return problem_response(request, UNSUPPORTED_MEDIA_TYPE, detail=exc.message)
    return validation_problem(
        request,
        [
            FieldError(
                location="body", field="file", code=exc.code, message=exc.message, params=exc.params
            )
        ],
    )


@router.post(
    "/preview",
    summary="Classify a CSV file without importing anything",
    description=(
        "Reads the file, checks every row against the import rules and the catalog, and returns "
        "the outcome of each row. Nothing is stored."
    ),
    openapi_extra=CSV_BODY,
    responses=RESPONSES,
)
async def preview_import(
    request: Request,
    use_case: Annotated[PreviewImport, Depends(get_preview_import)],
) -> ImportPreviewResponse:
    content = await read_body(request, MAX_FILE_BYTES)
    preview = await use_case.execute(content, request.headers.get("content-type"))
    return ImportPreviewResponse.of(preview)
