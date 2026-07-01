from datetime import datetime

from pydantic import BaseModel, Field

EraDimensionKey = str  # knowledge | operational | documentation | structural | burnout
EraRiskLevel = str  # low | medium | high
ComponentCriticality = str  # tier1_revenue | tier2_core | tier3_support
IdentityCoverageLevel = str  # confirmed | high | missing
IntegrationId = str  # github | jira | slack | notion


class EraDimensions(BaseModel):
    knowledge: float = Field(ge=0, le=100)
    operational: float = Field(ge=0, le=100)
    documentation: float = Field(ge=0, le=100)
    structural: float = Field(ge=0, le=100)
    burnout: float = Field(ge=0, le=100)
    partial: dict[str, bool] = Field(default_factory=dict)


class EraEvidenceSource(BaseModel):
    provider: str
    label: str
    url: str | None = None


class EraEvidenceItem(BaseModel):
    id: str
    dimension: EraDimensionKey
    severity: str  # high | medium | low
    title: str
    description: str
    impact_points: float = Field(ge=0)
    sources: list[EraEvidenceSource] = Field(default_factory=list)
    synthetic: bool = False
    mitigation_status: str | None = None


class EraAffectedComponent(BaseModel):
    id: str
    name: str
    spof: bool = False
    criticality: ComponentCriticality = "tier2_core"
    ownership_pct: float | None = None


class EraRecoveryEstimate(BaseModel):
    min: int = Field(ge=1)
    max: int = Field(ge=1)


class EraUnmappedActivityCount(BaseModel):
    provider: str
    count: int = Field(ge=0)


class EraTeamSummary(BaseModel):
    avg_risk_score: float = Field(ge=0, le=100)
    high_risk_count: int = Field(ge=0)
    medium_risk_count: int = Field(ge=0)
    low_risk_count: int = Field(ge=0)
    spof_component_count: int = Field(ge=0)
    open_p1_count: int = Field(ge=0)
    undocumented_incident_count: int = Field(ge=0)
    top_risk_driver: EraDimensionKey = "knowledge"
    estimated_recovery_weeks: EraRecoveryEstimate
    data_health_pct: float = Field(ge=0, le=100)


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
    dimensions: EraDimensions | None = None
    evidence: list[EraEvidenceItem] = Field(default_factory=list)
    evidence_total_count: int = Field(default=0, ge=0)
    affected_components: list[EraAffectedComponent] = Field(default_factory=list)
    identity_coverage: dict[str, IdentityCoverageLevel] = Field(default_factory=dict)
    data_completeness_pct: float = Field(default=0, ge=0, le=100)
    recovery_estimate_weeks: EraRecoveryEstimate | None = None
    departure_watchlist: bool = False
    trend_7d: float | None = None
    excluded: bool = False
    exclusion_reason: str | None = None


class EraAnalyticsResponse(BaseModel):
    computed_at: datetime
    demo_mode: bool = False
    warnings: list[str] = Field(default_factory=list)
    team_summary: EraTeamSummary
    employees: list[EraEmployeeMetrics]
    unmapped_activity: list[EraUnmappedActivityCount] = Field(default_factory=list)
    sync_freshness: dict[str, str | None] = Field(default_factory=dict)


class EraEmployeeDetailResponse(BaseModel):
    computed_at: datetime
    employee: EraEmployeeMetrics
    evidence: list[EraEvidenceItem]
    evidence_total_count: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
