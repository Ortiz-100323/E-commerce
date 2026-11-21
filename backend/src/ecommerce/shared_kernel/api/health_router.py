from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel

from ecommerce.shared_kernel.application.ports import DatabaseProbe

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["up", "down"]


def get_database_probe(request: Request) -> DatabaseProbe:
    probe: DatabaseProbe = request.app.state.database_probe
    return probe


@router.get(
    "/health",
    summary="Liveness and database check",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def health(
    response: Response, probe: Annotated[DatabaseProbe, Depends(get_database_probe)]
) -> HealthResponse:
    if await probe.is_up():
        return HealthResponse(status="ok", database="up")
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status="unavailable", database="down")
