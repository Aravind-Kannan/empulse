"""Tests for background integration sync jobs."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from app.services.background_runner import run_heavy_job
from app.services.integration_sync_jobs import (
    _execute_integration_sync_job,
    _update_job,
    create_integration_sync_job,
    job_to_status_response,
    list_integration_sync_jobs,
    reconcile_stalled_sync_jobs,
    schedule_integration_sync_job,
)


async def _slow_job() -> None:
    await asyncio.sleep(1.0)


async def _noop_job() -> None:
    return None


def test_run_heavy_job_marks_waiting_callback_when_queue_busy():
    calls: list[str] = []

    async def runner() -> None:
        first = asyncio.create_task(run_heavy_job(_slow_job))
        second = asyncio.create_task(
            run_heavy_job(_noop_job, on_waiting=lambda: calls.append("waiting"))
        )
        await asyncio.sleep(0.4)
        assert calls == ["waiting"]
        await second
        await first

    asyncio.run(runner())


def test_run_heavy_job_skips_waiting_callback_when_queue_free():
    calls: list[str] = []

    async def runner() -> None:
        await run_heavy_job(_noop_job, on_waiting=lambda: calls.append("waiting"))
        await asyncio.sleep(0.4)

    asyncio.run(runner())
    assert calls == []


def test_reconcile_stalled_sync_jobs_redispatches_queued_without_task(db, tenant):
    job = create_integration_sync_job(db, tenant_id=tenant.id, source="notion")
    _update_job(
        db,
        job.id,
        progress_message="Waiting for another sync job to finish…",
    )

    redispatch = reconcile_stalled_sync_jobs(db, tenant.id)

    assert redispatch == [(job.id, tenant.id)]
    db.refresh(job)
    assert job.status == "queued"
    assert job.progress_message == "Waiting to start…"


def test_reconcile_stalled_sync_jobs_fails_running_without_task(db, tenant):
    job = create_integration_sync_job(db, tenant_id=tenant.id, source="slack")
    _update_job(db, job.id, status="running", phase="fetching")

    redispatch = reconcile_stalled_sync_jobs(db, tenant.id)

    assert redispatch == []
    db.refresh(job)
    assert job.status == "failed"
    assert job.progress_message == "Sync interrupted."


def test_create_integration_sync_job(db, tenant):
    job = create_integration_sync_job(db, tenant_id=tenant.id, source="github")
    assert job.source == "github"
    assert job.status == "queued"

    response = job_to_status_response(job)
    assert response.source == "github"
    assert response.status == "queued"

    jobs = list_integration_sync_jobs(db, tenant.id, active_only=True)
    assert any(item.id == job.id for item in jobs)


def test_job_to_status_response_includes_duration_seconds(db, tenant):
    from datetime import timedelta

    from app.services.integration_sync_jobs import _utcnow

    job = create_integration_sync_job(db, tenant_id=tenant.id, source="github")
    started = _utcnow()
    job.created_at = started
    completed = started + timedelta(seconds=125)
    _update_job(db, job.id, status="completed", progress_message="Done.")
    job = db.query(type(job)).filter_by(id=job.id).one()
    job.created_at = started
    job.completed_at = completed
    db.commit()
    db.refresh(job)

    response = job_to_status_response(job)
    assert response.duration_seconds == 125.0
    job = create_integration_sync_job(db, tenant_id=tenant.id, source="github")
    fake_result = {
        "source": "github",
        "graph_nodes_created": 1,
        "graph_edges_created": 0,
        "items_skipped": 0,
    }

    with patch(
        "app.services.integration_sync_jobs.SessionLocal",
        return_value=db,
    ), patch.object(db, "close"), patch(
        "app.services.integration_sync_jobs.process_external_app_sync",
        new_callable=AsyncMock,
        return_value=fake_result,
    ), patch(
        "app.services.era_snapshots.refresh_era_after_integration_sync",
    ) as refresh_mock, patch(
        "app.services.component_management.finalize_org_after_integration_sync",
        new_callable=AsyncMock,
        return_value={},
    ):
        asyncio.run(_execute_integration_sync_job(job.id, tenant.id))

    refresh_mock.assert_called_once()
    assert refresh_mock.call_args[0][1] == tenant.id

    db.refresh(job)
    assert job.status == "completed"
