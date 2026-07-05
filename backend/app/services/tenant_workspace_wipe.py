"""Destructive wipe of tenant operational Postgres data (org roster, analytics snapshots)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.ingest_job import IngestJob
from app.models.integration_sync_job import IntegrationSyncJob
from app.models.integration_sync_record import IntegrationSyncRecord
from app.models.operational import (
    Assignment,
    Component,
    DoaFileSnapshot,
    Employee,
    EmployeeIdentity,
    EraAlert,
    EraDepartureOrphanBaseline,
    EraEvidenceMitigation,
    EraRiskSnapshot,
    EraTeamHealthSnapshot,
    EraTeamReview,
    FileRiskSnapshot,
    GitHubOwnershipSnapshot,
    IncidentRecord,
    NotionDocSnapshot,
    RoleHistory,
    UnmappedActivity,
)

logger = logging.getLogger(__name__)


def _delete_for_tenant(db: Session, model: type, tenant_id: uuid.UUID) -> int:
    return (
        db.query(model)
        .filter(model.tenant_id == tenant_id)
        .delete(synchronize_session=False)
    )


def wipe_tenant_operational_data(
    db: Session,
    tenant_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Remove all workspace operational data for a tenant.

    Preserves integration credentials, tenant membership, and user accounts.
    Clears employees, components, assignments, identity mappings, incidents,
    ERA/KRA snapshots, sync job history, and ingest job history.
    """
    counts: dict[str, int] = {}

    db.query(Employee).filter(Employee.tenant_id == tenant_id).update(
        {Employee.manager_id: None},
        synchronize_session=False,
    )

    dependent_models: list[tuple[type, str]] = [
        (Assignment, "assignments"),
        (EmployeeIdentity, "employee_identities"),
        (RoleHistory, "role_history"),
        (GitHubOwnershipSnapshot, "github_ownership_snapshots"),
        (DoaFileSnapshot, "doa_file_snapshots"),
        (FileRiskSnapshot, "file_risk_snapshots"),
        (NotionDocSnapshot, "notion_doc_snapshots"),
        (EraEvidenceMitigation, "era_evidence_mitigations"),
        (EraRiskSnapshot, "era_risk_snapshots"),
        (EraAlert, "era_alerts"),
        (EraDepartureOrphanBaseline, "era_departure_orphan_baselines"),
        (EraTeamHealthSnapshot, "era_team_health_snapshots"),
        (EraTeamReview, "era_team_reviews"),
        (UnmappedActivity, "unmapped_activities"),
        (IncidentRecord, "incidents"),
        (IntegrationSyncRecord, "sync_ledger_rows"),
        (IntegrationSyncJob, "sync_jobs"),
        (IngestJob, "ingest_jobs"),
    ]
    for model, key in dependent_models:
        counts[key] = _delete_for_tenant(db, model, tenant_id)

    counts["employees"] = _delete_for_tenant(db, Employee, tenant_id)
    counts["components"] = _delete_for_tenant(db, Component, tenant_id)

    db.commit()

    _invalidate_tenant_caches(tenant_id)

    total_rows = sum(counts.values())
    logger.warning(
        "Wiped %d operational row(s) for tenant %s: %s",
        total_rows,
        tenant_id,
        counts,
    )
    return {
        "tenant_id": str(tenant_id),
        "counts": counts,
        "total_rows_removed": total_rows,
        "message": (
            f"Removed {counts['employees']} employee(s), "
            f"{counts['components']} component(s), and {total_rows} total "
            "operational row(s). Integration credentials were preserved."
        ),
    }


def _invalidate_tenant_caches(tenant_id: uuid.UUID) -> None:
    from app.services.incident_feed import invalidate_incident_feed_cache
    from app.services.kra_metrics import invalidate_kra_summary_cache
    from app.services.provider_members import invalidate_provider_members_cache
    from app.services.slack_client import invalidate_slack_threads_cache

    invalidate_kra_summary_cache(tenant_id)
    invalidate_incident_feed_cache(tenant_id)
    invalidate_provider_members_cache(tenant_id)
    invalidate_slack_threads_cache()
