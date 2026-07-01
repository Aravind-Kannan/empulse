"""Quarantine queue for integration events that cannot be attributed to an employee."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.operational import UnmappedActivity
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
