"""ERA alert and review settings persisted per tenant."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.operational import TenantIntegrationConfig

ERA_SETTINGS_SOURCE = "era"

DEFAULT_ERA_SETTINGS: dict[str, Any] = {
    "slack_webhook_url": "",
    "slack_webhook_enabled": False,
    "unmapped_threshold": 5,
    "review_cadence_days": 30,
}


def get_era_settings(db: Session, tenant_id: uuid.UUID) -> dict[str, Any]:
    row = (
        db.query(TenantIntegrationConfig)
        .filter(
            TenantIntegrationConfig.tenant_id == tenant_id,
            TenantIntegrationConfig.source == ERA_SETTINGS_SOURCE,
        )
        .one_or_none()
    )
    if not row:
        return deepcopy(DEFAULT_ERA_SETTINGS)
    return {**deepcopy(DEFAULT_ERA_SETTINGS), **(row.config or {})}


def save_era_settings(
    db: Session,
    tenant_id: uuid.UUID,
    patch: dict[str, Any],
) -> dict[str, Any]:
    current = get_era_settings(db, tenant_id)
    merged = {**current, **patch}
    row = (
        db.query(TenantIntegrationConfig)
        .filter(
            TenantIntegrationConfig.tenant_id == tenant_id,
            TenantIntegrationConfig.source == ERA_SETTINGS_SOURCE,
        )
        .one_or_none()
    )
    now = datetime.now(UTC)
    if row is None:
        row = TenantIntegrationConfig(
            tenant_id=tenant_id,
            source=ERA_SETTINGS_SOURCE,
            config=merged,
            updated_at=now,
        )
        db.add(row)
    else:
        row.config = merged
        row.updated_at = now
    db.commit()
    return merged
