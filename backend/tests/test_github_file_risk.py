"""File risk matrix tests (ERA Step 13)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.models.operational import Component, EmployeeIdentity, FileRiskSnapshot
from app.services.github_file_risk import (
    build_file_risk_evidence_items,
    classify_quadrant,
    compute_file_risk_from_activities,
    get_kra_file_risk,
    persist_file_risk_snapshots,
    should_exclude_file_path,
)
from app.services.github_types import GitHubFileChange, GitHubPullRequestActivity
from app.services.integration_telemetry import apply_github_telemetry, reset_telemetry_for_tests

from tests.conftest import add_employee


@pytest.fixture(autouse=True)
def _reset():
    reset_telemetry_for_tests()
    yield
    reset_telemetry_for_tests()


def _seed(db, tenant_id: uuid.UUID):
    add_employee(
        db,
        tenant_id,
        employee_id="emp-eng-001",
        name="Ben Rivera",
        email="ben@acme.com",
    )
    db.add(
        EmployeeIdentity(
            tenant_id=tenant_id,
            employee_id="emp-eng-001",
            provider="github",
            provider_username_or_id="gh-benrivera",
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
    db.commit()


def _activity(
    pr_number: int,
    path: str,
    *,
    merged_at: str = "2026-06-15T10:00:00Z",
) -> GitHubPullRequestActivity:
    return GitHubPullRequestActivity(
        pr_number=pr_number,
        commit_sha=f"sha-{pr_number}",
        merge_commit_sha=f"sha-{pr_number}",
        branch="main",
        author_provider_user_id="gh-benrivera",
        author_login="benrivera",
        author_type="User",
        pr_url=f"https://github.com/acme/payments-service/pull/{pr_number}",
        merged_at=merged_at,
        files=[
            GitHubFileChange(
                path=path,
                loc_added=20,
                loc_removed=2,
                component_id="comp-payments",
            )
        ],
    )


def test_should_exclude_test_and_vendor_paths():
    assert should_exclude_file_path("services/payments/tests/handler.py") is True
    assert should_exclude_file_path("services/payments/__tests__/handler.ts") is True
    assert should_exclude_file_path("package-lock.json") is True
    assert should_exclude_file_path("vendor/foo/bar.go") is True
    assert should_exclude_file_path("services/payments/handler.ts") is False


def test_classify_quadrant():
    assert classify_quadrant(churn_score=4, contributor_count=1) == "critical"
    assert classify_quadrant(churn_score=1, contributor_count=1) == "stable_niche"
    assert classify_quadrant(churn_score=4, contributor_count=4) == "active_shared"
    assert classify_quadrant(churn_score=1, contributor_count=4) == "healthy"


def test_critical_file_persisted_and_surfaces_in_api(db, tenant):
    _seed(db, tenant.id)
    activities = [
        _activity(pr, "services/payments/handler.ts")
        for pr in (401, 402, 403, 404)
    ]
    activities.append(
        _activity(405, "services/payments/tests/handler.py"),
    )

    persist_file_risk_snapshots(
        db,
        tenant.id,
        activities,
        repo_path="acme/payments-service",
    )
    db.commit()

    rows = (
        db.query(FileRiskSnapshot)
        .filter(FileRiskSnapshot.tenant_id == tenant.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].quadrant == "critical"
    assert rows[0].file_path == "services/payments/handler.ts"
    assert rows[0].primary_owner_employee_id == "emp-eng-001"

    payload = get_kra_file_risk(db, tenant.id, component_id="comp-payments")
    assert payload["quadrant_counts"].get("critical") == 1
    assert payload["files"][0]["quadrant"] == "critical"
    assert len(payload["cross_training_priority"]) == 1


def test_file_risk_evidence_for_primary_owner(db, tenant):
    _seed(db, tenant.id)
    activities = [
        _activity(pr, "services/payments/handler.ts")
        for pr in (501, 502, 503)
    ]
    persist_file_risk_snapshots(db, tenant.id, activities, repo_path="acme/payments-service")
    db.commit()

    items = build_file_risk_evidence_items(
        db, tenant.id, "emp-eng-001", "Ben Rivera"
    )
    assert items
    assert items[0]["dimension"] == "knowledge"
    assert items[0]["severity"] == "high"
    assert "Critical file" in items[0]["title"]
    assert "handler.ts" in items[0]["title"]


def test_apply_github_telemetry_persists_file_risk(db, tenant):
    _seed(db, tenant.id)
    activities = [
        _activity(pr, "services/payments/handler.ts")
        for pr in (601, 602, 603)
    ]
    apply_github_telemetry(db, tenant.id, activities)
    db.commit()

    count = (
        db.query(FileRiskSnapshot)
        .filter(
            FileRiskSnapshot.tenant_id == tenant.id,
            FileRiskSnapshot.quadrant == "critical",
        )
        .count()
    )
    assert count == 1
