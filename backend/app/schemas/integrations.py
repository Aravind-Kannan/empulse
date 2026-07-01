from typing import Literal

from pydantic import BaseModel, Field


class GitHubConfigRequest(BaseModel):
    repository_url: str = Field(min_length=1)
    branch_target: str = "main"
    personal_access_token: str = ""
    oauth_connected: bool = False


class JiraConfigRequest(BaseModel):
    site_url: str = Field(min_length=1)
    project_keys: str = ""
    api_token: str = ""


class NotionValidateRequest(BaseModel):
    integration_token: str = Field(min_length=1)


class SlackValidateRequest(BaseModel):
    bot_token: str = Field(min_length=1)


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
