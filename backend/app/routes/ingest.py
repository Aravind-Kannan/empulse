import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.ingest_job import IngestJobAcceptedResponse, IngestJobStatusResponse
from app.schemas.org import OrgChartIngestRequest
from app.services.cognee_ingest import persist_org_chart
from app.services.ingest_jobs import (
    create_org_chart_ingest_job,
    get_ingest_job_for_tenant,
    job_to_status_response,
    schedule_org_chart_ingest_job,
    validate_org_chart_payload,
)
from app.services.org_chart_read import load_org_chart
from app.tenancy import CurrentTenant

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.get("/org-chart", response_model=OrgChartIngestRequest)
def get_org_chart(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> OrgChartIngestRequest:
    return load_org_chart(db, tenant)


@router.post(
    "/org-chart",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IngestJobAcceptedResponse,
)
async def ingest_org_chart(
    payload: OrgChartIngestRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> IngestJobAcceptedResponse:
    validate_org_chart_payload(payload)

    try:
        persist_org_chart(db, payload, tenant.id)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail=f"Failed to persist org chart to PostgreSQL: {exc}",
        ) from exc

    job = create_org_chart_ingest_job(db, tenant_id=tenant.id, payload=payload)
    schedule_org_chart_ingest_job(job.id, tenant.id)

    return IngestJobAcceptedResponse(
        job_id=job.id,
        status="queued",
        poll_url=f"/api/ingest/jobs/{job.id}",
        message=(
            "Org chart saved to PostgreSQL. Cognee graph build started in the background."
        ),
    )


@router.get("/jobs/{job_id}", response_model=IngestJobStatusResponse)
def get_ingest_job_status(
    job_id: uuid.UUID,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> IngestJobStatusResponse:
    job = get_ingest_job_for_tenant(db, job_id, tenant.id)
    return job_to_status_response(job)
