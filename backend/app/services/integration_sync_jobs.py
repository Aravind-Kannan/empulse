"""Background Cognee integration sync jobs with per-source progress tracking."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.integration_sync_job import IntegrationSyncJob
from app.schemas.integration_sync_job import (
    IntegrationSyncJobAcceptedResponse,
    IntegrationSyncJobStatusResponse,
    IntegrationSyncPhase,
)
from app.schemas.integrations import IntegrationSyncResponse
from app.services.background_runner import run_off_main_loop
from app.services.integration_sync import process_external_app_sync
from app.services.sync_job_errors import format_sync_job_error

logger = logging.getLogger(__name__)

_RUNNING_TASKS: dict[uuid.UUID, asyncio.Task] = {}
VALID_SOURCES = frozenset({"github", "jira", "notion", "slack"})


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def create_integration_sync_job(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    source: str,
) -> IntegrationSyncJob:
    normalized = source.lower().strip()
    if normalized not in VALID_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported integration source '{source}'.",
        )

    job = IntegrationSyncJob(
        tenant_id=tenant_id,
        source=normalized,
        status="queued",
        progress_message="Waiting to start…",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_integration_sync_job_for_tenant(
    db: Session,
    job_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> IntegrationSyncJob:
    job = (
        db.query(IntegrationSyncJob)
        .filter(IntegrationSyncJob.id == job_id, IntegrationSyncJob.tenant_id == tenant_id)
        .one_or_none()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Integration sync job not found.")
    return job


def list_integration_sync_jobs(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    limit: int = 20,
    active_only: bool = False,
) -> list[IntegrationSyncJob]:
    query = (
        db.query(IntegrationSyncJob)
        .filter(IntegrationSyncJob.tenant_id == tenant_id)
        .order_by(IntegrationSyncJob.created_at.desc())
    )
    if active_only:
        query = query.filter(IntegrationSyncJob.status.in_(("queued", "running")))
    return query.limit(max(1, min(limit, 100))).all()


def job_to_status_response(job: IntegrationSyncJob) -> IntegrationSyncJobStatusResponse:
    result = None
    if job.result:
        result = IntegrationSyncResponse.model_validate(job.result)

    return IntegrationSyncJobStatusResponse(
        job_id=job.id,
        source=job.source,
        status=job.status,  # type: ignore[arg-type]
        phase=job.phase,  # type: ignore[arg-type]
        progress_message=job.progress_message,
        error=format_sync_job_error(job.error) if job.error else None,
        result=result,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


def job_to_accepted_response(job: IntegrationSyncJob) -> IntegrationSyncJobAcceptedResponse:
    return IntegrationSyncJobAcceptedResponse(
        job_id=job.id,
        source=job.source,
        status="queued",
        poll_url=f"/api/integrations/sync/jobs/{job.id}",
        message=(
            f"{job.source.title()} sync queued. "
            "Track progress in the sync jobs panel."
        ),
    )


def _update_job(
    db: Session,
    job_id: uuid.UUID,
    *,
    status: str | None = None,
    phase: str | None = None,
    progress_message: str | None = None,
    error: str | None = None,
    result: dict | None = None,
) -> None:
    job = db.query(IntegrationSyncJob).filter(IntegrationSyncJob.id == job_id).one()
    if status is not None:
        job.status = status
    if phase is not None:
        job.phase = phase
    if progress_message is not None:
        job.progress_message = progress_message
    if error is not None:
        job.error = error
    if result is not None:
        job.result = result
    job.updated_at = _utcnow()
    if status in ("completed", "failed"):
        job.completed_at = _utcnow()
    db.commit()


def make_progress_reporter(job_id: uuid.UUID):
    def report(phase: IntegrationSyncPhase, message: str) -> None:
        db = SessionLocal()
        try:
            _update_job(
                db,
                job_id,
                status="running",
                phase=phase,
                progress_message=message,
            )
        except Exception:
            logger.exception("Failed to update sync job %s progress", job_id)
        finally:
            db.close()

    return report


async def run_integration_sync_job(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    try:
        await run_off_main_loop(_execute_integration_sync_job, job_id, tenant_id)
    finally:
        _RUNNING_TASKS.pop(job_id, None)


async def _execute_integration_sync_job(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        job = db.query(IntegrationSyncJob).filter(IntegrationSyncJob.id == job_id).one()
        source = job.source
        _update_job(
            db,
            job_id,
            status="running",
            phase="fetching",
            progress_message=f"Fetching {source} data…",
        )

        report = make_progress_reporter(job_id)
        result = await process_external_app_sync(
            source,
            db,
            tenant_id,
            progress=report,
        )

        _update_job(
            db,
            job_id,
            status="completed",
            phase="finalizing",
            progress_message="Sync complete.",
            result=dict(result),
        )

        from app.services.era_snapshots import refresh_era_after_integration_sync

        try:
            refresh_era_after_integration_sync(db, tenant_id)
        except Exception:
            logger.exception(
                "ERA refresh failed after integration sync job %s", job_id
            )
    except Exception as exc:
        logger.exception("Integration sync job %s failed", job_id)
        try:
            _update_job(
                db,
                job_id,
                status="failed",
                error=format_sync_job_error(exc),
                progress_message="Sync failed.",
            )
        except Exception:
            logger.exception("Failed to mark integration sync job %s as failed", job_id)
    finally:
        db.close()


def schedule_integration_sync_job(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    loop = asyncio.get_running_loop()
    task = loop.create_task(run_integration_sync_job(job_id, tenant_id))
    _RUNNING_TASKS[job_id] = task

    def _log_task_failure(done: asyncio.Task) -> None:
        try:
            done.result()
        except Exception:
            logger.exception("Unhandled failure in integration sync job task %s", job_id)

    task.add_done_callback(_log_task_failure)


def recover_orphaned_sync_jobs() -> int:
    """
    Mark queued/running jobs as failed after a process restart.

    Background asyncio tasks do not survive uvicorn reload; without this,
    the UI polls forever and integration cards stay on Syncing.
    """
    db = SessionLocal()
    try:
        orphans = (
            db.query(IntegrationSyncJob)
            .filter(IntegrationSyncJob.status.in_(("queued", "running")))
            .all()
        )
        if not orphans:
            return 0
        now = _utcnow()
        for job in orphans:
            job.status = "failed"
            job.error = "Sync interrupted by server restart. Please sync again."
            job.progress_message = "Sync interrupted."
            job.updated_at = now
            job.completed_at = now
        db.commit()
        logger.info("Recovered %d orphaned integration sync job(s)", len(orphans))
        return len(orphans)
    finally:
        db.close()
