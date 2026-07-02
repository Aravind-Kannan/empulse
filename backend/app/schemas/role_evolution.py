from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RoleHistoryRecord(BaseModel):
    id: int
    employee_id: str
    old_role: str
    new_role: str
    changed_at: datetime


class EmployeeAssignmentsUpdate(BaseModel):
    component_ids: list[str] = Field(default_factory=list)


class EmployeeUpdateRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    email: EmailStr | None = None
    tenure_years: float | None = Field(default=None, ge=0)
    manager_id: str | None = None
    team_name: str | None = None
    active: bool | None = None
    assignments: EmployeeAssignmentsUpdate | None = None


class EmployeeUpdateResponse(BaseModel):
    employee_id: str
    role_changed: bool
    role_history_entry: RoleHistoryRecord | None = None
    cognee_dataset: str
    graph_nodes_created: int
    graph_edges_created: int


class EmployeeDeleteResponse(BaseModel):
    employee_id: str
    direct_reports_reparented: int
    cognee_dataset: str
    graph_nodes_created: int
    graph_edges_created: int
