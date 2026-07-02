from datetime import datetime

from pydantic import BaseModel, Field

IdentityProvider = str  # github | jira | slack | notion


class ProviderMember(BaseModel):
    id: str
    label: str
    email: str | None = None


class EmployeeIdentityMapping(BaseModel):
    employee_id: str
    provider: str
    provider_username_or_id: str


class EmployeeIdentityRecord(EmployeeIdentityMapping):
    id: int


class EmployeeIdentityRow(BaseModel):
    employee_id: str
    name: str
    email: str
    role: str
    mappings: dict[str, str | None] = Field(default_factory=dict)


class UnmappedCountByProvider(BaseModel):
    provider: str
    count: int = Field(ge=0)


class IdentityReconciliationResponse(BaseModel):
    employees: list[EmployeeIdentityRow]
    provider_members: dict[str, list[ProviderMember]]
    connected_providers: list[str]
    provider_warnings: dict[str, str] = Field(default_factory=dict)
    unmapped_activity: list[UnmappedCountByProvider] = Field(default_factory=list)
    total_unmapped_count: int = 0


class UnmappedActivityRecord(BaseModel):
    id: int
    provider: str
    provider_user_id: str
    provider_label: str | None = None
    event_type: str
    occurrence_count: int = Field(ge=1)
    first_seen_at: datetime
    last_seen_at: datetime
    payload_json: dict = Field(default_factory=dict)


class UnmappedActivityListResponse(BaseModel):
    items: list[UnmappedActivityRecord]
    total_unmapped_count: int = Field(ge=0)
    unmapped_by_provider: list[UnmappedCountByProvider] = Field(default_factory=list)


class IdentityMappingsUpdateRequest(BaseModel):
    mappings: list[EmployeeIdentityMapping]
