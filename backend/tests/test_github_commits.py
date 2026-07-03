"""Direct branch commit touch tests for KRA DOA / file risk."""

from __future__ import annotations

import uuid

import pytest

from app.models.operational import Component, EmployeeIdentity
from app.services.github_client import load_fixture_commits
from app.services.github_file_risk import compute_file_risk_from_activities
from app.services.github_touch import build_file_touch_indexes, pr_merge_shas
from app.services.github_types import GitHubCommitActivity, GitHubFileChange, GitHubPullRequestActivity
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


def _commit(path: str, sha: str, *, committed_at: str) -> GitHubCommitActivity:
    return GitHubCommitActivity(
        commit_sha=sha,
        branch="main",
        author_provider_user_id="gh-benrivera",
        author_login="benrivera",
        author_type="User",
        commit_url=f"https://github.com/acme/payments-service/commit/{sha}",
        committed_at=committed_at,
        files=[
            GitHubFileChange(
                path=path,
                loc_added=10,
                loc_removed=1,
                component_id="comp-payments",
            )
        ],
    )


def _pr(path: str, pr_number: int, *, merged_at: str, merge_sha: str) -> GitHubPullRequestActivity:
    return GitHubPullRequestActivity(
        pr_number=pr_number,
        commit_sha=merge_sha,
        merge_commit_sha=merge_sha,
        branch="main",
        author_provider_user_id="gh-benrivera",
        author_login="benrivera",
        author_type="User",
        pr_url=f"https://github.com/acme/payments-service/pull/{pr_number}",
        merged_at=merged_at,
        files=[
            GitHubFileChange(
                path=path,
                loc_added=10,
                loc_removed=1,
                component_id="comp-payments",
            )
        ],
    )


def test_commit_touches_included_in_file_risk(db, tenant):
    _seed(db, tenant.id)
    commits = [
        _commit("services/payments/checkout.py", "c1", committed_at="2026-06-20T11:00:00Z"),
        _commit("services/payments/checkout.py", "c2", committed_at="2026-06-21T11:00:00Z"),
        _commit("services/payments/checkout.py", "c3", committed_at="2026-06-22T11:00:00Z"),
    ]
    records = compute_file_risk_from_activities(db, tenant.id, [], commits)
    assert len(records) == 1
    assert records[0].churn_score == 3
    assert records[0].quadrant == "critical"


def test_pr_merge_commit_not_double_counted(db, tenant):
    _seed(db, tenant.id)
    prs = [
        _pr(
            "services/payments/checkout.py",
            100,
            merged_at="2026-06-15T10:00:00Z",
            merge_sha="merge-sha-100",
        )
    ]
    commits = [
        _commit(
            "services/payments/checkout.py",
            "merge-sha-100",
            committed_at="2026-06-15T10:00:00Z",
        ),
        _commit(
            "services/payments/checkout.py",
            "direct-only",
            committed_at="2026-06-16T10:00:00Z",
        ),
    ]
    events, _ = build_file_touch_indexes(db, tenant.id, prs, commits)
    key = ("comp-payments", "services/payments/checkout.py")
    churn_keys = {event.churn_key for event in events[key]}
    assert churn_keys == {"merge-sha-100", "direct-only"}


def test_pr_merge_shas_collects_merge_and_head():
    prs = [
        GitHubPullRequestActivity(
            pr_number=1,
            commit_sha="head-sha",
            merge_commit_sha="merge-sha",
            branch="main",
            author_provider_user_id="gh-a",
            author_login="a",
            author_type="User",
            pr_url="https://example.com/1",
            merged_at="2026-06-01T00:00:00Z",
            files=[],
        )
    ]
    assert pr_merge_shas(prs) == {"merge-sha", "head-sha"}


def test_apply_github_telemetry_with_fixture_commits(db, tenant):
    _seed(db, tenant.id)
    commits = load_fixture_commits()
    for commit in commits:
        for file_change in commit.files:
            file_change.component_id = "comp-payments"

    ownership = apply_github_telemetry(db, tenant.id, [], commit_activities=commits)
    assert "comp-payments" in ownership
    assert ownership["comp-payments"]["emp-eng-001"] > 0
