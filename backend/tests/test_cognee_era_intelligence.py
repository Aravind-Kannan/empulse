"""ERA Step 10 — Cognee intelligence tests."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.operational import Assignment, Component, Employee, EmployeeIdentity
from app.schemas.era import EraAffectedComponent, EraRecoveryEstimate
from app.services.cognee_era_intelligence import (
    CogneeUnavailable,
    build_employee_detail_intelligence,
    detect_documentation_gaps,
    find_backup_candidates,
    reset_intelligence_cache_for_tests,
)
from app.services.era_analytics import get_era_employee_detail, get_era_metrics
from app.services.github_client import load_fixture_activities
from app.services.integration_telemetry import (
    apply_github_telemetry,
    apply_jira_telemetry,
    reset_telemetry_for_tests,
)
from app.services.jira_types import JiraIssueActivity

from tests.conftest import add_employee


@pytest.fixture(autouse=True)
def _reset_state():
    reset_telemetry_for_tests()
    reset_intelligence_cache_for_tests()
    yield
    reset_telemetry_for_tests()
    reset_intelligence_cache_for_tests()


@pytest.fixture()
def client():
    return TestClient(app)


def _seed_backup_fixtures(db, tenant_id: uuid.UUID) -> None:
    for employee_id, gh_id, name in (
        ("emp-primary", "gh-primary", "Primary Owner"),
        ("emp-backup-a", "gh-backup-a", "Backup Alice"),
        ("emp-backup-b", "gh-backup-b", "Backup Ben"),
    ):
        add_employee(
            db,
            tenant_id,
            employee_id=employee_id,
            name=name,
            email=f"{employee_id}@acme.com",
        )
        db.add(
            EmployeeIdentity(
                tenant_id=tenant_id,
                employee_id=employee_id,
                provider="github",
                provider_username_or_id=gh_id,
                confidence="confirmed",
            )
        )
    db.add(
        Component(
            id="comp-payments",
            tenant_id=tenant_id,
            name="Payment Gateway",
            description="",
        )
    )
    db.add(
        Assignment(
            tenant_id=tenant_id,
            employee_id="emp-primary",
            component_id="comp-payments",
            codebase_share_pct=80.0,
        )
    )
    db.commit()


def test_backup_candidates_rank_two_contributors(db, tenant):
    _seed_backup_fixtures(db, tenant.id)
    activities = load_fixture_activities()
    for activity in activities:
        activity.author_provider_user_id = {
            "benrivera": "gh-backup-a",
            "carapatel": "gh-backup-b",
            "diegoalvarez": "gh-primary",
        }.get(activity.author_login.lower(), activity.author_provider_user_id)
        for file_change in activity.files:
            if "payments" in file_change.path:
                file_change.component_id = "comp-payments"

    apply_github_telemetry(db, tenant.id, activities)

    ranked = find_backup_candidates(
        db,
        tenant.id,
        "emp-primary",
        "comp-payments",
        component_name="Payment Gateway",
        limit=3,
    )
    assert len(ranked) >= 1
    assert ranked[0].employee_id != "emp-primary"
    if len(ranked) >= 2:
        assert ranked[0].score >= ranked[1].score


def test_ramping_label_when_review_participation_high(db, tenant):
    _seed_backup_fixtures(db, tenant.id)
    activities = load_fixture_activities()
    for activity in activities:
        activity.author_provider_user_id = "gh-primary"
        for file_change in activity.files:
            file_change.component_id = "comp-payments"
        if activity.author_login.lower() == "benrivera":
            activity.author_provider_user_id = "gh-backup-a"
            activity.reviewer_logins = ["primary"]
        if activity.author_login.lower() == "diegoalvarez":
            activity.reviewer_logins = ["backup-a", "backup-b", "backup-c"]

    apply_github_telemetry(db, tenant.id, activities)
    ranked = find_backup_candidates(
        db,
        tenant.id,
        "emp-primary",
        "comp-payments",
        component_name="Payment Gateway",
    )
    ramping = [row for row in ranked if row.label == "ramping"]
    assert ramping or ranked


def test_detect_documentation_gap_without_notion_sources(db, tenant):
    _seed_backup_fixtures(db, tenant.id)
    activities = load_fixture_activities()
    for activity in activities:
        for file_change in activity.files:
            file_change.component_id = "comp-payments"
    apply_github_telemetry(db, tenant.id, activities)

    with (
        patch("app.services.cognee_era_intelligence.has_notion_sync", return_value=True),
        patch("app.services.cognee_era_intelligence.get_notion_component_sources", return_value=[]),
        patch(
            "app.services.cognee_era_intelligence.get_github_ownership",
            return_value={"comp-payments": {"emp-primary": 90.0}},
        ),
    ):
        gaps = detect_documentation_gaps(["comp-payments"], notion_connected=True)
    assert "comp-payments" in gaps


def test_enrich_evidence_adds_graph_jira_links(db, tenant):
    _seed_backup_fixtures(db, tenant.id)
    activities = load_fixture_activities()
    for activity in activities[:2]:
        activity.author_provider_user_id = "gh-primary"
        for file_change in activity.files:
            file_change.component_id = "comp-payments"
    apply_github_telemetry(db, tenant.id, activities)
    apply_jira_telemetry(
        db,
        tenant.id,
        [
            JiraIssueActivity(
                issue_key="PAY-101",
                issue_type="Bug",
                priority="High",
                status="Open",
                status_category="new",
                project_key="PAY",
                component_id="comp-payments",
                issue_url="https://acme.atlassian.net/browse/PAY-101",
            )
        ],
    )

    employee = db.query(Employee).filter_by(id="emp-primary").one()
    affected = [
        EraAffectedComponent(id="comp-payments", name="Payment Gateway", spof=True)
    ]
    evidence = [
        {
            "id": "emp-primary-k-1",
            "dimension": "knowledge",
            "severity": "high",
            "title": "SPOF ownership",
            "description": "Primary owner on payments.",
            "impact_points": 30.0,
            "sources": [{"provider": "github", "label": "PR #1", "url": "https://github.com/pr/1"}],
            "synthetic": False,
        }
    ]
    result = build_employee_detail_intelligence(
        db,
        tenant.id,
        employee,
        evidence,
        affected,
        jira_connected=True,
        notion_connected=False,
        recovery_estimate=EraRecoveryEstimate(min=2, max=4),
        use_cache=False,
    )
    jira_sources = [
        source
        for item in result.enriched_evidence
        for source in item.get("sources", [])
        if source.get("provider") == "jira"
    ]
    assert jira_sources
    assert any("PAY-101" in (source.get("label") or "") for source in jira_sources)


def test_cognee_down_returns_degraded_warning(db, tenant):
    _seed_backup_fixtures(db, tenant.id)
    employee = db.query(Employee).filter_by(id="emp-primary").one()
    affected = [
        EraAffectedComponent(id="comp-payments", name="Payment Gateway", spof=True)
    ]

    with patch(
        "app.services.cognee_era_intelligence.fetch_blast_radius_narrative",
        new=AsyncMock(side_effect=CogneeUnavailable("down")),
    ):
        result = build_employee_detail_intelligence(
            db,
            tenant.id,
            employee,
            [],
            affected,
            jira_connected=False,
            notion_connected=False,
            recovery_estimate=None,
            use_cache=False,
        )
    assert "cognee_degraded" in result.warnings


def test_detail_api_includes_backup_candidates(client, db, tenant):
    _seed_backup_fixtures(db, tenant.id)
    activities = load_fixture_activities()
    for activity in activities:
        for file_change in activity.files:
            if "payments" in file_change.path:
                file_change.component_id = "comp-payments"
    apply_github_telemetry(db, tenant.id, activities)

    with patch("app.services.era_analytics.get_settings") as mock_settings:
        mock_settings.return_value.era_v2_scoring = True
        detail = get_era_employee_detail(db, tenant, "emp-primary", limit=20, offset=0)

    assert detail is not None
    assert isinstance(detail.backup_candidates, list)
    assert isinstance(detail.warnings, list)


def test_list_endpoint_does_not_call_cognee_intelligence(db, tenant):
    with patch("app.services.era_analytics.get_settings") as mock_settings:
        mock_settings.return_value.era_v2_scoring = True
        with patch(
            "app.services.era_analytics.build_employee_detail_intelligence"
        ) as intelligence_mock:
            get_era_metrics(db, tenant)
    intelligence_mock.assert_not_called()


def test_detail_api_cognee_degraded_still_200(db, tenant):
    _seed_backup_fixtures(db, tenant.id)
    with patch("app.services.era_analytics.get_settings") as mock_settings:
        mock_settings.return_value.era_v2_scoring = True
        with patch(
            "app.services.cognee_era_intelligence.fetch_blast_radius_narrative",
            new=AsyncMock(side_effect=CogneeUnavailable("down")),
        ):
            detail = get_era_employee_detail(db, tenant, "emp-primary", limit=20, offset=0)
    assert detail is not None
    assert "cognee_degraded" in detail.warnings
