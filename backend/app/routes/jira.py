from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.schemas.jira import (
    JiraConnectRequest,
    JiraDebugState,
    JiraIntegrationResponse,
    JiraProjectsRequest,
    JiraProjectsResponse,
    JiraValidateRequest,
    JiraValidateResponse,
)
from app.services.background_runner import run_off_main_loop
from app.services.jira_service import (
    connect_jira_integration,
    get_jira_debug_state,
    get_jira_integration,
    integration_to_response,
    list_accessible_jira_projects,
    sync_jira_to_cognee,
    validate_jira_credentials,
)
from app.tenancy import CurrentTenant

router = APIRouter(prefix="/api/integrations/jira", tags=["jira"])


async def _run_jira_sync_background(tenant_id: uuid.UUID) -> None:
    await run_off_main_loop(_execute_jira_sync, tenant_id)


async def _execute_jira_sync(tenant_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        await sync_jira_to_cognee(tenant_id, db)
    except Exception:
        pass
    finally:
        db.close()


@router.get("", response_model=JiraIntegrationResponse | None)
def get_jira_status(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> JiraIntegrationResponse | None:
    integration = get_jira_integration(db, tenant.id)
    if not integration:
        return None
    return integration_to_response(integration)


@router.get("/debug-state", response_model=JiraDebugState | None)
def get_jira_sync_debug_state(
    tenant: CurrentTenant,
) -> JiraDebugState | None:
    return get_jira_debug_state(tenant.id)


@router.post("/validate", response_model=JiraValidateResponse)
def validate_jira(payload: JiraValidateRequest) -> JiraValidateResponse:
    try:
        message, display_name = validate_jira_credentials(
            payload.jira_domain,
            str(payload.auth_email),
            payload.api_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JiraValidateResponse(
        valid=True,
        message=message,
        account_display_name=display_name,
    )


@router.post("/projects", response_model=JiraProjectsResponse)
def discover_jira_projects(payload: JiraProjectsRequest) -> JiraProjectsResponse:
    try:
        projects = list_accessible_jira_projects(
            payload.jira_domain,
            str(payload.auth_email),
            payload.api_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not projects:
        return JiraProjectsResponse(
            projects=[],
            message="No Jira projects found for this account.",
        )

    return JiraProjectsResponse(
        projects=projects,
        message=f"Found {len(projects)} accessible project{'s' if len(projects) != 1 else ''}.",
    )


@router.post("/connect", response_model=JiraIntegrationResponse)
def connect_jira(
    payload: JiraConnectRequest,
    background_tasks: BackgroundTasks,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> JiraIntegrationResponse:
    try:
        integration = connect_jira_integration(db, tenant.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    background_tasks.add_task(_run_jira_sync_background, tenant.id)
    return integration_to_response(integration)
