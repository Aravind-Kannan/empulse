from datetime import date, datetime

from pydantic import BaseModel, Field

EraDimensionKey = str  # knowledge | operational | documentation | structural | burnout
EraRiskLevel = str  # low | medium | high
ComponentCriticality = str  # tier1_revenue | tier2_core | tier3_support
IdentityCoverageLevel = str  # confirmed | high | medium | missing
IntegrationId = str  # github | jira | slack | notion


class EraDimensions(BaseModel):
    knowledge: float = Field(ge=0, le=100)
    operational: float = Field(ge=0, le=100)
    documentation: float = Field(ge=0, le=100)
    structural: float = Field(ge=0, le=100)
    burnout: float = Field(ge=0, le=100)
    partial: dict[str, bool] = Field(default_factory=dict)


class EraDimensionFactorSummary(BaseModel):
    key: str
    label: str
    value: float
    impact_points: float = Field(ge=0)
    provider: str = "internal"
    synthetic: bool = False


class EraDimensionSummary(BaseModel):
    score: float = Field(ge=0, le=100)
    partial: bool = False
    headline: str = ""
    top_factors: list[EraDimensionFactorSummary] = Field(default_factory=list)


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
    suggested_mitigation: str | None = None
    mitigation_assignee_id: str | None = None
    mitigation_due_date: str | None = None
    mitigation_notes: str | None = None


class EraMitigationItem(BaseModel):
    evidence_id: str
    title: str
    priority: str = "medium"
    link: str | None = None
    suggested_mitigation: str | None = None
    mitigation_status: str = "open"
    mitigation_assignee_id: str | None = None
    mitigation_due_date: str | None = None
    mitigation_notes: str | None = None


class EraEvidenceMitigationPatchRequest(BaseModel):
    employee_id: str
    mitigation_status: str
    assignee_id: str | None = None
    due_date: date | None = None
    notes: str | None = None


class EraEvidenceMitigationPatchResponse(BaseModel):
    evidence_id: str
    employee_id: str
    mitigation_status: str
    suggested_mitigation: str | None = None
    mitigation_assignee_id: str | None = None
    mitigation_due_date: str | None = None
    mitigation_notes: str | None = None
    updated_at: datetime


class EraAffectedComponent(BaseModel):
    id: str
    name: str
    spof: bool = False
    criticality: ComponentCriticality = "tier2_core"
    ownership_pct: float | None = None


class EraBackupCandidate(BaseModel):
    employee_id: str
    name: str
    component_id: str
    component_name: str
    ownership_pct: float = Field(ge=0, le=100)
    review_count: int = Field(ge=0)
    recent_commits: int = Field(ge=0)
    score: float = Field(ge=0)
    label: str  # ramping | secondary


class EraRecoveryEstimate(BaseModel):
    min: int = Field(ge=1)
    max: int = Field(ge=1)


class EraUnmappedActivityCount(BaseModel):
    provider: str
    count: int = Field(ge=0)


class EraTeamSummary(BaseModel):
    avg_risk_score: float = Field(ge=0, le=100)
    avg_risk_trend_7d: float | None = None
    high_risk_count: int = Field(ge=0)
    medium_risk_count: int = Field(ge=0)
    low_risk_count: int = Field(ge=0)
    spof_component_count: int = Field(ge=0)
    open_p1_count: int = Field(ge=0)
    undocumented_incident_count: int = Field(ge=0)
    top_risk_driver: EraDimensionKey = "knowledge"
    estimated_recovery_weeks: EraRecoveryEstimate
    data_health_pct: float = Field(ge=0, le=100)
    org_health_score: float = Field(default=0.0, ge=0, le=100)
    orphan_file_count: int = Field(default=0, ge=0)
    orphan_delta_90d: int = Field(default=0)
    org_health_caution: bool = False
    critical_hotspot_count: int = Field(default=0, ge=0)
    last_risk_review_at: datetime | None = None
    unacknowledged_alert_count: int = Field(default=0, ge=0)


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
    dimension_summaries: dict[str, EraDimensionSummary] = Field(default_factory=dict)
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
    identity_warning: bool = False


class EraAnalyticsResponse(BaseModel):
    computed_at: datetime
    demo_mode: bool = False
    warnings: list[str] = Field(default_factory=list)
    team_summary: EraTeamSummary
    employees: list[EraEmployeeMetrics]
    unmapped_activity: list[EraUnmappedActivityCount] = Field(default_factory=list)
    sync_freshness: dict[str, str | None] = Field(default_factory=dict)
    team_risk_history_30d: list["EraRiskHistoryPoint"] = Field(default_factory=list)
    team_evidence: list[EraEvidenceItem] = Field(default_factory=list)


class EraRiskHistoryPoint(BaseModel):
    snapshot_date: str
    risk_factor_score: float = Field(ge=0, le=100)
    org_health_score: float | None = Field(default=None, ge=0, le=100)
    orphan_file_count: int | None = Field(default=None, ge=0)


class EraManagerRollupReport(BaseModel):
    employee_id: str
    name: str
    role: str
    risk_factor_score: float = Field(ge=0, le=100)
    risk_level: str
    trend_7d: float | None = None


