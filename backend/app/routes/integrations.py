from fastapi import APIRouter, Depends, HTTPException, Query
import logging
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.integrations import (
    GitHubBranchesRequest,
    GitHubBranchesResponse,
    GitHubConfigRequest,
    GitHubDiscoverRequest,
    GitHubDiscoverResponse,
    GitHubValidateRequest,
    GlobalSyncResponse,
    IntegrationConfigResponse,
    IntegrationSyncResponse,
    IntegrationValidateResponse,
    JiraConfigRequest,
    MemberRosterSyncResponse,
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
from app.services.integration_config_store import (
    delete_source_config,
    get_all_configs,
    get_github_config,
    get_jira_config,
    get_notion_config,
    get_slack_config,
    get_source_config,
    is_source_configured,
    save_github_config,
    save_jira_config,
    save_notion_config,
    save_slack_config,
)
from app.services.github_client import (
    GitHubClientError,
    list_accessible_repositories,
    list_repository_branches,
)
from app.services.integration_validate import (
    validate_github_credentials,
    validate_jira_credentials,
    validate_notion_token,
    validate_slack_bot_token,
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
from app.services.member_roster_sync import sync_member_roster
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
    stored = get_source_config(db, tenant.id, "github")
    token = payload.personal_access_token.strip() or (
        stored.get("personal_access_token") or ""
    ).strip()

    repository_urls = [
        url.strip() for url in payload.repository_urls if url.strip()
    ]
    if not repository_urls:
        legacy_url = payload.repository_url.strip() or (
            stored.get("repository_url") or ""
        ).strip()
        if legacy_url:
            repository_urls = [legacy_url]

    branch_targets = [
        branch.strip() for branch in payload.branch_targets if branch.strip()
    ]
    branch_target = payload.branch_target.strip() or (
        stored.get("branch_target") or "main"
    )
    if not branch_targets and branch_target:
        branch_targets = [branch_target]

    if not repository_urls:
        raise HTTPException(
            status_code=422,
            detail="Select at least one GitHub repository to sync.",
        )
    if not token:
        raise HTTPException(
            status_code=422,
            detail="GitHub personal access token is required.",
        )

    try:
        validation_message = validate_github_credentials(
            token,
            repository_urls=repository_urls,
            branch_targets=branch_targets,
            sync_all_branches=payload.sync_all_branches,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    save_github_config(
        db,
        tenant.id,
        GitHubConfigRequest(
            repository_url=repository_urls[0],
            repository_urls=repository_urls,
            branch_target=branch_targets[0] if branch_targets else branch_target,
            branch_targets=branch_targets,
            sync_all_branches=payload.sync_all_branches,
            personal_access_token=token,
            oauth_connected=False,
            path_component_map=payload.path_component_map
            or stored.get("path_component_map")
            or {},
            default_component_id=payload.default_component_id
            or stored.get("default_component_id"),
        ),
    )
    return IntegrationConfigResponse(
        source="github",
        configured=True,
        message=validation_message,
    )


@router.post("/jira/config", response_model=IntegrationConfigResponse)
def configure_jira(
    payload: JiraConfigRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> IntegrationConfigResponse:
    stored = get_source_config(db, tenant.id, "jira")
    token = payload.api_token.strip() or (stored.get("api_token") or "").strip()
    account_email = payload.account_email.strip() or (stored.get("account_email") or "").strip()
    project_keys = payload.project_keys.strip() or (stored.get("project_keys") or "").strip()
    site_url = payload.site_url.strip() or (stored.get("site_url") or "").strip()

    if not token:
        raise HTTPException(status_code=422, detail="Jira API token is required.")
    if not site_url:
        raise HTTPException(status_code=422, detail="Jira site URL is required.")
    if not project_keys:
        raise HTTPException(
            status_code=422,
            detail="Jira project keys are required (comma-separated, e.g. SCRUM).",
        )

    try:
        resolved_email, validation_message = validate_jira_credentials(
            site_url,
            token,
            account_email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    save_jira_config(
        db,
        tenant.id,
        JiraConfigRequest(
            site_url=site_url,
            project_keys=project_keys,
            api_token=token,
            account_email=resolved_email,
            component_field_map=payload.component_field_map or stored.get("component_field_map") or {},
            label_component_map=payload.label_component_map or stored.get("label_component_map") or {},
            project_component_map=payload.project_component_map or stored.get("project_component_map") or {},
            default_component_id=payload.default_component_id or stored.get("default_component_id"),
            high_priorities=payload.high_priorities or stored.get("high_priorities") or ["Highest", "High", "Critical"],
        ),
    )
    return IntegrationConfigResponse(
        source="jira",
        configured=True,
        message=validation_message,
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


@router.post("/github/validate", response_model=IntegrationValidateResponse)
def validate_github(payload: GitHubValidateRequest) -> IntegrationValidateResponse:
    repository_urls = [url.strip() for url in payload.repository_urls if url.strip()]
    if not repository_urls and payload.repository_url.strip():
        repository_urls = [payload.repository_url.strip()]
    branch_targets = [branch.strip() for branch in payload.branch_targets if branch.strip()]
    if not branch_targets and payload.branch_target.strip():
        branch_targets = [payload.branch_target.strip()]

    try:
        message = validate_github_credentials(
            payload.personal_access_token,
            repository_urls=repository_urls,
            branch_targets=branch_targets,
            sync_all_branches=payload.sync_all_branches,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IntegrationValidateResponse(
        source="github",
        valid=True,
        message=message,
    )


@router.post("/github/discover", response_model=GitHubDiscoverResponse)
def discover_github_repositories(
    payload: GitHubDiscoverRequest,
) -> GitHubDiscoverResponse:
    try:
        repositories = list_accessible_repositories(payload.personal_access_token)
    except GitHubClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not repositories:
        return GitHubDiscoverResponse(
            repositories=[],
            message=(
                "No repositories were returned for this token. "
                "Confirm the PAT has repository read access."
            ),
        )

    return GitHubDiscoverResponse(
        repositories=repositories,
        message=f"Found {len(repositories)} accessible repositor{'y' if len(repositories) == 1 else 'ies'}.",
    )


@router.post("/github/branches", response_model=GitHubBranchesResponse)
def list_github_branches(payload: GitHubBranchesRequest) -> GitHubBranchesResponse:
    try:
        default_branch, branches = list_repository_branches(
            payload.personal_access_token,
            payload.repository_url,
        )
    except GitHubClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GitHubBranchesResponse(
        repository_url=payload.repository_url.strip(),
        default_branch=default_branch,
        branches=branches,
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
            use_notion_fixture=use_fixture,
            use_slack_fixture=use_fixture,
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
    if get_notion_config(db, tenant.id):
        sources.append("notion")
    if get_slack_config(db, tenant.id):
        sources.append("slack")

    if not sources:
        raise HTTPException(
            status_code=400,
            detail="No configured integrations are available for sync.",
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
