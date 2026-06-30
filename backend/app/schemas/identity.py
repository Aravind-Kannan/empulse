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


class IdentityReconciliationResponse(BaseModel):
    employees: list[EmployeeIdentityRow]
    provider_members: dict[str, list[ProviderMember]]
    connected_providers: list[str]


class IdentityMappingsUpdateRequest(BaseModel):
    mappings: list[EmployeeIdentityMapping]
