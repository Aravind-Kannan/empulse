from pydantic import BaseModel, Field


class EraEmployeeMetrics(BaseModel):
    employee_id: str
    name: str
    role: str
    email: str
    unresolved_issues: int = Field(ge=0)
    open_tasks: int = Field(ge=0)
    undocumented_solved_incidents: int = Field(ge=0)
    codebase_share_pct: float = Field(ge=0, le=100)
    risk_factor_score: float = Field(ge=0, le=100)
    risk_level: str
    jira_backlog_boost: int = Field(default=0, ge=0)


class EraAnalyticsResponse(BaseModel):
    employees: list[EraEmployeeMetrics]
