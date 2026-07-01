"""K / O / D / S / B dimension calculators."""

from __future__ import annotations

from app.services.era.normalize import (
    TenantPercentiles,
    absolute_operational_norm,
    normalize_value,
)
from app.services.era.signals import EmployeeSignals
from app.services.era.types import DimensionFactor, DimensionResult
from app.services.role_utils import is_leadership_role


def compute_knowledge(
    signals: EmployeeSignals,
    tenant_stats: TenantPercentiles,
) -> DimensionResult:
    github_missing = signals.identity_coverage_github == "missing" or not signals.github_connected
    ownership_pct = 0.0 if github_missing else signals.max_github_ownership_pct
    if ownership_pct == 0.0 and signals.codebase_share_pct > 0:
        ownership_pct = signals.codebase_share_pct

    ownership_term = 0.40 * ownership_pct * signals.max_criticality_multiplier
    spof_term = 0.25 * min(100.0, signals.spof_component_count * 15)
    breadth_term = 0.20 * signals.assignment_breadth_pct
    backup_term = 0.15 * (100.0 - signals.backup_review_score)

    score = min(100.0, ownership_term + spof_term + breadth_term + backup_term)
    ownership_label = (
        "DOA codebase ownership"
        if signals.uses_doa_ownership
        else "Codebase ownership concentration"
    )
    factors = [
        DimensionFactor(
            "ownership",
            ownership_label,
            ownership_pct,
            round(ownership_term, 1),
            provider="github" if not github_missing else "internal",
            synthetic=github_missing and signals.codebase_share_pct > 0 and not signals.uses_doa_ownership,
        ),
        DimensionFactor(
            "spof",
            "Single-owner components",
            float(signals.spof_component_count),
            round(spof_term, 1),
            provider="github",
        ),
        DimensionFactor(
            "breadth",
            "Assignment breadth",
            signals.assignment_breadth_pct,
            round(breadth_term, 1),
        ),
        DimensionFactor(
            "backup_review",
            "Backup review coverage gap",
            100.0 - signals.backup_review_score,
            round(backup_term, 1),
            provider="github" if signals.github_connected else "internal",
            synthetic=not signals.uses_review_network,
        ),
    ]
    return DimensionResult(
        key="knowledge",
        score=round(score, 1),
        factors=factors,
        partial=github_missing,
    )


def compute_operational(
    signals: EmployeeSignals,
    tenant_stats: TenantPercentiles,
) -> DimensionResult:
    if tenant_stats.employee_count <= 1:
        unresolved_norm = absolute_operational_norm(signals.unresolved_issues, 5.0)
        open_tasks_norm = absolute_operational_norm(signals.open_tasks, 3.0)
        open_prs_norm = absolute_operational_norm(signals.open_prs, 4.0)
        on_call_norm = absolute_operational_norm(signals.on_call_incidents_30d, 5.0)
    else:
        unresolved_norm = normalize_value(
            float(signals.unresolved_issues), tenant_stats, "unresolved_issues"
        )
        open_tasks_norm = normalize_value(
            float(signals.open_tasks), tenant_stats, "open_tasks"
        )
        open_prs_norm = normalize_value(float(signals.open_prs), tenant_stats, "open_prs")
        on_call_norm = normalize_value(
            float(signals.on_call_incidents_30d),
            tenant_stats,
            "on_call_incidents_30d",
        )

    jira_term = min(100.0, signals.jira_backlog_boost * 8.0) * 0.20
    score = min(
        100.0,
        unresolved_norm * 0.35 * signals.max_criticality_multiplier
        + open_tasks_norm * 0.25 * signals.max_criticality_multiplier
        + jira_term
        + open_prs_norm * 0.10
        + on_call_norm * 0.10,
    )
    factors = [
        DimensionFactor(
            "unresolved_issues",
            "Unresolved incidents on owned components",
            float(signals.unresolved_issues),
            round(unresolved_norm * 0.35, 1),
            provider="jira",
        ),
        DimensionFactor(
            "open_tasks",
            "Open tasks on owned components",
            float(signals.open_tasks),
            round(open_tasks_norm * 0.25, 1),
            provider="jira",
        ),
        DimensionFactor(
            "jira_backlog",
            "Unassigned high-priority bugs attributed",
            float(signals.jira_backlog_boost),
            round(jira_term, 1),
            provider="jira",
        ),
    ]
    if signals.on_call_incidents_30d > 0:
        factors.append(
            DimensionFactor(
                "on_call_incidents",
                "On-call incidents (30d)",
                float(signals.on_call_incidents_30d),
                round(on_call_norm * 0.10, 1),
                provider="slack" if signals.slack_connected else "internal",
                synthetic=not signals.slack_connected,
            )
        )
    return DimensionResult(key="operational", score=round(score, 1), factors=factors)


