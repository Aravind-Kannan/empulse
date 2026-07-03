from typing import Literal

from pydantic import BaseModel, Field


class KraNode(BaseModel):
    id: str
    label: str
    type: Literal["engineer", "component"]
    role: str | None = None
    description: str | None = None
    documentation_sources: list[str] = Field(default_factory=list)
    is_spof: bool = False
    github_verified_spof: bool = False
    bus_factor: int | None = None


class KraLink(BaseModel):
    source: str
    target: str
    relationship: str = "owns"
    codebase_share_pct: float | None = None


class KraAnalyticsResponse(BaseModel):
    nodes: list[KraNode]
    links: list[KraLink]


class KraBackupAssignmentRequest(BaseModel):
    component_id: str
    employee_id: str
    codebase_share_pct: float = Field(default=20.0, ge=0, le=100)


class KraBackupAssignmentResponse(BaseModel):
    component_id: str
    employee_id: str
    codebase_share_pct: float
    is_spof_resolved: bool


class KraMetricCoverage(BaseModel):
    github: Literal["confirmed", "partial", "missing"] = "missing"
    is_partial: bool = True


class CriticalSpofComponent(BaseModel):
    component_id: str
    component_name: str
    bus_factor: int | None = None
    owner_count: int
    owner_names: list[str] = Field(default_factory=list)
    github_verified: bool = False
    criticality: str


class CriticalSpofResult(BaseModel):
    count: int
    components: list[CriticalSpofComponent] = Field(default_factory=list)
    data_completeness: KraMetricCoverage


class KraSummaryResponse(BaseModel):
    critical_spof: CriticalSpofResult
