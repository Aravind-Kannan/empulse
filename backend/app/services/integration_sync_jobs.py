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
from app.services.background_runner import current_heavy_job_label, run_off_main_loop
from app.services.integration_sync import process_external_app_sync
from app.services.github_repo_sync import process_github_repo_sync
from app.services.sync_job_errors import SyncJobCancelled, format_sync_job_error

logger = logging.getLogger(__name__)

_RUNNING_TASKS: dict[uuid.UUID, asyncio.Task] = {}
VALID_SOURCES = frozenset({"github", "jira", "notion", "slack"})
_STALLED_RUNNING_ERROR = (
    "Sync interrupted — background task stopped unexpectedly. Please sync again."
)


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
        job_kind="source",
        status="queued",
        progress_message="Waiting to start…",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def create_github_repo_sync_job(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    repository_url: str,
) -> IntegrationSyncJob:
    normalized_url = repository_url.strip().rstrip("/")
    if not normalized_url:
        raise HTTPException(status_code=422, detail="repository_url is required.")

    job = IntegrationSyncJob(
        tenant_id=tenant_id,
        source="github_repo",
        job_kind="github_repo",
        repository_url=normalized_url,
        status="queued",
        progress_message="Waiting to start repository sync…",
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


def _sync_job_task_is_live(job_id: uuid.UUID) -> bool:
    task = _RUNNING_TASKS.get(job_id)
    return task is not None and not task.done()


def reconcile_stalled_sync_jobs(
    db: Session,
    tenant_id: uuid.UUID,
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """
    Fix active jobs whose asyncio dispatcher died (reload, cancellation race).

    Running jobs without a live task are marked failed — never completed.
    Queued jobs without a live task are reset and returned for re-dispatch.
    """
    stalled = (
        db.query(IntegrationSyncJob)
        .filter(
            IntegrationSyncJob.tenant_id == tenant_id,
            IntegrationSyncJob.status.in_(("queued", "running")),
        )
        .all()
    )
    redispatch: list[tuple[uuid.UUID, uuid.UUID]] = []
    for job in stalled:
        if _sync_job_task_is_live(job.id):
            continue
        if job.status == "running":
            _update_job(
                db,
                job.id,
                status="failed",
                error=_STALLED_RUNNING_ERROR,
                progress_message="Sync interrupted.",
            )
            logger.warning(
                "Reconciled stalled running integration sync job %s",
                job.id,
            )
            continue
        restart_message = (
            "Waiting to start repository sync…"
            if job.job_kind == "github_repo"
            else "Waiting to start…"
        )
        _update_job(
            db,
            job.id,
            progress_message=restart_message,
        )
        redispatch.append((job.id, tenant_id))
        logger.info(
            "Re-dispatching stalled queued integration sync job %s",
            job.id,
        )
    return redispatch


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


def _job_duration_seconds(job: IntegrationSyncJob) -> float | None:
    if not job.completed_at or not job.created_at:
        return None
    return max(0.0, (job.completed_at - job.created_at).total_seconds())


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
        progress_stats=job.progress_stats,
        error=format_sync_job_error(job.error) if job.error else None,
        result=result,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        duration_seconds=_job_duration_seconds(job),
        job_kind=job.job_kind or "source",
        repository_url=job.repository_url,
    )


def job_to_accepted_response(job: IntegrationSyncJob) -> IntegrationSyncJobAcceptedResponse:
    if job.job_kind == "github_repo" and job.repository_url:
        message = (
            f"Repository sync queued for {job.repository_url}. "
            "Track progress in the sync jobs panel."
        )
    else:
        message = (
            f"{job.source.title()} sync queued. "
            "Track progress in the sync jobs panel."
        )

    return IntegrationSyncJobAcceptedResponse(
        job_id=job.id,
        source=job.source,
        status="queued",
        poll_url=f"/api/integrations/sync/jobs/{job.id}",
        message=message,
        job_kind=job.job_kind or "source",
        repository_url=job.repository_url,
    )


def _update_job(
    db: Session,
    job_id: uuid.UUID,
    *,
    status: str | None = None,
    phase: str | None = None,
    progress_message: str | None = None,
    progress_stats: dict | None = None,
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
    if progress_stats is not None:
        job.progress_stats = progress_stats
    if error is not None:
        job.error = error
    if result is not None:
        job.result = result
    job.updated_at = _utcnow()
    if status in ("completed", "failed", "cancelled"):
        job.completed_at = _utcnow()
    db.commit()


def cancel_integration_sync_job(
    db: Session,
    job_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> IntegrationSyncJob:
    job = get_integration_sync_job_for_tenant(db, job_id, tenant_id)
    if job.status not in ("queued", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel sync job with status '{job.status}'.",
        )

    job.status = "cancelled"
    job.progress_message = "Sync cancelled."
    job.updated_at = _utcnow()
    job.completed_at = _utcnow()
    db.commit()
    db.refresh(job)

    task = _RUNNING_TASKS.get(job_id)
    if task and not task.done():
        task.cancel()

    return job


def _raise_if_job_cancelled(db: Session, job_id: uuid.UUID) -> None:
    job = db.query(IntegrationSyncJob).filter(IntegrationSyncJob.id == job_id).one_or_none()
    if job and job.status == "cancelled":
        raise SyncJobCancelled()


def make_progress_reporter(job_id: uuid.UUID):
    def report(
        phase: IntegrationSyncPhase,
        message: str,
        stats: dict | None = None,
    ) -> None:
        db = SessionLocal()
        try:
            _raise_if_job_cancelled(db, job_id)
            _update_job(
                db,
                job_id,
                status="running",
                phase=phase,
                progress_message=message,
                progress_stats=stats,
            )
        except Exception:
            logger.exception("Failed to update sync job %s progress", job_id)
        finally:
            db.close()

    return report


async def run_integration_sync_job(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    def _mark_waiting_behind_queue() -> None:
        db = SessionLocal()
        try:
            job = (
                db.query(IntegrationSyncJob)
                .filter(IntegrationSyncJob.id == job_id)
                .one_or_none()
            )
            if job and job.status == "queued":
                blocker = (
                    db.query(IntegrationSyncJob)
                    .filter(
                        IntegrationSyncJob.tenant_id == tenant_id,
                        IntegrationSyncJob.status == "running",
                        IntegrationSyncJob.id != job_id,
                    )
                    .order_by(IntegrationSyncJob.updated_at.desc())
                    .first()
                )
                holder = current_heavy_job_label()
                if blocker:
                    detail = f"{blocker.source} sync is running"
                elif holder:
                    detail = holder.replace("_execute_", "").replace("_job", "")
                else:
                    detail = "another background job"
                _update_job(
                    db,
                    job_id,
                    progress_message=(
                        f"Waiting for another sync job to finish ({detail})…"
                    ),
                )
        except Exception:
            logger.exception(
                "Failed to mark integration sync job %s as queue-waiting",
                job_id,
            )
        finally:
            db.close()

    try:
        await run_off_main_loop(
            _execute_integration_sync_job,
            job_id,
            tenant_id,
            on_waiting=_mark_waiting_behind_queue,
        )
    except asyncio.CancelledError:
        db = SessionLocal()
        try:
            job = (
                db.query(IntegrationSyncJob)
                .filter(IntegrationSyncJob.id == job_id)
                .one_or_none()
            )
            if job and job.status not in ("cancelled", "completed", "failed"):
                _update_job(
                    db,
                    job_id,
                    status="cancelled",
                    progress_message="Sync cancelled.",
                )
        except Exception:
            logger.exception(
                "Failed to mark integration sync job %s as cancelled after task cancel",
                job_id,
            )
        finally:
            db.close()
        raise
    finally:
        _RUNNING_TASKS.pop(job_id, None)


async def _execute_integration_sync_job(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        job = db.query(IntegrationSyncJob).filter(IntegrationSyncJob.id == job_id).one()
        if job.status == "cancelled":
            return
        source = job.source
        if job.job_kind == "github_repo":
            if not job.repository_url:
                raise ValueError("Repository sync job is missing repository_url.")
            _update_job(
                db,
                job_id,
                status="running",
                phase="fetching",
                progress_message=f"Walking {job.repository_url}…",
            )
            report = make_progress_reporter(job_id)

            def cancel_check() -> None:
                check_db = SessionLocal()
                try:
                    _raise_if_job_cancelled(check_db, job_id)
                finally:
                    check_db.close()

            result = await process_github_repo_sync(
                db,
                tenant_id,
                job.repository_url,
                progress=report,
                cancel_check=cancel_check,
            )
        else:
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
            status="running",
            phase="finalizing",
            progress_message="Refreshing ERA metrics…",
        )

        from app.services.era_snapshots import refresh_era_after_integration_sync

        try:
            await asyncio.to_thread(
                refresh_era_after_integration_sync,
                db,
                tenant_id,
            )
        except Exception:
            logger.exception(
                "ERA refresh failed after integration sync job %s", job_id
            )

        _update_job(
            db,
            job_id,
            status="running",
            phase="finalizing",
            progress_message="Syncing org chart to Cognee…",
        )

        from app.models.tenant import Tenant
        from app.services.component_management import finalize_org_after_integration_sync

        tenant_row = db.get(Tenant, tenant_id)
        if tenant_row:
            try:
                await finalize_org_after_integration_sync(db, tenant_row)
            except Exception:
                logger.exception(
                    "Org chart finalize failed after integration sync job %s", job_id
                )

        _update_job(
            db,
            job_id,
            status="completed",
            phase="finalizing",
            progress_message="Sync complete.",
            result=dict(result),
        )
    except SyncJobCancelled:
        logger.info("Integration sync job %s cancelled", job_id)
    except asyncio.CancelledError:
        logger.info("Integration sync job %s task cancelled", job_id)
        try:
            job = (
                db.query(IntegrationSyncJob)
                .filter(IntegrationSyncJob.id == job_id)
                .one_or_none()
            )
            if job and job.status not in ("cancelled", "completed", "failed"):
                _update_job(
                    db,
                    job_id,
                    status="cancelled",
                    progress_message="Sync cancelled.",
                )
        except Exception:
            logger.exception("Failed to mark integration sync job %s as cancelled", job_id)
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
    existing = _RUNNING_TASKS.get(job_id)
    if existing is not None and not existing.done():
        logger.debug(
            "Integration sync job %s already has a live dispatcher task",
            job_id,
        )
        return

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
