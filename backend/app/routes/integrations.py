from fastapi import APIRouter, Depends, HTTPException, Query
import logging
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.integrations import (
    GitHubConfigRequest,
    GlobalSyncResponse,
    IntegrationConfigResponse,
    IntegrationSyncResponse,
    IntegrationValidateResponse,
    JiraConfigRequest,
    MemberRosterSyncResponse,
    NotionValidateRequest,
    SlackValidateRequest,
)
from app.services.member_roster_sync import sync_member_roster
from app.services.integration_sync import (
    get_github_config,
    get_jira_config,
    process_external_app_sync,
    process_global_sync,
    save_github_config,
    save_jira_config,
)
from app.schemas.employee_master import (
    EmployeeMasterDataResponse,
    FetchUsersRequest,
)
from app.services.employee_master_fetch import (
    enrich_jira_credentials_from_db,
    fetch_employee_master_data,
)
from app.services.integration_validate import (
    validate_notion_token,
    validate_slack_bot_token,
)
from app.tenancy import CurrentTenant

router = APIRouter(prefix="/api/integrations", tags=["integrations"])
logger = logging.getLogger(__name__)


@router.post("/github/config", response_model=IntegrationConfigResponse)
def configure_github(payload: GitHubConfigRequest) -> IntegrationConfigResponse:
    if not payload.personal_access_token and not payload.oauth_connected:
        raise HTTPException(
            status_code=422,
            detail="GitHub requires a personal access token or OAuth authorization.",
        )
    save_github_config(payload)
    return IntegrationConfigResponse(
        source="github",
        configured=True,
        message="GitHub integration configuration saved.",
    )


@router.post("/jira/config", response_model=IntegrationConfigResponse)
def configure_jira(payload: JiraConfigRequest) -> IntegrationConfigResponse:
    if not payload.api_token.strip():
        raise HTTPException(status_code=422, detail="Jira API token is required.")
    save_jira_config(payload)
    return IntegrationConfigResponse(
        source="jira",
        configured=True,
        message="Jira integration configuration saved.",
    )


@router.post("/notion/validate", response_model=IntegrationValidateResponse)
def validate_notion(payload: NotionValidateRequest) -> IntegrationValidateResponse:
    try:
        message = validate_notion_token(payload.integration_token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IntegrationValidateResponse(
        source="notion",
        valid=True,
        message=message,
    )


@router.post("/slack/validate", response_model=IntegrationValidateResponse)
def validate_slack(payload: SlackValidateRequest) -> IntegrationValidateResponse:
    try:
        message = validate_slack_bot_token(payload.bot_token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IntegrationValidateResponse(
        source="slack",
        valid=True,
        message=message,
    )


@router.get("/status")
def integration_status(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    from app.services.jira_service import get_jira_integration

    jira = get_jira_integration(db, tenant.id)
    return {
        "github": get_github_config() is not None,
        "jira": jira is not None and jira.status in ("connected", "syncing"),
    }


@router.get("/telemetry")
def integration_telemetry() -> dict[str, object]:
    from app.services.integration_telemetry import get_telemetry_snapshot

    return get_telemetry_snapshot()


@router.get("/fetch-users", response_model=EmployeeMasterDataResponse)
def fetch_users_get(
    sources: list[str] = Query(default=[]),
    company: str = Query(default="Acme Company"),
) -> EmployeeMasterDataResponse:
    if not sources:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one source query param (slack, jira, notion, github).",
        )
    try:
        return fetch_employee_master_data(sources, company=company, flat_hierarchy=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/fetch-users", response_model=EmployeeMasterDataResponse)
def fetch_users_post(
    payload: FetchUsersRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> EmployeeMasterDataResponse:
    if not payload.sources:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one source (slack, jira, notion, github).",
        )
    credentials = enrich_jira_credentials_from_db(payload, db, tenant.id)
    try:
        return fetch_employee_master_data(
            credentials.sources,
            company=credentials.company,
            credentials=credentials,
            flat_hierarchy=credentials.flat_hierarchy,
            tenant_id=tenant.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sync-members", response_model=MemberRosterSyncResponse)
async def sync_members(
    payload: FetchUsersRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> MemberRosterSyncResponse:
    member_sources = [
        source
        for source in payload.sources
        if source in ("slack", "jira", "notion", "github")
    ]
    if not member_sources:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one member source: slack, jira, notion, or github.",
        )
    try:
        result = await sync_member_roster(
            db,
            tenant,
            payload.model_copy(update={"sources": member_sources}),
        )
    except ValueError as exc:
        logger.warning("sync-members rejected: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Member roster sync failed: {exc}",
        ) from exc

    return MemberRosterSyncResponse(**result)


@router.post("/sync/{source}", response_model=IntegrationSyncResponse)
async def sync_integration(
    source: str,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> IntegrationSyncResponse:
    try:
        result = await process_external_app_sync(source, db, tenant.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Cognee sync failed for {source}: {exc}",
        ) from exc

    return IntegrationSyncResponse(**result)


@router.post("/sync", response_model=GlobalSyncResponse)
async def sync_all_configured(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> GlobalSyncResponse:
    sources: list[str] = []
    if get_github_config():
        sources.append("github")
    if get_jira_config(db, tenant.id):
        sources.append("jira")

    if not sources:
        raise HTTPException(
            status_code=400,
            detail="No GitHub or Jira integrations are configured for sync.",
        )

    try:
        results = await process_global_sync(db, tenant.id, sources)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Global Cognee sync failed: {exc}",
        ) from exc

    sync_results = [IntegrationSyncResponse(**result) for result in results]
    return GlobalSyncResponse(
        results=sync_results,
        total_nodes_created=sum(item.graph_nodes_created for item in sync_results),
        total_edges_created=sum(item.graph_edges_created for item in sync_results),
    )
