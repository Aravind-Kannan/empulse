from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.integrations import (
    GitHubConfigRequest,
    GlobalSyncResponse,
    IntegrationConfigResponse,
    IntegrationSyncResponse,
    JiraConfigRequest,
)
from app.services.integration_sync import (
    get_github_config,
    get_jira_config,
    process_external_app_sync,
    process_global_sync,
    save_github_config,
    save_jira_config,
)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


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


@router.get("/status")
def integration_status() -> dict[str, bool]:
    return {
        "github": get_github_config() is not None,
        "jira": get_jira_config() is not None,
    }


@router.get("/telemetry")
def integration_telemetry() -> dict[str, object]:
    from app.services.integration_telemetry import get_telemetry_snapshot

    return get_telemetry_snapshot()


@router.post("/sync/{source}", response_model=IntegrationSyncResponse)
async def sync_integration(
    source: str,
    db: Session = Depends(get_db),
) -> IntegrationSyncResponse:
    try:
        result = await process_external_app_sync(source, db)
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
    db: Session = Depends(get_db),
) -> GlobalSyncResponse:
    sources: list[str] = []
    if get_github_config():
        sources.append("github")
    if get_jira_config():
        sources.append("jira")

    if not sources:
        raise HTTPException(
            status_code=400,
            detail="No GitHub or Jira integrations are configured for sync.",
        )

    try:
        results = await process_global_sync(db, sources)
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
