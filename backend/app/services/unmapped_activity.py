"""Quarantine queue for integration events that cannot be attributed to an employee."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.operational import Employee, EmployeeIdentity, EraAlert, UnmappedActivity
from app.schemas.identity import UnmappedActivityRecord, UnmappedCountByProvider


def record_unmapped_activity(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    provider: str,
    provider_user_id: str,
    event_type: str,
    provider_label: str | None = None,
    payload: dict | None = None,
) -> UnmappedActivity:
    now = datetime.utcnow()
    existing = (
        db.query(UnmappedActivity)
        .filter(
            UnmappedActivity.tenant_id == tenant_id,
            UnmappedActivity.provider == provider,
            UnmappedActivity.provider_user_id == provider_user_id,
            UnmappedActivity.event_type == event_type,
        )
        .one_or_none()
    )
    if existing:
        existing.occurrence_count += 1
        existing.last_seen_at = now
        if provider_label:
            existing.provider_label = provider_label
        if payload:
            existing.payload_json = payload
        db.flush()
        return existing

    row = UnmappedActivity(
        tenant_id=tenant_id,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_label=provider_label,
        event_type=event_type,
        payload_json=payload or {},
        occurrence_count=1,
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(row)
    db.flush()
    return row


def list_unmapped_activities(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    provider: str | None = None,
    limit: int = 100,
) -> list[UnmappedActivityRecord]:
    query = db.query(UnmappedActivity).filter(UnmappedActivity.tenant_id == tenant_id)
    if provider:
        query = query.filter(UnmappedActivity.provider == provider)
    rows = (
        query.order_by(UnmappedActivity.last_seen_at.desc(), UnmappedActivity.id.desc())
        .limit(limit)
        .all()
    )
    return [
        UnmappedActivityRecord(
            id=row.id,
            provider=row.provider,
            provider_user_id=row.provider_user_id,
            provider_label=row.provider_label,
            event_type=row.event_type,
            occurrence_count=row.occurrence_count,
            first_seen_at=row.first_seen_at,
            last_seen_at=row.last_seen_at,
            payload_json=row.payload_json or {},
        )
        for row in rows
    ]


def get_unmapped_counts_by_provider(
    db: Session,
    tenant_id: uuid.UUID,
) -> list[UnmappedCountByProvider]:
    rows = (
        db.query(
            UnmappedActivity.provider,
            func.sum(UnmappedActivity.occurrence_count).label("count"),
        )
        .filter(UnmappedActivity.tenant_id == tenant_id)
        .group_by(UnmappedActivity.provider)
        .all()
    )
    return [
        UnmappedCountByProvider(provider=provider, count=int(count or 0))
        for provider, count in rows
    ]


def get_total_unmapped_count(db: Session, tenant_id: uuid.UUID) -> int:
    total = (
        db.query(func.coalesce(func.sum(UnmappedActivity.occurrence_count), 0))
        .filter(UnmappedActivity.tenant_id == tenant_id)
        .scalar()
    )
    return int(total or 0)


def get_configured_identity_providers(db: Session, tenant_id: uuid.UUID) -> list[str]:
    from app.services.identity_mapping import PROVIDERS
    from app.services.integration_config_store import is_source_configured

    return [
        provider
        for provider in PROVIDERS
        if is_source_configured(db, tenant_id, provider)
    ]


def is_employee_identity_grid_complete(db: Session, tenant_id: uuid.UUID) -> bool:
    """True when every employee has a saved mapping for each configured integration."""
    employees = (
        db.query(Employee.id)
        .filter(Employee.tenant_id == tenant_id)
        .all()
    )
    if not employees:
        return True

    configured = get_configured_identity_providers(db, tenant_id)
    if not configured:
        return False

    saved = {
        (row.employee_id, row.provider)
        for row in db.query(EmployeeIdentity)
        .filter(
            EmployeeIdentity.tenant_id == tenant_id,
            EmployeeIdentity.provider_username_or_id.isnot(None),
        )
        .all()
        if row.provider_username_or_id.strip()
    }

    for (employee_id,) in employees:
        for provider in configured:
            if (employee_id, provider) not in saved:
                return False
    return True


def reconcile_unmapped_activity(db: Session, tenant_id: uuid.UUID) -> int:
    """Remove quarantine rows that now resolve to an employee."""
    from app.services.identity_resolver import resolve_employee, should_attribute

    rows = (
        db.query(UnmappedActivity)
        .filter(UnmappedActivity.tenant_id == tenant_id)
        .all()
    )
    removed = 0
    for row in rows:
        result = resolve_employee(
            db,
            tenant_id,
            row.provider,
            row.provider_user_id,
        )
        if should_attribute(result):
            db.delete(row)
            removed += 1
    if removed:
        db.flush()
    return removed


def purge_unmapped_activity(db: Session, tenant_id: uuid.UUID) -> int:
    """Delete all quarantine rows for a tenant."""
    deleted = (
        db.query(UnmappedActivity)
        .filter(UnmappedActivity.tenant_id == tenant_id)
        .delete(synchronize_session=False)
    )
    if deleted:
        db.flush()
    return int(deleted or 0)


def dismiss_stale_identity_gap_alerts(db: Session, tenant_id: uuid.UUID) -> int:
    """Auto-acknowledge identity_gap alerts when quarantine is empty."""
    if get_total_unmapped_count(db, tenant_id) > 0:
        return 0

    now = datetime.now(UTC)
    rows = (
        db.query(EraAlert)
        .filter(
            EraAlert.tenant_id == tenant_id,
            EraAlert.rule_id == "identity_gap",
            EraAlert.acknowledged_at.is_(None),
        )
        .all()
    )
    for row in rows:
        row.acknowledged_at = now
        row.acknowledged_by = "system:identity_reconciled"
    if rows:
        db.flush()
    return len(rows)


def reconcile_and_prune_unmapped_activity(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    commit: bool = True,
) -> int:
    """
    Clear resolvable quarantine rows, purge stale backlog when the identity grid
    is fully saved, and dismiss obsolete identity_gap alerts.
    """
    removed = reconcile_unmapped_activity(db, tenant_id)
    configured = get_configured_identity_providers(db, tenant_id)
    if configured and is_employee_identity_grid_complete(db, tenant_id):
        removed += purge_unmapped_activity(db, tenant_id)
    dismiss_stale_identity_gap_alerts(db, tenant_id)
    if commit:
        db.commit()
    else:
        db.flush()
    return removed
