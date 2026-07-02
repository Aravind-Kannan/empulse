from datetime import datetime

from pydantic import BaseModel, Field


class HandoverResponse(BaseModel):
    employee_id: str
    employee_name: str
    markdown: str
    filename: str
    era_risk_score: float | None = None
    era_sections_included: list[str] = Field(default_factory=list)
    era_computed_at: datetime | None = None
    prefill_from_era: bool = False


class DashboardMetrics(BaseModel):
    average_attrition_rate: float = Field(description="Percentage")
    average_tenure_years: float
    open_incident_count: int
    active_spof_count: int
    employee_count: int


class EmployeeOption(BaseModel):
    id: str
    name: str
    role: str
