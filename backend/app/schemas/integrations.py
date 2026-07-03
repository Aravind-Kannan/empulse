from typing import Literal

from pydantic import BaseModel, Field


class GitHubConfigRequest(BaseModel):
    repository_url: str = ""
    repository_urls: list[str] = Field(default_factory=list)
    branch_target: str = "main"
    branch_targets: list[str] = Field(default_factory=list)
    sync_all_branches: bool = False
    ingest_file_content: bool = False
    personal_access_token: str = ""
    oauth_connected: bool = False
    path_component_map: dict[str, str] = Field(default_factory=dict)
    default_component_id: str | None = None

    def resolved_repository_urls(self) -> list[str]:
        urls = [url.strip() for url in self.repository_urls if url.strip()]
        if not urls and self.repository_url.strip():
            urls = [self.repository_url.strip()]
        return urls

    def resolved_branch_targets(self) -> list[str] | None:
        if self.sync_all_branches:
            return None
        branches = [branch.strip() for branch in self.branch_targets if branch.strip()]
        if not branches and self.branch_target.strip():
            branches = [self.branch_target.strip()]
        return branches or ["main"]

    def with_repository(self, repository_url: str) -> "GitHubConfigRequest":
        return self.model_copy(
            update={
                "repository_url": repository_url,
                "repository_urls": [repository_url],
            }
        )


class JiraConfigRequest(BaseModel):
    site_url: str = Field(min_length=1)
    project_keys: str = ""
    api_token: str = ""
    account_email: str = ""
    component_field_map: dict[str, str] = Field(default_factory=dict)
    label_component_map: dict[str, str] = Field(default_factory=dict)
    project_component_map: dict[str, str] = Field(default_factory=dict)
    default_component_id: str | None = None
    high_priorities: list[str] = Field(
        default_factory=lambda: ["Highest", "High", "Critical"]
    )


class NotionValidateRequest(BaseModel):
    integration_token: str = Field(min_length=1)


class GitHubValidateRequest(BaseModel):
    personal_access_token: str = Field(min_length=1)
    repository_url: str = ""
    repository_urls: list[str] = Field(default_factory=list)
    branch_target: str = "main"
    branch_targets: list[str] = Field(default_factory=list)
    sync_all_branches: bool = False


class GitHubDiscoverRequest(BaseModel):
    personal_access_token: str = Field(min_length=1)


class GitHubRepoInfo(BaseModel):
    full_name: str
    html_url: str
    default_branch: str
    private: bool
    description: str | None = None


class GitHubDiscoverResponse(BaseModel):
    repositories: list[GitHubRepoInfo]
    message: str


class GitHubBranchesRequest(BaseModel):
    personal_access_token: str = Field(min_length=1)
    repository_url: str = Field(min_length=1)


class GitHubBranchesResponse(BaseModel):
    repository_url: str
    default_branch: str
    branches: list[str]


class SlackValidateRequest(BaseModel):
    bot_token: str = Field(min_length=1)


class SlackConfigRequest(BaseModel):
    workspace_url: str = ""
    bot_token: str = ""
    channel_ids: str = ""
    incident_channel_ids: str = ""
    on_call_channel_ids: str = ""
    validated: bool = False
    previously_connected: bool = False


class NotionConfigRequest(BaseModel):
    integration_token: str = ""
    database_ids: str = ""
    validated: bool = False
    previously_connected: bool = False


class StoredSlackConfig(BaseModel):
    workspace_url: str = ""
    bot_token: str = ""
    channel_ids: str = ""
    incident_channel_ids: str = ""
    on_call_channel_ids: str = ""
    validated: bool = False
    previously_connected: bool = False


class StoredNotionConfig(BaseModel):
    integration_token: str = ""
    database_ids: str = ""
    validated: bool = False
    previously_connected: bool = False


class StoredGitHubConfig(BaseModel):
    repository_url: str = ""
    repository_urls: list[str] = Field(default_factory=list)
    branch_target: str = "main"
    branch_targets: list[str] = Field(default_factory=list)
    sync_all_branches: bool = False
    ingest_file_content: bool = False
    personal_access_token: str = ""
    oauth_connected: bool = False
    validated: bool = False
    previously_connected: bool = False


class StoredJiraConfig(BaseModel):
    site_url: str = ""
    project_keys: str = ""
    api_token: str = ""
    account_email: str = ""
    validated: bool = False
    previously_connected: bool = False


class TenantIntegrationsConfigResponse(BaseModel):
    slack: StoredSlackConfig
    notion: StoredNotionConfig
    github: StoredGitHubConfig
    jira: StoredJiraConfig


class IntegrationValidateResponse(BaseModel):
    source: Literal["notion", "slack", "github"]
    valid: bool
    message: str


class IntegrationConfigResponse(BaseModel):
    source: Literal["github", "jira", "notion", "slack"]
    configured: bool
    message: str


class IntegrationSyncResponse(BaseModel):
    source: str
    cognee_dataset: str
    documents_ingested: int
    graph_nodes_created: int
    graph_edges_created: int
    narrative_preview: str
    items_fetched: int = 0
    items_new: int = 0
    items_updated: int = 0
    items_skipped: int = 0
    skipped_preview: list[str] = Field(default_factory=list)
    already_synced_note: str = ""
    repository_url: str = ""
    branch: str = ""
    ref: str = ""
    files_discovered: int = 0
    files_mapped_to_components: int = 0
    branches_synced: list[str] = Field(default_factory=list)
    branches_total: int = 0
    channels_discovered: int | None = None
    channels_synced: int | None = None
    messages_ingested: int | None = None


class GitHubRepoSyncRequest(BaseModel):
    repository_url: str = Field(min_length=1)


class CogneeDatasetResetRequest(BaseModel):
    """Reset the tenant Cognee knowledge graph dataset."""

    memory_only: bool = Field(
        default=False,
        description=(
            "When true, delete graph nodes and vector embeddings only. "
            "Raw dataset files remain for re-cognify."
        ),
    )
    clear_ledger: bool = Field(
        default=True,
        description="Clear integration sync ledger so the next sync re-ingests all items.",
    )
    clear_telemetry: bool = Field(
        default=False,
        description=(
            "Also clear Postgres DOA/ownership snapshots and in-memory integration telemetry."
        ),
    )


class CogneeDatasetResetResponse(BaseModel):
    dataset: str
    mode: str
    memory_only: bool
    forget_summary: dict = Field(default_factory=dict)
    graph_purge: dict = Field(default_factory=dict)
    ledger_rows_removed: int = 0
    telemetry_cleared: bool = False
    message: str


class GlobalSyncResponse(BaseModel):
    results: list[IntegrationSyncResponse]
    total_nodes_created: int
    total_edges_created: int


class MemberRosterSyncResponse(BaseModel):
    sources: list[str]
    employees_imported: int
    employees_added: int
    employees_updated: int
    employees_persisted: int
    hierarchy_mode: str
    cognee_dataset: str
    graph_nodes_created: int
    graph_edges_created: int
    source_errors: list[str] = Field(default_factory=list)
