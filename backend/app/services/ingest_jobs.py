"""Async Cognee ingest jobs (PostgreSQL persist sync, graph build in background)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.ingest_job import IngestJob
from app.models.tenant import Tenant
from app.schemas.ingest_job import IngestJobStatusResponse
from app.schemas.org import OrgChartIngestRequest, OrgChartIngestResponse
from app.services.background_runner import run_off_main_loop
from app.services.cognee_ingest import ingest_org_chart_to_cognee
from app.services.org_chart_read import load_org_chart

logger = logging.getLogger(__name__)

_RUNNING_TASKS: dict[uuid.UUID, asyncio.Task] = {}


def validate_org_chart_payload(payload: OrgChartIngestRequest) -> None:
    employee_ids = {employee.id for employee in payload.employees}
    if len(employee_ids) != len(payload.employees):
        raise HTTPException(status_code=422, detail="Duplicate employee ids detected.")

    for employee in payload.employees:
        if employee.manager_id and employee.manager_id not in employee_ids:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Unknown manager_id '{employee.manager_id}' "
                    f"for employee '{employee.id}'."
                ),
            )

    component_ids = {component.id for component in payload.components}
    for assignment in payload.assignments:
        if assignment.employee_id not in employee_ids:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown employee_id '{assignment.employee_id}' in assignment.",
            )
        if assignment.component_id not in component_ids:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown component_id '{assignment.component_id}' in assignment.",
            )


def create_org_chart_ingest_job(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    payload: OrgChartIngestRequest,
) -> IngestJob:
    job = IngestJob(
        tenant_id=tenant_id,
        job_type="org_chart",
        status="queued",
        company=payload.company,
        employees_persisted=len(payload.employees),
        components_persisted=len(payload.components),
        assignments_persisted=len(payload.assignments),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_ingest_job_for_tenant(
    db: Session,
    job_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> IngestJob:
    job = (
        db.query(IngestJob)
        .filter(IngestJob.id == job_id, IngestJob.tenant_id == tenant_id)
        .one_or_none()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Ingest job not found.")
    return job


def job_to_status_response(job: IngestJob) -> IngestJobStatusResponse:
    result = None
    if job.result:
        result = OrgChartIngestResponse.model_validate(job.result)

    return IngestJobStatusResponse(
        job_id=job.id,
        status=job.status,  # type: ignore[arg-type]
        job_type=job.job_type,
        company=job.company,
        employees_persisted=job.employees_persisted,
        components_persisted=job.components_persisted,
        assignments_persisted=job.assignments_persisted,
        error=job.error,
        result=result,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _update_job_status(
    db: Session,
    job_id: uuid.UUID,
    *,
    status: str,
    error: str | None = None,
    result: dict | None = None,
) -> None:
    job = db.query(IngestJob).filter(IngestJob.id == job_id).one()
    job.status = status
    job.error = error
    job.result = result
    job.updated_at = _utcnow()
    if status in ("completed", "failed"):
        job.completed_at = _utcnow()
    db.commit()


async def run_org_chart_ingest_job(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    try:
        await run_off_main_loop(_execute_org_chart_ingest_job, job_id, tenant_id)
    finally:
        _RUNNING_TASKS.pop(job_id, None)


async def _execute_org_chart_ingest_job(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        _update_job_status(db, job_id, status="running")
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).one()
        org = load_org_chart(db, tenant)
        cognee_result = await ingest_org_chart_to_cognee(org, tenant_id=tenant_id)
        result = OrgChartIngestResponse(
            company=org.company,
            employees_persisted=len(org.employees),
            components_persisted=len(org.components),
            assignments_persisted=len(org.assignments),
            cognee_dataset=str(cognee_result["cognee_dataset"]),
            graph_nodes_created=int(cognee_result["graph_nodes_created"]),
            graph_edges_created=int(cognee_result["graph_edges_created"]),
        )
        _update_job_status(
            db,
            job_id,
            status="completed",
            result=result.model_dump(),
        )
    except Exception as exc:
        logger.exception("Ingest job %s failed", job_id)
        try:
            _update_job_status(db, job_id, status="failed", error=str(exc))
        except Exception:
            logger.exception("Failed to mark ingest job %s as failed", job_id)
    finally:
        db.close()


def schedule_org_chart_ingest_job(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    loop = asyncio.get_running_loop()
    task = loop.create_task(run_org_chart_ingest_job(job_id, tenant_id))
    _RUNNING_TASKS[job_id] = task

    def _log_task_failure(done: asyncio.Task) -> None:
        try:
            done.result()
        except Exception:
            logger.exception("Unhandled failure in ingest job task %s", job_id)

    task.add_done_callback(_log_task_failure)
