from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status

from ecommerce.catalog.api.import_schemas import (
    ImportBatchResponse,
    ImportPreviewResponse,
    ImportRowChangeResponse,
    ResolveRowRequest,
)
from ecommerce.catalog.application.importing import (
    DEFAULT_FILE_NAME,
    MAX_FILE_BYTES,
    CommitImport,
    DiscardImport,
    ExistingProducts,
    GetImport,
    ImportFileReader,
    ImportFileRejected,
    PreviewImport,
    ResolveImportRow,
    StartImport,
)
from ecommerce.catalog.application.unit_of_work import CatalogUnitOfWorkFactory
from ecommerce.catalog.domain.importing.batch import RowAction
from ecommerce.catalog.domain.importing.policies import ImportPolicies
from ecommerce.shared_kernel.api.access import ADMIN_ONLY_RESPONSES, require_actor, require_admin
from ecommerce.shared_kernel.api.exception_handlers import validation_problem
from ecommerce.shared_kernel.api.problem_details import (
    PAYLOAD_TOO_LARGE,
    UNSUPPORTED_MEDIA_TYPE,
    problem_response,
)
from ecommerce.shared_kernel.api.validation import FieldError, InvalidParameters
from ecommerce.shared_kernel.application.ports import Clock
from ecommerce.shared_kernel.domain.actor import Actor
from ecommerce.shared_kernel.domain.errors import ValidationIssue

MAX_FILE_NAME_LENGTH = 255
MAX_LINE = 10_000_000

router = APIRouter(
    prefix="/imports",
    tags=["imports"],
    dependencies=[Depends(require_admin)],
    responses=ADMIN_ONLY_RESPONSES,
)

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


ActorName = Annotated[Actor, Depends(require_actor)]
FileName = Annotated[
    str | None,
    Query(
        min_length=1,
        max_length=MAX_FILE_NAME_LENGTH,
        description="The name of the uploaded file, shown in the review screen.",
    ),
]
Line = Annotated[int, Path(ge=1, le=MAX_LINE, description="The line number in the file.")]

NOT_FOUND: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": "The import or the line was not found."}
}
CHANGE_RESPONSES: dict[int | str, dict[str, Any]] = {
    **NOT_FOUND,
    status.HTTP_409_CONFLICT: {
        "description": "The import is no longer pending, or the row cannot be resolved that way."
    },
}
COMMIT_RESPONSES: dict[int | str, dict[str, Any]] = {
    **NOT_FOUND,
    status.HTTP_409_CONFLICT: {
        "description": (
            "Rows still need a decision (`import-not-committable`), products changed after the "
            "file was checked (`import-stale-rows`), or the import is no longer pending."
        )
    },
}


def catalog_of(request: Request) -> CatalogUnitOfWorkFactory:
    catalog: CatalogUnitOfWorkFactory = request.app.state.catalog_unit_of_work
    return catalog


def clock_of(request: Request) -> Clock:
    clock: Clock = request.app.state.clock
    return clock


def policies_of(request: Request) -> ImportPolicies:
    policies: ImportPolicies = request.app.state.import_policies
    return policies


def get_start_import(request: Request) -> StartImport:
    state = request.app.state
    reader: ImportFileReader = state.import_reader
    products: ExistingProducts = state.existing_products
    return StartImport(
        reader, products, catalog_of(request), policies_of(request), clock_of(request)
    )


def get_get_import(request: Request) -> GetImport:
    return GetImport(catalog_of(request), clock_of(request))


def get_resolve_row(request: Request) -> ResolveImportRow:
    return ResolveImportRow(catalog_of(request), policies_of(request), clock_of(request))


def get_commit_import(request: Request) -> CommitImport:
    return CommitImport(catalog_of(request), policies_of(request), clock_of(request))


