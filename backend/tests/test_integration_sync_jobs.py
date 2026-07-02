"""Tests for background integration sync jobs."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from app.services.integration_sync_jobs import (
    _execute_integration_sync_job,
    create_integration_sync_job,
    job_to_status_response,
    list_integration_sync_jobs,
)


def test_create_integration_sync_job(db, tenant):
    job = create_integration_sync_job(db, tenant_id=tenant.id, source="github")
    assert job.source == "github"
    assert job.status == "queued"

    response = job_to_status_response(job)
    assert response.source == "github"
    assert response.status == "queued"

    jobs = list_integration_sync_jobs(db, tenant.id, active_only=True)
    assert any(item.id == job.id for item in jobs)


def test_completed_sync_job_refreshes_era(db, tenant):
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
    ) as refresh_mock:
        asyncio.run(_execute_integration_sync_job(job.id, tenant.id))

    refresh_mock.assert_called_once()
    assert refresh_mock.call_args[0][1] == tenant.id

    db.refresh(job)
    assert job.status == "completed"
