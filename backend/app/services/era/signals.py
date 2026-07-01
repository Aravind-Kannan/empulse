"""Employee signal inputs for ERA dimension calculators."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EmployeeSignals:
    employee_id: str
    name: str
    role: str
    email: str
    tenure_months: float
    direct_reports: int = 0
    unresolved_issues: int = 0
    open_tasks: int = 0
    undocumented_solved_incidents: int = 0
    codebase_share_pct: float = 0.0
    jira_backlog_boost: int = 0
    max_github_ownership_pct: float = 0.0
    spof_component_count: int = 0
    assignment_breadth_pct: float = 0.0
    backup_review_score: float = 50.0
    components_without_docs: int = 0
    stale_runbook_count: int = 0
    cross_team_sole_owner_count: int = 0
    sole_epic_owner_count: int = 0
    high_risk_report_roll_up: float = 0.0
    open_prs: int = 0
    on_call_incidents_30d: int = 0
    sprint_points: int = 0
    after_hours_commits: int = 0
    pr_cycle_time_trend: float = 0.0
    on_call_off_hours_messages: int = 0
    rising_load_trend: float = 0.0
    on_call_rotation_active: bool = False
    owned_component_count: int = 0
    max_criticality_multiplier: float = 1.0
    identity_coverage_github: str = "missing"
    github_connected: bool = False
    component_names: list[str] = field(default_factory=list)