def get_discard_import(request: Request) -> DiscardImport:
    return DiscardImport(catalog_of(request), clock_of(request))


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a CSV file and keep it for review",
    description=(
        "Classifies every row like the preview, then keeps the import in `PENDING_REVIEW` "
        "until a person resolves the flagged rows and commits it. Nothing reaches the catalog "
        "yet."
    ),
    openapi_extra=CSV_BODY,
    responses=RESPONSES,
)
async def start_import(
    request: Request,
    response: Response,
    actor: ActorName,
    use_case: Annotated[StartImport, Depends(get_start_import)],
    file_name: FileName = None,
) -> ImportBatchResponse:
    content = await read_body(request, MAX_FILE_BYTES)
    name = (file_name or "").strip() or DEFAULT_FILE_NAME
    state = await use_case.execute(content, request.headers.get("content-type"), name, actor)
    response.headers["Location"] = f"{request.url.path}/{state.batch.id}"
    return ImportBatchResponse.of(state)


@router.get(
    "/{batch_id}",
    summary="Get an import with every row and its outcome",
    responses=NOT_FOUND,
)
async def get_import(
    batch_id: UUID, use_case: Annotated[GetImport, Depends(get_get_import)]
) -> ImportBatchResponse:
    return ImportBatchResponse.of(await use_case.execute(batch_id))


@router.patch(
    "/{batch_id}/rows/{line}",
    summary="Resolve a row: confirm, correct or skip",
    description=(
        "`confirm` accepts a price or weight of 0, or confirms an update. `correct` sends new "
        "values for a row held for review; the row is checked again. `skip` leaves the row out "
        "of the import."
    ),
    responses=CHANGE_RESPONSES,
)
async def resolve_row(
    batch_id: UUID,
    line: Line,
    body: ResolveRowRequest,
    actor: ActorName,
    use_case: Annotated[ResolveImportRow, Depends(get_resolve_row)],
) -> ImportRowChangeResponse:
    if body.values is not None and body.action is not RowAction.CORRECT:
        raise InvalidParameters(
            "body",
            [
                ValidationIssue(
                    "values", "not_allowed", "Values are only sent with the action correct."
                )
            ],
        )
    if body.action is RowAction.CONFIRM and body.expected_outcome is None:
        raise InvalidParameters(
            "body",
            [
                ValidationIssue(
                    "expected_outcome",
                    "required",
                    "Send the row outcome that was shown when it was confirmed.",
                )
            ],
        )
    if body.action is not RowAction.CONFIRM and body.expected_outcome is not None:
        raise InvalidParameters(
            "body",
            [
                ValidationIssue(
                    "expected_outcome",
                    "not_allowed",
                    "The expected outcome is only sent with the action confirm.",
                )
            ],
        )
    values = body.values.provided() if body.values is not None else None
    change = await use_case.execute(
        batch_id,
        line,
        body.action,
        values,
        actor,
        expected_outcome=body.expected_outcome,
    )
    return ImportRowChangeResponse.of(change)


@router.post(
    "/{batch_id}/commit",
    summary="Apply the import to the catalog in one transaction",
    description=(
        "Creates the new products and applies the confirmed updates, all or nothing. "
        "Committing an import that is already committed returns it unchanged."
    ),
    responses=COMMIT_RESPONSES,
)
async def commit_import(
    batch_id: UUID,
    actor: ActorName,
    use_case: Annotated[CommitImport, Depends(get_commit_import)],
) -> ImportBatchResponse:
    return ImportBatchResponse.of(await use_case.execute(batch_id, actor))


@router.delete(
    "/{batch_id}",
    summary="Discard an import",
    description="The import and its rows are kept for the audit trail; nothing is imported.",
    responses=CHANGE_RESPONSES,
)
async def discard_import(
    batch_id: UUID,
    actor: ActorName,
    use_case: Annotated[DiscardImport, Depends(get_discard_import)],
) -> ImportBatchResponse:
    return ImportBatchResponse.of(await use_case.execute(batch_id, actor))
