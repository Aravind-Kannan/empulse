from pydantic import BaseModel, EmailStr, Field


class MasterDataRecord(BaseModel):
    """Raw employee record from a single integration source."""

    source: str
    external_id: str
    name: str
    email: EmailStr
    title: str = Field(description="Job title / role from provider metadata")
    manager_email: EmailStr | None = None
    tenure_years: float | None = None


class MasterDataEmployee(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    manager_id: str | None = None
    manager_email: EmailStr | None = None
    tenure_years: float = 0
    source_providers: list[str] = Field(default_factory=list)


class EmployeeMasterDataResponse(BaseModel):
    company: str
    employees: list[MasterDataEmployee]
    sources_queried: list[str]
    roles_discovered: list[str]
    records_merged: int
    hierarchy_mode: str = Field(
        default="flat",
        description="flat = all members at root; structured = reporting lines resolved",
    )
    source_errors: list[str] = Field(default_factory=list)


class FetchUsersRequest(BaseModel):
    sources: list[str]
    company: str = "Acme Company"
    flat_hierarchy: bool = False
    slack_bot_token: str | None = None
    notion_integration_token: str | None = None
    notion_database_ids: str | None = None
    github_repository_url: str | None = None
    github_personal_access_token: str | None = None
    jira_site_url: str | None = None
    jira_auth_email: str | None = None
    jira_api_token: str | None = None
    jira_account_email: str | None = None
    jira_project_keys: str | None = None
