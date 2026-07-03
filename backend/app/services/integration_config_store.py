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
        "incident_channel_ids": "",
        "on_call_channel_ids": "",
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
        "repository_urls": [],
        "branch_target": "main",
        "branch_targets": [],
        "sync_all_branches": False,
        "ingest_file_content": False,
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
    configs = {
        source: get_source_config(db, tenant_id, source) for source in INTEGRATION_SOURCES
    }
    configs["jira"] = _merge_jira_integration_config(db, tenant_id, configs["jira"])
    return configs


def _merge_jira_integration_config(
    db: Session,
    tenant_id: uuid.UUID,
    stored: dict[str, Any],
) -> dict[str, Any]:
    from app.services.credential_crypto import decrypt_secret
    from app.services.jira_service import get_jira_integration

    integration = get_jira_integration(db, tenant_id)
    if not integration:
        return stored

    token = (stored.get("api_token") or "").strip()
    if not token:
        try:
            token = decrypt_secret(integration.encrypted_api_token)
        except Exception:
            token = ""

    merged = {
        **stored,
        "site_url": integration.jira_domain or stored.get("site_url", ""),
        "account_email": integration.auth_email or stored.get("account_email", ""),
        "project_keys": integration.project_keys or stored.get("project_keys", ""),
        "api_token": token,
        "validated": bool(token) or bool(stored.get("validated")),
        "previously_connected": True,
    }
    if token:
        merged["validated"] = True
    return merged


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

    if source == "jira":
        from app.services.jira_service import delete_jira_integration

        delete_jira_integration(db, tenant_id)

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
    repository_urls = [
        url.strip()
        for url in (stored.get("repository_urls") or [])
        if str(url).strip()
    ]
    repository_url = (stored.get("repository_url") or "").strip()
    if not repository_urls and repository_url:
        repository_urls = [repository_url]
    if not repository_urls:
        return None
    if not stored.get("personal_access_token", "").strip() and not stored.get(
        "oauth_connected"
    ):
        return None
    branch_targets = [
        branch.strip()
        for branch in (stored.get("branch_targets") or [])
        if str(branch).strip()
    ]
    return GitHubConfigRequest(
        repository_url=repository_urls[0],
        repository_urls=repository_urls,
        branch_target=stored.get("branch_target", "main"),
        branch_targets=branch_targets,
        sync_all_branches=bool(stored.get("sync_all_branches")),
        ingest_file_content=bool(stored.get("ingest_file_content")),
        personal_access_token=stored.get("personal_access_token", ""),
        oauth_connected=bool(stored.get("oauth_connected")),
        path_component_map=stored.get("path_component_map") or {},
        default_component_id=stored.get("default_component_id"),
    )


def get_jira_config(
    db: Session,
    tenant_id: uuid.UUID,
) -> JiraConfigRequest | None:
    stored = _merge_jira_integration_config(
        db,
        tenant_id,
        get_source_config(db, tenant_id, "jira"),
    )
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


def get_notion_config(
    db: Session,
    tenant_id: uuid.UUID,
) -> NotionConfigRequest | None:
    stored = get_source_config(db, tenant_id, "notion")
    if not stored.get("integration_token", "").strip():
        return None
    return NotionConfigRequest(
        integration_token=stored["integration_token"],
        database_ids=stored.get("database_ids", ""),
        validated=bool(stored.get("validated")),
        previously_connected=bool(stored.get("previously_connected")),
    )


def get_slack_config(
    db: Session,
    tenant_id: uuid.UUID,
) -> SlackConfigRequest | None:
    stored = get_source_config(db, tenant_id, "slack")
    if not stored.get("bot_token", "").strip():
        return None
    return SlackConfigRequest(
        workspace_url=stored.get("workspace_url", ""),
        bot_token=stored["bot_token"],
        channel_ids=stored.get("channel_ids", ""),
        incident_channel_ids=stored.get("incident_channel_ids", ""),
        on_call_channel_ids=stored.get("on_call_channel_ids", ""),
        validated=bool(stored.get("validated")),
        previously_connected=bool(stored.get("previously_connected")),
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


def record_integration_sync(
    db: Session,
    tenant_id: uuid.UUID,
    source: str,
) -> None:
    """Persist last sync time so ERA survives backend restarts."""
    upsert_source_config(
        db,
        tenant_id,
        source,
        {"last_synced_at": datetime.now(UTC).isoformat()},
        merge_secrets=True,
    )


def get_integration_last_synced(
    db: Session,
    tenant_id: uuid.UUID,
    source: str,
) -> str | None:
    stored = get_source_config(db, tenant_id, source)
    value = stored.get("last_synced_at")
    return str(value) if value else None


def save_telemetry_cache(
    db: Session,
    tenant_id: uuid.UUID,
    source: str,
    cache: dict[str, Any],
) -> None:
    upsert_source_config(
        db,
        tenant_id,
        source,
        {"telemetry_cache": cache},
        merge_secrets=True,
    )


def get_telemetry_cache(
    db: Session,
    tenant_id: uuid.UUID,
    source: str,
) -> dict[str, Any] | None:
    stored = get_source_config(db, tenant_id, source)
    cache = stored.get("telemetry_cache")
    return cache if isinstance(cache, dict) else None
