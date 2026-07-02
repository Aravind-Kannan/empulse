from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

FileRiskQuadrant = Literal["critical", "stable_niche", "active_shared", "healthy"]


class FileRiskItem(BaseModel):
    component_id: str
    component_name: str
    repo_path: str
    file_path: str
    churn_score: int = Field(ge=0)
    contributor_count: int = Field(ge=0)
    bus_factor: int = Field(ge=0)
    quadrant: FileRiskQuadrant
    primary_owner_employee_id: str | None = None
    primary_owner_name: str | None = None
    primary_owner_doa_pct: float | None = None
    github_url: str | None = None
    computed_at: datetime


class KraFileRiskResponse(BaseModel):
    component_id: str | None = None
    component_name: str | None = None
    files: list[FileRiskItem] = Field(default_factory=list)
    quadrant_counts: dict[str, int] = Field(default_factory=dict)
    cross_training_priority: list[FileRiskItem] = Field(default_factory=list)


class EraHotspotsResponse(BaseModel):
    employee_id: str
    critical_count: int = Field(ge=0)
    files: list[FileRiskItem] = Field(default_factory=list)
