"""GitHub telemetry tests (ERA Step 04)."""

from __future__ import annotations

import uuid

import pytest

from app.models.operational import Component, EmployeeIdentity, GitHubOwnershipSnapshot
from app.schemas.integrations import GitHubConfigRequest
from app.services.github_client import load_fixture_activities
from app.services.github_path_mapper import map_path_to_component
from app.services.github_evidence import build_github_evidence_items
from app.services.integration_config_store import save_github_config
from app.services.integration_telemetry import (
    apply_github_telemetry,
    get_github_ownership,
    has_github_sync,
    is_github_spof,
    reset_telemetry_for_tests,
)
from app.services.unmapped_activity import get_total_unmapped_count

from tests.conftest import add_employee


@pytest.fixture(autouse=True)
def _reset_telemetry():
    reset_telemetry_for_tests()
    yield
    reset_telemetry_for_tests()


def _seed_github_identities(db, tenant_id: uuid.UUID) -> None:
    mapping = {
        "emp-eng-001": "gh-benrivera",
        "emp-eng-002": "gh-carapatel",
    }
    for employee_id, gh_id in mapping.items():
        add_employee(
            db,
            tenant_id,
            employee_id=employee_id,
            name=employee_id,
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


def test_path_mapper_prefix_priority():
    components = {
        "comp-payments": Component(
            id="comp-payments",
            tenant_id=uuid.uuid4(),
            name="Payments",
            description="",
        ),
        "comp-auth": Component(
            id="comp-auth",
            tenant_id=uuid.uuid4(),
            name="Auth",
            description="",
        ),
    }
    mapped = map_path_to_component(
        "services/payments/checkout.py",
        path_component_map={"services/payments": "comp-payments"},
        repo_name="payments-service",
        components_by_id=components,
        components_by_name={},
        default_component_id=None,
    )
    assert mapped == "comp-payments"


def test_ownership_split_two_contributors(db, tenant):
    _seed_github_identities(db, tenant.id)
    activities = load_fixture_activities()
    for activity in activities:
        for file_change in activity.files:
            if "payments" in file_change.path:
                file_change.component_id = "comp-payments"
            elif "auth" in file_change.path:
                file_change.component_id = "comp-auth"

    ownership = apply_github_telemetry(db, tenant.id, activities)
    payments = ownership["comp-payments"]
    assert payments["emp-eng-001"] > payments.get("emp-eng-002", 0)
    assert abs(sum(payments.values()) - 100.0) < 0.2


def test_single_contributor_spof_flag(db, tenant):
    _seed_github_identities(db, tenant.id)
    activities = load_fixture_activities()
    solo = [activity for activity in activities if activity.pr_number == 491]
    for activity in solo:
        for file_change in activity.files:
            file_change.component_id = "comp-auth"

    apply_github_telemetry(db, tenant.id, solo)
    assert is_github_spof("comp-auth")


def test_unmapped_author_quarantined(db, tenant):
    _seed_github_identities(db, tenant.id)
    activities = load_fixture_activities()
    contractor = [activity for activity in activities if activity.pr_number == 510]
    for activity in contractor:
        for file_change in activity.files:
            file_change.component_id = "comp-payments"

    before = get_total_unmapped_count(db, tenant.id)
    apply_github_telemetry(db, tenant.id, contractor)
    after = get_total_unmapped_count(db, tenant.id)
    assert after > before
    ownership = get_github_ownership().get("comp-payments", {})
    assert "emp-eng-001" not in ownership or ownership.get("emp-eng-001", 0) < 100


def test_ownership_persisted_to_db(db, tenant):
    _seed_github_identities(db, tenant.id)
    activities = load_fixture_activities()
    for activity in activities:
        for file_change in activity.files:
            if "payments" in file_change.path:
                file_change.component_id = "comp-payments"

    apply_github_telemetry(db, tenant.id, activities)
    rows = (
        db.query(GitHubOwnershipSnapshot)
        .filter(GitHubOwnershipSnapshot.tenant_id == tenant.id)
        .all()
    )
    assert len(rows) >= 1
    assert has_github_sync()


def test_evidence_includes_real_pr_urls(db, tenant):
    _seed_github_identities(db, tenant.id)
    activities = load_fixture_activities()
    for activity in activities:
        for file_change in activity.files:
            if "payments" in file_change.path:
                file_change.component_id = "comp-payments"

    apply_github_telemetry(db, tenant.id, activities)
    items = build_github_evidence_items(
        "emp-eng-001",
        "Ben Rivera",
        component_names={"comp-payments": "Payment Gateway"},
        github_connected=True,
    )
    assert items
    assert any(
        item["sources"][0].get("url", "").startswith("https://github.com/")
        for item in items
    )


def test_fetch_fixture_activity_via_config(db, tenant):
    config = GitHubConfigRequest(
        repository_url="https://github.com/acme/payments-service",
        personal_access_token="",
    )
    save_github_config(db, tenant.id, config)
    activities, open_prs = __import__(
        "app.services.github_client", fromlist=["fetch_github_pull_request_activity"]
    ).fetch_github_pull_request_activity(config, use_fixture=True)
    assert len(activities) >= 2
    assert activities[0].pr_url.startswith("https://github.com/")
