"""Tests for ERA dimension summary headlines."""

from __future__ import annotations

from app.services.era.dimension_summaries import build_dimension_summaries
from app.services.era.dimensions import compute_knowledge
from app.services.era.normalize import TenantPercentiles
from app.services.era.signals import EmployeeSignals


def _signals(**overrides) -> EmployeeSignals:
    base = dict(
        employee_id="emp-001",
        name="Test Engineer",
        role="Engineer",
        email="test@acme.com",
        tenure_months=24.0,
        unresolved_issues=3,
        open_tasks=8,
        undocumented_solved_incidents=2,
        codebase_share_pct=45.0,
        jira_backlog_boost=2,
        assignment_breadth_pct=60.0,
        max_github_ownership_pct=68.0,
        spof_component_count=1,
        backup_review_score=20.0,
        github_connected=True,
        notion_connected=False,
        slack_connected=False,
        identity_coverage_github="confirmed",
        uses_doa_ownership=True,
        uses_review_network=True,
        max_criticality_multiplier=1.2,
        direct_reports=0,
        cross_team_sole_owner_count=0,
        sole_epic_owner_count=0,
        incident_escalation_threads=0,
        high_risk_report_roll_up=0.0,
        components_without_docs=1,
        stale_runbook_count=0,
        open_prs=2,
        on_call_incidents_30d=0,
        sprint_points=0,
        after_hours_commits=0,
        pr_cycle_time_trend=0.0,
        on_call_off_hours_messages=0,
        rising_load_trend=0.0,
    )
    base.update(overrides)
    return EmployeeSignals(**base)


def test_knowledge_summary_includes_headline_and_factors():
    result = compute_knowledge(_signals(), TenantPercentiles())
    summaries = build_dimension_summaries([result])

    knowledge = summaries["knowledge"]
    assert knowledge["score"] > 0
    assert knowledge["headline"]
    assert len(knowledge["top_factors"]) >= 1
    assert knowledge["top_factors"][0]["label"]


def test_partial_dimension_suggests_integration():
    result = compute_knowledge(
        _signals(
            github_connected=False,
            identity_coverage_github="missing",
            max_github_ownership_pct=0.0,
            codebase_share_pct=0.0,
            assignment_breadth_pct=0.0,
            spof_component_count=0,
            backup_review_score=100.0,
            uses_review_network=False,
        ),
        TenantPercentiles(),
    )
    summaries = build_dimension_summaries([result])

    assert summaries["knowledge"]["partial"] is True
    assert "GitHub" in summaries["knowledge"]["headline"]
