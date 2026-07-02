from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
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
    write_incident_memory_to_cognee,
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
async def patch_incident_status(
    incident_id: str,
    payload: IncidentStatusUpdate,
    background_tasks: BackgroundTasks,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> IncidentSummary:
    from app.models.operational import IncidentRecord

    record = (
        db.query(IncidentRecord)
        .filter(
            IncidentRecord.id == incident_id,
            IncidentRecord.tenant_id == tenant.id,
        )
        .one_or_none()
    )
    if not record:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    try:
        summary = update_incident_status(db, tenant, incident_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    background_tasks.add_task(
        write_incident_memory_to_cognee,
        tenant.id,
        incident_id,
        payload.status,
        resolution_note=payload.resolution_note,
        title=record.title,
        system_scope=record.system_scope,
        jira_id=record.jira_id,
    )
    return summary


@router.post("/chat/stream")
async def investigation_chat_stream(
    payload: InvestigationChatRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
):
    return StreamingResponse(
        stream_investigation_chat(payload, tenant, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
