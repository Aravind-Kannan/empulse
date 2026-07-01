"""Jira integration: credential storage, validation, and Cognee ingestion pipeline."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cognee
import requests
from cognee.tasks.storage import add_data_points
from sqlalchemy.orm import Session

from app.models.jira_integration import JiraIntegration
from app.schemas.integrations import JiraConfigRequest
from app.schemas.jira import (
    JiraConnectRequest,
    JiraDebugStage,
    JiraDebugState,
    JiraIntegrationResponse,
    parse_project_keys,
)
from app.services.credential_crypto import encrypt_secret
from app.services.integration_feeds import MOCK_JIRA_ISSUES
from app.services.integration_telemetry import apply_jira_telemetry
from app.services.tenant_cognee import tenant_add_and_cognify
from app.tenancy import tenant_dataset_name

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
DEBUG_STATE_PATH = BACKEND_ROOT / "data" / "jira_debug_state.json"

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
    """Live Atlassian API check via /rest/api/3/myself."""
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

    encrypted = encrypt_secret(payload.api_token)
    integration = get_jira_integration(db, tenant_id)

    if integration:
        integration.jira_domain = payload.jira_domain
        integration.auth_email = str(payload.auth_email)
        integration.encrypted_api_token = encrypted
        integration.project_keys = payload.project_keys
        integration.status = "syncing"
        integration.updated_at = _utc_now()
    else:
        integration = JiraIntegration(
            tenant_id=tenant_id,
            jira_domain=payload.jira_domain,
            auth_email=str(payload.auth_email),
            encrypted_api_token=encrypted,
            project_keys=payload.project_keys,
            status="syncing",
        )
        db.add(integration)

    db.commit()
    db.refresh(integration)
    return integration


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


def _filter_issues(project_keys: str) -> list[dict[str, Any]]:
    keys = parse_project_keys(project_keys)
    if not keys:
        return list(MOCK_JIRA_ISSUES)
    key_set = set(keys)
    return [issue for issue in MOCK_JIRA_ISSUES if issue["project_key"] in key_set]


def _sanitize_issues(issues: list[dict[str, Any]]) -> list[str]:
    documents: list[str] = []
    for issue in issues:
        assignee = issue.get("assignee_employee_id") or "Unassigned"
        documents.append(
            f"{issue['ticket_id']} [{issue['issue_type']}] "
            f"Priority: {issue['priority']} | Status: {issue['status']} | "
            f"Project: {issue['project_key']} | Assignee: {assignee}\n"
            f"{issue.get('description', '')}"
        )
    return documents


async def sync_jira_to_cognee(tenant_id: uuid.UUID, db: Session) -> dict[str, Any]:
    """
    Fetch (mock) Jira issues, append to Cognee, cognify, and update debug diagnostics.
    """
    integration = get_jira_integration(db, tenant_id)
    if not integration:
        raise ValueError("Jira integration is not configured for this tenant.")

    state = _init_debug_state(tenant_id)
    _write_debug_state(state)

    try:
        # Stage 1: Fetching Issues
        t0 = time.perf_counter()
        started = _iso_now()
        _update_stage(state, "Fetching Issues", status="running", started_at=started)
        await asyncio.sleep(0.15)

        issues = _filter_issues(integration.project_keys)
        scope = (
            f"projects {integration.project_keys}"
            if integration.project_keys.strip()
            else "all projects"
        )
        fetch_ms = int((time.perf_counter() - t0) * 1000)
        state.issues_fetched = len(issues)
        _update_stage(
            state,
            "Fetching Issues",
            status="completed",
            completed_at=_iso_now(),
            duration_ms=fetch_ms,
            detail=f"Fetched {len(issues)} issues from {scope}.",
        )

        # Stage 2: Sanitizing Metadata
        t1 = time.perf_counter()
        _update_stage(
            state,
            "Sanitizing Metadata",
            status="running",
            started_at=_iso_now(),
        )
        await asyncio.sleep(0.1)
        documents = _sanitize_issues(issues)
        config = _integration_to_config(integration)
        from app.services.integration_sync import _load_org_context, analyze_jira_payload

        employee_nodes, component_nodes = _load_org_context(db, tenant_id)
        narrative, data_points, edge_count = analyze_jira_payload(
            config,
            employee_nodes,
            component_nodes,
            issues=issues,
        )
        sanitize_ms = int((time.perf_counter() - t1) * 1000)
        _update_stage(
            state,
            "Sanitizing Metadata",
            status="completed",
            completed_at=_iso_now(),
            duration_ms=sanitize_ms,
            detail=f"Sanitized {len(documents)} issue documents.",
        )

        # Stage 3: Vector Append
        t2 = time.perf_counter()
        _update_stage(state, "Vector Append", status="running", started_at=_iso_now())
        payload = "\n\n---\n\n".join(documents)
        dataset = tenant_dataset_name(tenant_id)
        await cognee.add(payload, dataset_name=dataset)
        if data_points:
            await add_data_points(data_points)
        append_ms = int((time.perf_counter() - t2) * 1000)
        state.documents_appended = len(documents)
        _update_stage(
            state,
            "Vector Append",
            status="completed",
            completed_at=_iso_now(),
            duration_ms=append_ms,
            detail=f"Appended {len(documents)} documents to dataset {dataset}.",
        )

        # Stage 4: Graph Cognify
        t3 = time.perf_counter()
        _update_stage(state, "Graph Cognify", status="running", started_at=_iso_now())
        custom_prompt = (
            "Extract Jira issue metadata including ticket IDs, issue types, priorities, "
            "status indicators, infrastructure references, and link assignees and blocked "
            "components via assignedTo and blocksComponent relationships."
        )
        await tenant_add_and_cognify(
            narrative,
            tenant_id,
            custom_prompt=custom_prompt,
        )
        cognify_ms = int((time.perf_counter() - t3) * 1000)
        _update_stage(
            state,
            "Graph Cognify",
            status="completed",
            completed_at=_iso_now(),
            duration_ms=cognify_ms,
            detail="Cognee graph cognify completed.",
        )

        apply_jira_telemetry(db, tenant_id)

        integration.status = "connected"
        integration.last_synced_at = _utc_now()
        integration.issues_synced_count = len(issues)
        integration.updated_at = _utc_now()
        db.commit()

        state.status = "completed"
        state.updated_at = _iso_now()
        _write_debug_state(state)

        return {
            "source": "jira",
            "cognee_dataset": dataset,
            "documents_ingested": len(documents),
            "graph_nodes_created": len(data_points),
            "graph_edges_created": edge_count,
            "narrative_preview": narrative[:280],
            "issues_synced": len(issues),
        }
    except Exception as exc:
        state.status = "failed"
        state.last_error = str(exc)
        state.updated_at = _iso_now()
        for stage in state.stages:
            if stage.status == "running":
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
