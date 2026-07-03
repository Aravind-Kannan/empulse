from typing import Literal

from pydantic import BaseModel, Field


class KraSpofReason(BaseModel):
    kind: Literal["single_owner", "dominant_owner", "low_bus_factor"]
    title: str
    detail: str


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
    spof_reasons: list[KraSpofReason] = Field(default_factory=list)


class KraLink(BaseModel):
    source: str
    target: str
    relationship: str = "owns"
    codebase_share_pct: float | None = None
    ownership_source: Literal["github", "org_chart"] | None = None


class KraAnalyticsResponse(BaseModel):
    nodes: list[KraNode]
    links: list[KraLink]


class KraMetricCoverage(BaseModel):
    github: Literal["confirmed", "partial", "missing"] = "missing"
    notion: Literal["confirmed", "partial", "missing"] = "missing"
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


class DocumentationGapComponent(BaseModel):
    component_id: str
    component_name: str
    gap_reason: Literal["missing", "stale"]
    last_doc_edit: str | None = None
    notion_sources: list[str] = Field(default_factory=list)
    notion_page_urls: list[str] = Field(default_factory=list)
    days_since_activity: int | None = None


class DocumentationCoveredComponent(BaseModel):
    component_id: str
    component_name: str
    last_doc_edit: str | None = None
    notion_sources: list[str] = Field(default_factory=list)
    notion_page_urls: list[str] = Field(default_factory=list)


class DocumentationCoverageResult(BaseModel):
    coverage_pct: int | None
    active_component_count: int
    covered_count: int
    covered_components: list[DocumentationCoveredComponent] = Field(default_factory=list)
    gap_components: list[DocumentationGapComponent] = Field(default_factory=list)
    data_completeness: KraMetricCoverage


class KraSummaryResponse(BaseModel):
    critical_spof: CriticalSpofResult
    documentation_coverage: DocumentationCoverageResult