class EraManagerRollupResponse(BaseModel):
    computed_at: datetime
    manager_id: str
    manager_name: str
    team_avg_risk: float = Field(ge=0, le=100)
    high_risk_report_count: int = Field(ge=0)
    manager_exposure_bonus: int = Field(ge=0, le=15)
    reports: list[EraManagerRollupReport] = Field(default_factory=list)


class EraEmployeeDetailResponse(BaseModel):
    computed_at: datetime
    employee: EraEmployeeMetrics
    evidence: list[EraEvidenceItem]
    evidence_total_count: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    backup_candidates: list[EraBackupCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blast_radius_narrative: str | None = None
    risk_history_30d: list[EraRiskHistoryPoint] = Field(default_factory=list)
    mitigations: list[EraMitigationItem] = Field(default_factory=list)
    open_mitigations_count: int = Field(default=0, ge=0)


class EraReviewNetworkEdge(BaseModel):
    reviewer_employee_id: str
    author_employee_id: str
    review_count: int = Field(ge=1)
    reviewer_login: str
    author_login: str


class EraReviewNetworkMetrics(BaseModel):
    employee_id: str
    review_concentration_pct: float = Field(ge=0, le=100)
    reviews_given_count: int = Field(ge=0)
    reviews_received_count: int = Field(ge=0)
    sole_reviewer_count: int = Field(ge=0)
    unique_reviewers_on_prs: int = Field(ge=0)
    isolation_score: float = Field(ge=0, le=100)
    backup_review_score: float = Field(ge=0, le=100)
    recent_pr_count: int = Field(ge=0)
    no_backup_pr_urls: list[str] = Field(default_factory=list)
    top_reviewer_employee_id: str | None = None
    top_reviewer_login: str | None = None


class EraReviewNetworkResponse(BaseModel):
    computed_at: datetime
    employee_id: str
    window_days: int = Field(ge=1)
    metrics: EraReviewNetworkMetrics | None = None
    incoming_reviewers: list[EraReviewNetworkEdge] = Field(default_factory=list)


class EraRiskyChangeItem(BaseModel):
    pr_number: int
    pr_url: str
    author_employee_id: str | None = None
    author_login: str
    author_name: str | None = None
    severity: str
    rule: str
    title: str
    description: str
    merged_at: str | None = None
    impact_points: float = Field(ge=0)


class EraTeamRiskyChangesResponse(BaseModel):
    computed_at: datetime
    window_days: int = Field(ge=1)
    items: list[EraRiskyChangeItem] = Field(default_factory=list)


class EraAlertItem(BaseModel):
    id: int
    rule_id: str
    severity: str
    title: str
    description: str
    employee_id: str | None = None
    component_id: str | None = None
    evidence_id: str | None = None
    created_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None


class EraAlertsResponse(BaseModel):
    computed_at: datetime
    alerts: list[EraAlertItem] = Field(default_factory=list)
    unacknowledged_count: int = Field(default=0, ge=0)


class EraAlertAcknowledgeRequest(BaseModel):
    acknowledged_by: str | None = None


class EraTeamReviewItem(BaseModel):
    id: int
    reviewed_at: datetime
    reviewer_user_id: str | None = None
    notes: str | None = None
    snapshot_avg_risk: float = Field(ge=0, le=100)
    delta_since_last: float | None = None


class EraTeamReviewsResponse(BaseModel):
    computed_at: datetime
    reviews: list[EraTeamReviewItem] = Field(default_factory=list)


class EraTeamReviewCreateRequest(BaseModel):
    notes: str | None = None
    reviewer_user_id: str | None = None


class EraReviewCadenceResponse(BaseModel):
    computed_at: datetime
    last_reviewed_at: datetime | None = None
    days_since_last_review: int | None = None
    review_overdue: bool = False
    review_cadence_days: int = Field(default=30, ge=1)
    snapshot_avg_risk: float | None = Field(default=None, ge=0, le=100)


class EraSettingsResponse(BaseModel):
    slack_webhook_url: str = ""
    slack_webhook_enabled: bool = False
    unmapped_threshold: int = Field(default=5, ge=1)
    review_cadence_days: int = Field(default=30, ge=1)


class EraSettingsUpdateRequest(BaseModel):
    slack_webhook_url: str | None = None
    slack_webhook_enabled: bool | None = None
    unmapped_threshold: int | None = Field(default=None, ge=1)
    review_cadence_days: int | None = Field(default=None, ge=1)


class EraOpenP1IssueItem(BaseModel):
    issue_key: str
    summary: str
    priority: str
    status: str
    project_key: str
    issue_type: str
    issue_url: str | None = None
    updated_at: datetime | None = None
    assignee_employee_id: str | None = None
    assignee_name: str | None = None
    assignee_unmapped: bool = False
    component_id: str | None = None
    component_name: str | None = None


class EraOpenP1IssuesResponse(BaseModel):
    computed_at: datetime
    jira_synced: bool = False
    total_count: int = Field(ge=0)
    issues: list[EraOpenP1IssueItem] = Field(default_factory=list)
    filters_note: str = (
        "Bugs and incidents from the latest Jira sync with Critical, Highest, or High "
        "priority that are not Done (same scope as the Open P1 KPI)."
    )