def compute_documentation(signals: EmployeeSignals) -> DimensionResult:
    undocumented_term = signals.undocumented_solved_incidents * 10
    no_docs_term = signals.components_without_docs * 12
    stale_term = signals.stale_runbook_count * 5
    score = min(100.0, float(undocumented_term + no_docs_term + stale_term))
    notion_live = signals.notion_connected
    slack_live = signals.slack_connected and notion_live
    undocumented_provider = "slack" if slack_live else ("notion" if notion_live else "slack")
    synthetic = (
        not slack_live
        and not notion_live
        and signals.undocumented_solved_incidents > 0
    )
    factors = [
        DimensionFactor(
            "undocumented_incidents",
            "Undocumented solved incidents",
            float(signals.undocumented_solved_incidents),
            float(undocumented_term),
            provider=undocumented_provider,
            synthetic=synthetic,
        ),
        DimensionFactor(
            "components_without_docs",
            "Owned components without docs",
            float(signals.components_without_docs),
            float(no_docs_term),
            provider="notion",
            synthetic=not notion_live,
        ),
        DimensionFactor(
            "stale_runbooks",
            "Stale runbooks",
            float(signals.stale_runbook_count),
            float(stale_term),
            provider="notion",
            synthetic=not notion_live,
        ),
    ]
    return DimensionResult(
        key="documentation",
        score=round(score, 1),
        factors=factors,
        partial=any(factor.synthetic for factor in factors),
    )


def compute_structural(signals: EmployeeSignals) -> DimensionResult:
    if is_leadership_role(signals.role):
        return DimensionResult(
            key="structural",
            score=0.0,
            excluded=True,
            factors=[],
        )

    reports_term = min(40.0, signals.direct_reports * 8)
    sole_owner_term = signals.cross_team_sole_owner_count * 15
    epic_term = signals.sole_epic_owner_count * 10
    escalation_term = min(40.0, signals.incident_escalation_threads * 4)
    roll_up_term = signals.high_risk_report_roll_up * 0.15
    score = min(
        100.0,
        reports_term + sole_owner_term + epic_term + escalation_term + roll_up_term,
    )
    factors = [
        DimensionFactor(
            "direct_reports",
            "Direct reports",
            float(signals.direct_reports),
            round(reports_term, 1),
        ),
        DimensionFactor(
            "cross_team_sole_owner",
            "Cross-team sole ownership",
            float(signals.cross_team_sole_owner_count),
            float(sole_owner_term),
        ),
        DimensionFactor(
            "incident_escalation_shadow",
            "Incident escalation concentration",
            float(signals.incident_escalation_threads),
            round(escalation_term, 1),
            provider="slack",
            synthetic=not signals.slack_connected,
        ),
        DimensionFactor(
            "high_risk_roll_up",
            "High-risk report roll-up",
            signals.high_risk_report_roll_up,
            round(roll_up_term, 1),
        ),
    ]
    return DimensionResult(key="structural", score=round(score, 1), factors=factors)


def compute_burnout(
    signals: EmployeeSignals,
    tenant_stats: TenantPercentiles,
) -> DimensionResult:
    if tenant_stats.employee_count <= 1:
        sprint_norm = absolute_operational_norm(signals.sprint_points, 2.5)
        after_hours_norm = absolute_operational_norm(signals.after_hours_commits, 8.0)
        messages_norm = absolute_operational_norm(
            signals.on_call_off_hours_messages, 5.0
        )
    else:
        sprint_norm = normalize_value(
            float(signals.sprint_points), tenant_stats, "sprint_points"
        )
        after_hours_norm = normalize_value(
            float(signals.after_hours_commits), tenant_stats, "after_hours_commits"
        )
        messages_norm = normalize_value(
            float(signals.on_call_off_hours_messages),
            tenant_stats,
            "on_call_off_hours_messages",
        )

    score = min(
        100.0,
        sprint_norm * 0.30
        + after_hours_norm * 0.25
        + signals.pr_cycle_time_trend * 0.20
        + messages_norm * 0.15
        + signals.rising_load_trend * 0.10,
    )
    factors = [
        DimensionFactor(
            "sprint_points",
            "Sprint delivery load",
            float(signals.sprint_points),
            round(sprint_norm * 0.30, 1),
            provider="jira",
            synthetic=True,
        ),
        DimensionFactor(
            "after_hours_commits",
            "After-hours commits",
            float(signals.after_hours_commits),
            round(after_hours_norm * 0.25, 1),
            provider="github",
            synthetic=True,
        ),
        DimensionFactor(
            "rising_load",
            "Rising workload trend",
            signals.rising_load_trend,
            round(signals.rising_load_trend * 0.10, 1),
            synthetic=True,
        ),
    ]
    if signals.on_call_off_hours_messages > 0:
        factors.append(
            DimensionFactor(
                "on_call_off_hours_messages",
                "After-hours on-call Slack activity",
                float(signals.on_call_off_hours_messages),
                round(messages_norm * 0.15, 1),
                provider="slack",
                synthetic=not signals.slack_connected,
            )
        )
    return DimensionResult(key="burnout", score=round(score, 1), factors=factors)
