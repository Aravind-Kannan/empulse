"""Jira integration: credential storage, validation, and Cognee ingestion pipeline."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.models.jira_integration import JiraIntegration
from app.schemas.integrations import JiraConfigRequest
from app.schemas.jira import (
    JiraConnectRequest,
    JiraDebugStage,
    JiraDebugState,
    JiraIntegrationResponse,
    JiraProjectInfo,
    parse_project_keys,
)
from app.services.credential_crypto import encrypt_secret
from app.services.integration_sync import process_external_app_sync
from app.services.tenant_cognee import tenant_dataset_name

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
DEBUG_STATE_PATH = BACKEND_ROOT / "data" / "jira_debug_state.json"
logger = logging.getLogger(__name__)

JIRA_STAGES = (
    "Fetching Issues",
    "Sanitizing Metadata",
    "Vector Append",
    "Graph Cognify",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _integration_to_config(integration: JiraIntegration) -> JiraConfigRequest:
    return JiraConfigRequest(
        site_url=integration.jira_domain,
        project_keys=integration.project_keys,
        api_token="configured",
    )


def integration_to_response(integration: JiraIntegration) -> JiraIntegrationResponse:
    keys = parse_project_keys(integration.project_keys)
    return JiraIntegrationResponse(
        id=integration.id,
        tenant_id=integration.tenant_id,
        jira_domain=integration.jira_domain,
        auth_email=integration.auth_email,
        project_keys=integration.project_keys,
        project_scope="specific" if keys else "all",
        status=integration.status,
        last_synced_at=integration.last_synced_at,
        issues_synced_count=integration.issues_synced_count,
    )


def get_jira_integration(db: Session, tenant_id: uuid.UUID) -> JiraIntegration | None:
    return (
        db.query(JiraIntegration)
        .filter(JiraIntegration.tenant_id == tenant_id)
        .one_or_none()
    )


def upsert_jira_integration_from_config(
    db: Session,
    tenant_id: uuid.UUID,
    config: JiraConfigRequest,
    *,
    status: str = "connected",
) -> JiraIntegration:
    """Persist encrypted Jira credentials on the legacy integration row."""
    token = config.api_token.strip()
    site_url = config.site_url.strip()
    account_email = config.account_email.strip()
    if not token or not site_url or not account_email:
        raise ValueError("Jira site URL, account email, and API token are required.")

    encrypted = encrypt_secret(token)
    integration = get_jira_integration(db, tenant_id)
    if integration:
        integration.jira_domain = site_url
        integration.auth_email = account_email
        integration.encrypted_api_token = encrypted
        integration.project_keys = config.project_keys
        integration.status = status
        integration.updated_at = _utc_now()
    else:
        integration = JiraIntegration(
            tenant_id=tenant_id,
            jira_domain=site_url,
            auth_email=account_email,
            encrypted_api_token=encrypted,
            project_keys=config.project_keys,
            status=status,
        )
        db.add(integration)

    db.commit()
    db.refresh(integration)
    return integration


def get_jira_config_for_tenant(
    db: Session,
    tenant_id: uuid.UUID,
) -> JiraConfigRequest | None:
    integration = get_jira_integration(db, tenant_id)
    if not integration:
        return None
    return _integration_to_config(integration)


def validate_jira_credentials(
    jira_domain: str,
    auth_email: str,
    api_token: str,
) -> tuple[str, str | None]:
    try:
        response = requests.get(
            f"{jira_domain}/rest/api/3/myself",
            auth=(auth_email, api_token),
            headers={"Accept": "application/json"},
            timeout=15,
        )
    except requests.RequestException as exc:
        raise ValueError(f"Could not reach Jira at {jira_domain}: {exc}") from exc

    if response.status_code == 401:
        raise ValueError(
            "Jira rejected these credentials (401). "
            "Confirm your account email and API token at id.atlassian.com."
        )
    if response.status_code == 403:
        raise ValueError(
            "Jira returned 403 — the token is valid but lacks required permissions."
        )
    if response.status_code >= 400:
        detail = response.text[:200] if response.text else response.reason
        raise ValueError(f"Jira API error ({response.status_code}): {detail}")

    payload = response.json()
    display = payload.get("displayName") or payload.get("emailAddress") or auth_email
    return f"Jira credentials valid — authenticated as {display}.", display


def list_accessible_jira_projects(
    jira_domain: str,
    auth_email: str,
    api_token: str,
) -> list[JiraProjectInfo]:
    projects: list[JiraProjectInfo] = []
    start_at = 0

    while start_at < 500:
        try:
            response = requests.get(
                f"{jira_domain}/rest/api/3/project/search",
                auth=(auth_email, api_token),
                headers={"Accept": "application/json"},
                params={
                    "startAt": start_at,
                    "maxResults": 50,
                    "orderBy": "name",
                },
                timeout=20,
            )
        except requests.RequestException as exc:
            raise ValueError(f"Could not reach Jira at {jira_domain}: {exc}") from exc

        if response.status_code == 401:
            raise ValueError(
                "Jira rejected these credentials (401). "
                "Confirm your account email and API token at id.atlassian.com."
            )
        if response.status_code >= 400:
            detail = response.text[:200] if response.text else response.reason
            raise ValueError(f"Jira API error ({response.status_code}): {detail}")

        payload = response.json()
        values = payload.get("values") or []
        for row in values:
            key = (row.get("key") or "").strip()
            if not key:
                continue
            projects.append(
                JiraProjectInfo(
                    key=key,
                    name=(row.get("name") or key).strip(),
                    project_type=(row.get("projectTypeKey") or None),
                )
            )

        if start_at + len(values) >= int(payload.get("total") or 0):
            break
        if not values:
            break
        start_at += len(values)

    return projects


def connect_jira_integration(
    db: Session,
    tenant_id: uuid.UUID,
    payload: JiraConnectRequest,
    *,
    skip_live_validation: bool = False,
) -> JiraIntegration:
    if not skip_live_validation:
        validate_jira_credentials(
            payload.jira_domain,
            str(payload.auth_email),
            payload.api_token,
        )

    config = JiraConfigRequest(
        site_url=payload.jira_domain,
        project_keys=payload.project_keys,
        api_token=payload.api_token,
        account_email=str(payload.auth_email),
    )
    integration = upsert_jira_integration_from_config(
        db,
        tenant_id,
        config,
        status="syncing",
    )

    from app.services.integration_config_store import save_jira_config

    save_jira_config(
        db,
        tenant_id,
        config,
        validated=True,
    )

    return integration


def delete_jira_integration(db: Session, tenant_id: uuid.UUID) -> None:
    integration = get_jira_integration(db, tenant_id)
    if integration:
        db.delete(integration)
        db.commit()


def _read_debug_state() -> dict[str, Any]:
    if not DEBUG_STATE_PATH.exists():
        return {}
    try:
        return json.loads(DEBUG_STATE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_debug_state(state: JiraDebugState) -> None:
    DEBUG_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = _read_debug_state()
    raw[str(state.tenant_id)] = state.model_dump()
    DEBUG_STATE_PATH.write_text(json.dumps(raw, indent=2))


def get_jira_debug_state(tenant_id: uuid.UUID) -> JiraDebugState | None:
    raw = _read_debug_state()
    entry = raw.get(str(tenant_id))
    if not entry:
        return None
    return JiraDebugState.model_validate(entry)


def _init_debug_state(tenant_id: uuid.UUID) -> JiraDebugState:
    return JiraDebugState(
        tenant_id=str(tenant_id),
        status="syncing",
        stages=[
            JiraDebugStage(name=stage, status="pending") for stage in JIRA_STAGES
        ],
        updated_at=_iso_now(),
    )


def _update_stage(
    state: JiraDebugState,
    stage_name: str,
    *,
    status: str,
    started_at: str | None = None,
    completed_at: str | None = None,
    duration_ms: int | None = None,
    detail: str | None = None,
) -> None:
    for stage in state.stages:
        if stage.name == stage_name:
            stage.status = status  # type: ignore[assignment]
            if started_at:
                stage.started_at = started_at
            if completed_at:
                stage.completed_at = completed_at
            if duration_ms is not None:
                stage.duration_ms = duration_ms
            if detail is not None:
                stage.detail = detail
            break
    state.updated_at = _iso_now()
    _write_debug_state(state)


async def sync_jira_to_cognee(tenant_id: uuid.UUID, db: Session) -> dict[str, Any]:
    """Fetch live Jira issues and sync them into the tenant Cognee dataset."""
    from app.services.integration_config_store import get_jira_config

    config = get_jira_config(db, tenant_id)
    if not config:
        raise ValueError("Jira integration is not configured for this tenant.")

    integration = get_jira_integration(db, tenant_id)
    if not integration:
        integration = upsert_jira_integration_from_config(
            db,
            tenant_id,
            config,
            status="syncing",
        )
    else:
        integration.status = "syncing"
        integration.updated_at = _utc_now()
        db.commit()

    state = _init_debug_state(tenant_id)
    _write_debug_state(state)
    started = _iso_now()

    try:
        _update_stage(state, "Fetching Issues", status="running", started_at=started)

        result = await process_external_app_sync("jira", db, tenant_id)

        issues_count = int(result.get("graph_nodes_created", 0))
        state.issues_fetched = issues_count
        state.documents_appended = int(result.get("documents_ingested", 0))
        now = _iso_now()

        _update_stage(
            state,
            "Fetching Issues",
            status="completed",
            completed_at=now,
            detail=f"Fetched {issues_count} Jira issues.",
        )
        _update_stage(
            state,
            "Sanitizing Metadata",
            status="completed",
            completed_at=now,
            detail="Mapped assignees and components.",
        )
        _update_stage(
            state,
            "Vector Append",
            status="completed",
            completed_at=now,
            detail=f"Appended documents to {result.get('cognee_dataset', '')}.",
        )
        _update_stage(
            state,
            "Graph Cognify",
            status="completed",
            completed_at=now,
            detail="Structured Jira graph nodes written to Cognee.",
        )

        integration.status = "connected"
        integration.last_synced_at = _utc_now()
        integration.issues_synced_count = issues_count
        integration.updated_at = _utc_now()
        db.commit()

        state.status = "completed"
        state.updated_at = _iso_now()
        _write_debug_state(state)

        return {
            "source": "jira",
            "cognee_dataset": result.get("cognee_dataset", tenant_dataset_name(tenant_id)),
            "documents_ingested": state.documents_appended,
            "graph_nodes_created": issues_count,
            "graph_edges_created": int(result.get("graph_edges_created", 0)),
            "narrative_preview": str(result.get("narrative_preview", "")),
            "issues_synced": issues_count,
        }
    except Exception as exc:
        logger.exception("Jira Cognee sync failed for tenant %s", tenant_id)
        state.status = "failed"
        state.last_error = str(exc)
        state.updated_at = _iso_now()
        for stage in state.stages:
            if stage.status in {"running", "pending"}:
                stage.status = "failed"
                stage.detail = str(exc)
        _write_debug_state(state)

        integration.status = "error"
        integration.updated_at = _utc_now()
        db.commit()
        raise


def disconnect_jira_integration(db: Session, tenant_id: uuid.UUID) -> None:
    integration = get_jira_integration(db, tenant_id)
    if integration:
        integration.status = "disconnected"
        integration.updated_at = _utc_now()
        db.commit()
