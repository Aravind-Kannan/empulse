from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.investigation import (
    IncidentListResponse,
    IncidentStatus,
    IncidentStatusUpdate,
    IncidentSummary,
    InvestigationChatRequest,
)
from app.services.investigation import (
    INCIDENT_STATUSES,
    list_incidents,
    stream_investigation_chat,
    update_incident_status,
)
from app.tenancy import CurrentTenant

router = APIRouter(prefix="/api/investigation", tags=["investigation"])


@router.get("/statuses")
def investigation_statuses() -> list[str]:
    return INCIDENT_STATUSES


@router.get("/incidents", response_model=IncidentListResponse)
def get_incidents(
    tenant: CurrentTenant,
    status: IncidentStatus | None = Query(default=None),
    db: Session = Depends(get_db),
) -> IncidentListResponse:
    return list_incidents(db, tenant, status)


@router.patch("/incidents/{incident_id}", response_model=IncidentSummary)
def patch_incident_status(
    incident_id: str,
    payload: IncidentStatusUpdate,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> IncidentSummary:
    try:
        return update_incident_status(db, tenant, incident_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/chat/stream")
async def investigation_chat_stream(
    payload: InvestigationChatRequest,
    tenant: CurrentTenant,
):
    return StreamingResponse(
        stream_investigation_chat(payload, tenant),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
