from typing import Literal

from pydantic import BaseModel, Field


class GitHubConfigRequest(BaseModel):
    repository_url: str = Field(min_length=1)
    branch_target: str = "main"
    personal_access_token: str = ""
    oauth_connected: bool = False
    path_component_map: dict[str, str] = Field(default_factory=dict)
    default_component_id: str | None = None


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
    branch_target: str = "main"
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
    source: Literal["notion", "slack"]
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
