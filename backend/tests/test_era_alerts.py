"""ERA Step 17 — alerts and review cadence tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.operational import (
    Assignment,
    Component,
    EraTeamReview,
    FileRiskSnapshot,
    UnmappedActivity,
)
from app.schemas.era import EraTeamReviewCreateRequest
from app.services.era_alerts import (
    acknowledge_era_alert,
    evaluate_alert_candidates,
    get_review_cadence,
    list_era_alerts,
    record_era_review,
    sync_era_alerts,
)
from app.services.integration_telemetry import reset_telemetry_for_tests

from tests.conftest import add_employee


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_telemetry():
    reset_telemetry_for_tests()
    yield
    reset_telemetry_for_tests()


def _seed_spof_tier1(db, tenant_id: uuid.UUID) -> None:
    add_employee(
        db,
        tenant_id,
        employee_id="emp-spof-owner",
        name="SPOF Owner",
        email="spof@acme.com",
    )
    db.add(
        Component(
            id="comp-payments",
            tenant_id=tenant_id,
            name="Payment Gateway",
            description="",
            criticality="tier1_revenue",
        )
    )
    db.add(
        Assignment(
            tenant_id=tenant_id,
            employee_id="emp-spof-owner",
            component_id="comp-payments",
            codebase_share_pct=95.0,
        )
    )
    db.commit()


def test_spof_tier1_rule_fires(db, tenant):
    _seed_spof_tier1(db, tenant.id)
    with patch("app.services.era_alerts.has_github_sync", return_value=True), patch(
        "app.services.era_alerts.is_github_spof",
        return_value=True,
    ):
        candidates = evaluate_alert_candidates(db, tenant.id)
    rules = {item.rule_id for item in candidates}
    assert "spof_tier1" in rules


def test_identity_gap_rule_fires(db, tenant):
    for index in range(6):
        db.add(
            UnmappedActivity(
                tenant_id=tenant.id,
                provider="github",
                provider_user_id=f"unknown-{index}",
                event_type="github_pr",
                payload_json={},
            )
        )
    db.commit()
    candidates = evaluate_alert_candidates(db, tenant.id)
    assert any(item.rule_id == "identity_gap" for item in candidates)


def test_critical_file_rule_fires(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-file-owner",
        name="File Owner",
        email="file@acme.com",
    )
    db.add(
        Component(
            id="comp-auth",
            tenant_id=tenant.id,
            name="Auth Service",
            description="",
        )
    )
    db.add(
        FileRiskSnapshot(
            tenant_id=tenant.id,
            component_id="comp-auth",
            repo_path="acme/auth",
            file_path="src/auth/session.rs",
            churn_score=14,
            contributor_count=1,
            bus_factor=1,
            quadrant="critical",
            primary_owner_employee_id="emp-file-owner",
            primary_owner_doa_pct=88.0,
            computed_at=datetime.now(UTC),
        )
    )
    db.commit()
    candidates = evaluate_alert_candidates(db, tenant.id)
    assert any(item.rule_id == "critical_file" for item in candidates)


def test_unassigned_p1_rule_fires_from_jira_cache(db, tenant):
    from app.services.integration_telemetry import apply_jira_telemetry
    from app.services.jira_client import load_fixture_issues
    from tests.test_jira_telemetry import _seed as seed_jira

    seed_jira(db, tenant.id)
    apply_jira_telemetry(db, tenant.id, load_fixture_issues())
    candidates = evaluate_alert_candidates(db, tenant.id)
    assert any(item.rule_id == "unassigned_p1" for item in candidates)


def test_sync_and_acknowledge_alert(db, tenant):
    _seed_spof_tier1(db, tenant.id)
    with patch("app.services.era_alerts.has_github_sync", return_value=True), patch(
        "app.services.era_alerts.is_github_spof",
        return_value=True,
    ):
        created = sync_era_alerts(db, tenant, demo_mode=False)
    assert len(created) >= 1

    listed = list_era_alerts(db, tenant.id, unacknowledged=True)
    assert listed.unacknowledged_count >= 1
    alert_id = listed.alerts[0].id

    acknowledged = acknowledge_era_alert(db, tenant.id, alert_id, acknowledged_by="manager")
    assert acknowledged is not None
    assert acknowledged.acknowledged_at is not None

    after = list_era_alerts(db, tenant.id, unacknowledged=True)
    assert all(item.id != alert_id for item in after.alerts)


def test_review_cadence_overdue(db, tenant):
    db.add(
        EraTeamReview(
            tenant_id=tenant.id,
            reviewed_at=datetime.now(UTC) - timedelta(days=47),
            reviewer_user_id="manager",
            notes="Prior review",
            snapshot_avg_risk=55.0,
            delta_since_last=None,
        )
    )
    db.commit()
    cadence = get_review_cadence(db, tenant.id)
    assert cadence.review_overdue is True
    assert cadence.days_since_last_review == 47


def test_record_review_clears_overdue(db, tenant):
    db.add(
        EraTeamReview(
            tenant_id=tenant.id,
            reviewed_at=datetime.now(UTC) - timedelta(days=47),
            reviewer_user_id="manager",
            notes="Prior review",
            snapshot_avg_risk=55.0,
            delta_since_last=None,
        )
    )
    db.commit()
    review = record_era_review(
        db,
        tenant,
        EraTeamReviewCreateRequest(
            notes="Monthly review",
            reviewer_user_id="manager",
        ),
    )
    assert review.notes == "Monthly review"
    cadence = get_review_cadence(db, tenant.id)
    assert cadence.review_overdue is False
    assert cadence.days_since_last_review == 0


def test_alerts_api_routes_exist(client):
    settings = client.get("/api/analytics/era/settings")
    assert settings.status_code == 200
    cadence = client.get("/api/analytics/era/review-cadence")
    assert cadence.status_code == 200


def test_slack_webhook_skipped_in_demo_mode(db, tenant):
    from app.services.era_settings_store import save_era_settings

    save_era_settings(
        db,
        tenant.id,
        {
            "slack_webhook_enabled": True,
            "slack_webhook_url": "https://hooks.slack.com/services/test",
        },
    )
    _seed_spof_tier1(db, tenant.id)
    with patch("app.services.era_alerts.has_github_sync", return_value=True), patch(
        "app.services.era_alerts.is_github_spof",
        return_value=True,
    ), patch("app.services.era_alerts._post_slack_webhook") as webhook_mock:
        sync_era_alerts(db, tenant, demo_mode=True)
    webhook_mock.assert_not_called()
