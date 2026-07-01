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
    NotionConfigRequest,
    NotionValidateRequest,
    SlackConfigRequest,
    SlackValidateRequest,
    StoredGitHubConfig,
    StoredJiraConfig,
    StoredNotionConfig,
    StoredSlackConfig,
    TenantIntegrationsConfigResponse,
)
from app.services.employee_master_fetch import fetch_employee_master_data
from app.services.integration_config_store import (
    delete_source_config,
    get_all_configs,
    get_github_config,
    get_jira_config,
    is_source_configured,
    save_github_config,
    save_jira_config,
    save_notion_config,
    save_slack_config,
)
from app.services.integration_sync import (
    process_external_app_sync,
    process_global_sync,
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


def _bundle_response(db: Session, tenant_id) -> TenantIntegrationsConfigResponse:
    stored = get_all_configs(db, tenant_id)
    return TenantIntegrationsConfigResponse(
        slack=StoredSlackConfig(**stored["slack"]),
        notion=StoredNotionConfig(**stored["notion"]),
        github=StoredGitHubConfig(**stored["github"]),
        jira=StoredJiraConfig(**stored["jira"]),
    )


@router.get("/config", response_model=TenantIntegrationsConfigResponse)
def get_integration_config(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> TenantIntegrationsConfigResponse:
    return _bundle_response(db, tenant.id)


@router.post("/github/config", response_model=IntegrationConfigResponse)
def configure_github(
    payload: GitHubConfigRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> IntegrationConfigResponse:
    existing = get_github_config(db, tenant.id)
    if (
        not payload.personal_access_token.strip()
        and not payload.oauth_connected
        and not existing
    ):
        raise HTTPException(
            status_code=422,
            detail="GitHub requires a personal access token or OAuth authorization.",
        )
    save_github_config(db, tenant.id, payload)
    return IntegrationConfigResponse(
        source="github",
        configured=True,
        message="GitHub integration configuration saved.",
    )


@router.post("/jira/config", response_model=IntegrationConfigResponse)
def configure_jira(
    payload: JiraConfigRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> IntegrationConfigResponse:
    existing = get_jira_config(db, tenant.id)
    if not payload.api_token.strip() and not existing:
        raise HTTPException(status_code=422, detail="Jira API token is required.")
    save_jira_config(db, tenant.id, payload)
    return IntegrationConfigResponse(
        source="jira",
        configured=True,
        message="Jira integration configuration saved.",
    )


@router.post("/slack/config", response_model=IntegrationConfigResponse)
def configure_slack(
    payload: SlackConfigRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> IntegrationConfigResponse:
    if not payload.bot_token.strip():
        raise HTTPException(status_code=422, detail="Slack bot token is required.")
    save_slack_config(db, tenant.id, payload)
    return IntegrationConfigResponse(
        source="slack",
        configured=True,
        message="Slack integration configuration saved.",
    )


@router.post("/notion/config", response_model=IntegrationConfigResponse)
def configure_notion(
    payload: NotionConfigRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> IntegrationConfigResponse:
    if not payload.integration_token.strip():
        raise HTTPException(
            status_code=422,
            detail="Notion integration token is required.",
        )
    save_notion_config(db, tenant.id, payload)
    return IntegrationConfigResponse(
        source="notion",
        configured=True,
        message="Notion integration configuration saved.",
    )


@router.delete("/{source}/config", response_model=IntegrationConfigResponse)
def remove_integration_config(
    source: str,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> IntegrationConfigResponse:
    normalized = source.lower().strip()
    if normalized not in {"github", "jira", "slack", "notion"}:
        raise HTTPException(status_code=404, detail=f"Unknown integration '{source}'.")
    delete_source_config(db, tenant.id, normalized)
    return IntegrationConfigResponse(
        source=normalized,  # type: ignore[arg-type]
        configured=False,
        message=f"{normalized.title()} integration disconnected.",
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
    return {
        "github": is_source_configured(db, tenant.id, "github"),
        "jira": is_source_configured(db, tenant.id, "jira"),
        "slack": is_source_configured(db, tenant.id, "slack"),
        "notion": is_source_configured(db, tenant.id, "notion"),
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
            db=db,
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
    use_fixture: bool = Query(default=False),
) -> IntegrationSyncResponse:
    try:
        result = await process_external_app_sync(
            source,
            db,
            tenant.id,
            use_github_fixture=use_fixture,
            use_jira_fixture=use_fixture,
        )
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
    if get_github_config(db, tenant.id):
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
