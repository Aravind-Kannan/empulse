"""Persist per-tenant integration credentials and settings in PostgreSQL."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.operational import TenantIntegrationConfig
from app.schemas.integrations import (
    GitHubConfigRequest,
    JiraConfigRequest,
    NotionConfigRequest,
    SlackConfigRequest,
)

INTEGRATION_SOURCES = ("slack", "notion", "github", "jira")

_SECRET_FIELDS: dict[str, tuple[str, ...]] = {
    "slack": ("bot_token",),
    "notion": ("integration_token",),
    "github": ("personal_access_token",),
    "jira": ("api_token",),
}

_DEFAULT_CONFIG: dict[str, dict[str, Any]] = {
    "slack": {
        "workspace_url": "",
        "bot_token": "",
        "channel_ids": "",
        "validated": False,
        "previously_connected": False,
    },
    "notion": {
        "integration_token": "",
        "database_ids": "",
        "validated": False,
        "previously_connected": False,
    },
    "github": {
        "repository_url": "",
        "branch_target": "main",
        "personal_access_token": "",
        "oauth_connected": False,
        "path_component_map": {},
        "default_component_id": None,
        "validated": False,
        "previously_connected": False,
    },
    "jira": {
        "site_url": "",
        "project_keys": "",
        "api_token": "",
        "account_email": "",
        "component_field_map": {},
        "label_component_map": {},
        "project_component_map": {},
        "default_component_id": None,
        "high_priorities": ["Highest", "High", "Critical"],
        "validated": False,
        "previously_connected": False,
    },
}


def _merge_secrets(source: str, incoming: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    merged = {**existing, **incoming}
    for field in _SECRET_FIELDS.get(source, ()):
        if not str(incoming.get(field, "")).strip() and existing.get(field):
            merged[field] = existing[field]
    return merged


def _get_row(
    db: Session,
    tenant_id: uuid.UUID,
    source: str,
) -> TenantIntegrationConfig | None:
    return (
        db.query(TenantIntegrationConfig)
        .filter(
            TenantIntegrationConfig.tenant_id == tenant_id,
            TenantIntegrationConfig.source == source,
        )
        .one_or_none()
    )


def get_source_config(
    db: Session,
    tenant_id: uuid.UUID,
    source: str,
) -> dict[str, Any]:
    row = _get_row(db, tenant_id, source)
    if not row:
        return deepcopy(_DEFAULT_CONFIG[source])
    return {**deepcopy(_DEFAULT_CONFIG[source]), **(row.config or {})}


def get_all_configs(db: Session, tenant_id: uuid.UUID) -> dict[str, dict[str, Any]]:
    return {source: get_source_config(db, tenant_id, source) for source in INTEGRATION_SOURCES}


def upsert_source_config(
    db: Session,
    tenant_id: uuid.UUID,
    source: str,
    config: dict[str, Any],
    *,
    merge_secrets: bool = True,
) -> dict[str, Any]:
    if source not in INTEGRATION_SOURCES:
        raise ValueError(f"Unsupported integration source '{source}'.")

    existing = get_source_config(db, tenant_id, source)
    merged = (
        _merge_secrets(source, config, existing)
        if merge_secrets
        else {**existing, **config}
    )
    merged["previously_connected"] = merged.get("previously_connected", True)

    row = _get_row(db, tenant_id, source)
    now = datetime.now(UTC).replace(tzinfo=None)
    if row:
        row.config = merged
        row.updated_at = now
    else:
        db.add(
            TenantIntegrationConfig(
                tenant_id=tenant_id,
                source=source,
                config=merged,
                updated_at=now,
            )
        )
    db.commit()
    return merged


def delete_source_config(db: Session, tenant_id: uuid.UUID, source: str) -> None:
    if source not in INTEGRATION_SOURCES:
        raise ValueError(f"Unsupported integration source '{source}'.")

    row = _get_row(db, tenant_id, source)
    if row:
        db.delete(row)
        db.commit()


def save_github_config(
    db: Session,
    tenant_id: uuid.UUID,
    config: GitHubConfigRequest,
    *,
    validated: bool = True,
) -> None:
    payload = config.model_dump()
    payload["validated"] = validated
    upsert_source_config(db, tenant_id, "github", payload)


def save_jira_config(
    db: Session,
    tenant_id: uuid.UUID,
    config: JiraConfigRequest,
    *,
    validated: bool = True,
) -> None:
    payload = config.model_dump()
    payload["validated"] = validated
    upsert_source_config(db, tenant_id, "jira", payload)


def save_slack_config(
    db: Session,
    tenant_id: uuid.UUID,
    config: SlackConfigRequest,
    *,
    validated: bool = True,
) -> None:
    payload = config.model_dump()
    payload["validated"] = validated
    upsert_source_config(db, tenant_id, "slack", payload)


def save_notion_config(
    db: Session,
    tenant_id: uuid.UUID,
    config: NotionConfigRequest,
    *,
    validated: bool = True,
) -> None:
    payload = config.model_dump()
    payload["validated"] = validated
    upsert_source_config(db, tenant_id, "notion", payload)


def get_github_config(
    db: Session,
    tenant_id: uuid.UUID,
) -> GitHubConfigRequest | None:
    stored = get_source_config(db, tenant_id, "github")
    if not stored.get("repository_url", "").strip():
        return None
    if not stored.get("personal_access_token", "").strip() and not stored.get(
        "oauth_connected"
    ):
        return None
    return GitHubConfigRequest(
        repository_url=stored["repository_url"],
        branch_target=stored.get("branch_target", "main"),
        personal_access_token=stored.get("personal_access_token", ""),
        oauth_connected=bool(stored.get("oauth_connected")),
        path_component_map=stored.get("path_component_map") or {},
        default_component_id=stored.get("default_component_id"),
    )


def get_jira_config(
    db: Session,
    tenant_id: uuid.UUID,
) -> JiraConfigRequest | None:
    stored = get_source_config(db, tenant_id, "jira")
    if not stored.get("site_url", "").strip():
        return None
    if not stored.get("api_token", "").strip():
        return None
    return JiraConfigRequest(
        site_url=stored["site_url"],
        project_keys=stored.get("project_keys", ""),
        api_token=stored.get("api_token", ""),
        account_email=stored.get("account_email", ""),
        component_field_map=stored.get("component_field_map") or {},
        label_component_map=stored.get("label_component_map") or {},
        project_component_map=stored.get("project_component_map") or {},
        default_component_id=stored.get("default_component_id"),
        high_priorities=stored.get("high_priorities")
        or ["Highest", "High", "Critical"],
    )


def is_source_configured(db: Session, tenant_id: uuid.UUID, source: str) -> bool:
    if source == "github":
        return get_github_config(db, tenant_id) is not None
    if source == "jira":
        return get_jira_config(db, tenant_id) is not None
    stored = get_source_config(db, tenant_id, source)
    if source == "slack":
        return bool(stored.get("bot_token", "").strip() and stored.get("validated"))
    if source == "notion":
        return bool(
            stored.get("integration_token", "").strip() and stored.get("validated")
        )
    return False
