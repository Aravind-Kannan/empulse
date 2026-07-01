"""GitHub review network tests (ERA Step 15)."""

from __future__ import annotations

import uuid

import pytest
from app.services.era_analytics import get_era_review_network, get_era_team_risky_changes
from app.models.operational import Component, EmployeeIdentity
from app.schemas.integrations import GitHubConfigRequest
from app.services.github_client import load_fixture_activities
from app.services.github_path_mapper import apply_path_mapping
from app.services.github_reviews import build_review_network, compute_backup_review_score
from app.services.integration_config_store import save_github_config
from app.services.integration_telemetry import (
    apply_github_telemetry,
    get_github_backup_review_score,
    get_team_risky_changes,
    has_review_network,
    reset_telemetry_for_tests,
)

from tests.conftest import add_employee


@pytest.fixture(autouse=True)
def _reset():
    reset_telemetry_for_tests()
    yield
    reset_telemetry_for_tests()

def _seed(db, tenant_id: uuid.UUID):
    for employee_id, gh_id, email in (
        ("emp-eng-001", "gh-benrivera", "ben@acme.com"),
        ("emp-eng-002", "gh-carapatel", "cara@acme.com"),
    ):
        add_employee(db, tenant_id, employee_id=employee_id, name=employee_id, email=email)
        db.add(
            EmployeeIdentity(
                tenant_id=tenant_id,
                employee_id=employee_id,
                provider="github",
                provider_username_or_id=gh_id,
                confidence="confirmed",
            )
        )
    for component_id, name in (
        ("comp-payments", "Payment Gateway"),
        ("comp-auth", "Auth Service"),
    ):
        db.add(
            Component(
                id=component_id,
                tenant_id=tenant_id,
                name=name,
                description="",
            )
        )
    db.commit()


def _mapped_fixture_activities(db, tenant_id):
    config = GitHubConfigRequest(
        repository_url="https://github.com/acme/payments-service",
        personal_access_token="test-token",
        path_component_map={
            "services/payments": "comp-payments",
            "services/auth": "comp-auth",
        },
    )
    save_github_config(db, tenant_id, config)
    components = {
        row.id: row
        for row in db.query(Component).filter(Component.tenant_id == tenant_id).all()
    }
    activities = load_fixture_activities()
    mapped, _ = apply_path_mapping(
        activities,
        path_component_map=config.path_component_map,
        repo_name="payments-service",
        components_by_id=components,
        default_component_id=None,
    )
    return mapped


def test_backup_review_score_penalizes_sole_reviewer():
    score = compute_backup_review_score(
        unique_reviewers=1,
        review_concentration_pct=100.0,
        sole_reviewer_count=2,
        recent_pr_count=2,
    )
    assert score < 30.0


def test_review_network_builds_incoming_edges(db, tenant):
    _seed(db, tenant.id)
    activities = _mapped_fixture_activities(db, tenant.id)
    components = {
        row.id: row
        for row in db.query(Component).filter(Component.tenant_id == tenant.id).all()
    }
    result = build_review_network(db, tenant.id, activities, component_by_id=components)
    ben_metrics = result.metrics_by_employee.get("emp-eng-001")
    assert ben_metrics is not None
    assert ben_metrics.recent_pr_count >= 1
    assert ben_metrics.unique_reviewers_on_prs >= 1
    assert any(edge.author_employee_id == "emp-eng-001" for edge in result.edges)


def test_apply_github_telemetry_sets_backup_review_score(db, tenant):
    _seed(db, tenant.id)
    activities = _mapped_fixture_activities(db, tenant.id)
    apply_github_telemetry(db, tenant.id, activities)
    assert has_review_network()
    score = get_github_backup_review_score("emp-eng-001")
    assert score != 50.0


def test_risky_change_merged_without_review(db, tenant):
    _seed(db, tenant.id)
    activities = _mapped_fixture_activities(db, tenant.id)
    apply_github_telemetry(db, tenant.id, activities)
    risky = get_team_risky_changes()
    rules = {item.rule for item in risky}
    assert "merged_without_approval" in rules
    without_review = next(item for item in risky if item.rule == "merged_without_approval")
    assert without_review.pr_number == 510
    assert without_review.pr_url.startswith("https://github.com/")


def test_review_network_api(db, tenant):
    _seed(db, tenant.id)
    activities = _mapped_fixture_activities(db, tenant.id)
    apply_github_telemetry(db, tenant.id, activities)

    payload = get_era_review_network(db, tenant, "emp-eng-001")
    assert payload is not None
    assert payload.employee_id == "emp-eng-001"
    assert payload.metrics is not None
    assert len(payload.incoming_reviewers) >= 1


def test_team_risky_changes_api(db, tenant):
    _seed(db, tenant.id)
    activities = _mapped_fixture_activities(db, tenant.id)
    apply_github_telemetry(db, tenant.id, activities)

    payload = get_era_team_risky_changes(db, tenant, since="90d")
    assert payload.window_days == 90
    assert any(item.rule == "merged_without_approval" for item in payload.items)


def test_github_evidence_no_backup_reviewer_links(db, tenant):
    from app.services.github_evidence import build_github_evidence_items

    _seed(db, tenant.id)
    activities = _mapped_fixture_activities(db, tenant.id)
    apply_github_telemetry(db, tenant.id, activities)

    items = build_github_evidence_items(
        "emp-eng-001",
        "Ben",
        component_names={"comp-payments": "Payments"},
        github_connected=True,
    )
    backup_items = [item for item in items if "no-backup-review" in item["id"]]
    if backup_items:
        assert backup_items[0]["sources"][0]["url"] is not None
        assert "No backup reviewer" in backup_items[0]["title"]
