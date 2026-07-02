"""Tests for background integration sync jobs."""

from __future__ import annotations

from app.services.integration_sync_jobs import (
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
