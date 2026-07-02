"""Seed default tenant and optional demo incident records."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.operational import IncidentRecord
from app.models.tenant import DEFAULT_TENANT_ID, Tenant
from app.tenancy import ensure_default_tenant

_DEMO_INCIDENTS = [
    {
        "id": "inc-001",
        "title": "Payment Gateway timeout spike",
        "status": "Investigating",
        "system_scope": "Payment Gateway",
        "jira_id": "PROJ-992",
        "updated_at": datetime(2026, 6, 30, 10, 15, tzinfo=UTC),
    },
    {
        "id": "inc-002",
        "title": "Auth Service elevated 503 rate",
        "status": "Open",
        "system_scope": "Auth Service",
        "jira_id": "PROJ-887",
        "updated_at": datetime(2026, 6, 30, 9, 40, tzinfo=UTC),
    },
    {
        "id": "inc-003",
        "title": "Notification delivery backlog",
        "status": "Waiting for Input",
        "system_scope": "Notification Hub",
        "jira_id": "PROJ-774",
        "updated_at": datetime(2026, 6, 29, 18, 20, tzinfo=UTC),
    },
    {
        "id": "inc-004",
        "title": "Checkout partial outage",
        "status": "Resolved",
        "system_scope": "Payment Gateway",
        "jira_id": "PROJ-651",
        "updated_at": datetime(2026, 6, 28, 14, 5, tzinfo=UTC),
    },
    {
        "id": "inc-005",
        "title": "SSO redirect loop regression",
        "status": "Closed",
        "system_scope": "Auth Service",
        "jira_id": "PROJ-540",
        "updated_at": datetime(2026, 6, 25, 11, 30, tzinfo=UTC),
    },
]


def seed_default_incidents(db: Session, tenant_id: uuid.UUID) -> None:
    flag = os.getenv("EMPULSE_SEED_DEMO_INCIDENTS", "").strip().lower()
    if flag not in {"1", "true", "yes"}:
        return

    existing = (
        db.query(IncidentRecord)
        .filter(IncidentRecord.tenant_id == tenant_id)
        .count()
    )
    if existing:
        return

    for item in _DEMO_INCIDENTS:
        db.add(
            IncidentRecord(
                id=item["id"],
                tenant_id=tenant_id,
                title=item["title"],
                status=item["status"],
                system_scope=item["system_scope"],
                jira_id=item["jira_id"],
                updated_at=item["updated_at"],
            )
        )
    db.commit()


def bootstrap_tenancy(db: Session) -> Tenant:
    tenant = ensure_default_tenant(db)
    seed_default_incidents(db, tenant.id)
    return tenant
