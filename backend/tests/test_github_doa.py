"""DOA ownership tests (ERA Step 14)."""

from __future__ import annotations

import uuid

import pytest

from app.models.operational import Component, DoaFileSnapshot, EmployeeIdentity
from app.schemas.kra import KraAnalyticsResponse
from app.services.github_client import load_fixture_activities
from app.services.github_doa import (
    DOA_AUTHOR_THRESHOLD,
    compute_bus_factor,
    compute_doa_for_file,
    compute_doa_from_activities,
    persist_doa_snapshots,
)
from app.services.github_touch import FileTouch
from app.services.github_evidence import build_github_evidence_items
from app.services.integration_telemetry import (
    apply_github_telemetry,
    get_all_bus_factors,
    has_doa_ownership,
    reset_telemetry_for_tests,
)
from app.services.kra_analytics import _build_graph
from app.services.era.signals_builder import build_signals_for_employee

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


def test_fritz_doa_first_author_scores_highest():
    touches = [
        FileTouch("emp-a", __import__("datetime").datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc)),
        FileTouch("emp-b", __import__("datetime").datetime(2026, 2, 1, tzinfo=__import__("datetime").timezone.utc)),
        FileTouch("emp-a", __import__("datetime").datetime(2026, 3, 1, tzinfo=__import__("datetime").timezone.utc)),
    ]
    scores = {row.employee_id: row for row in compute_doa_for_file(touches)}
    assert scores["emp-a"].doa_score >= scores["emp-b"].doa_score
    assert scores["emp-a"].is_author == (scores["emp-a"].doa_score >= DOA_AUTHOR_THRESHOLD)


def test_bus_factor_single_author_is_one():
    authoritative = {
        "a.py": ["emp-1"],
        "b.py": ["emp-1"],
    }
    assert compute_bus_factor(authoritative) == 1


def test_bus_factor_two_authors_cover_files():
    authoritative = {
        "a.py": ["emp-1"],
        "b.py": ["emp-2"],
    }
    assert compute_bus_factor(authoritative) == 2


def test_doa_snapshots_persisted(db, tenant):
    _seed(db, tenant.id)
    activities = load_fixture_activities()
    for activity in activities:
        for file_change in activity.files:
            if "payments" in file_change.path:
                file_change.component_id = "comp-payments"
            elif "auth" in file_change.path:
                file_change.component_id = "comp-auth"

    result = persist_doa_snapshots(db, tenant.id, activities)
    rows = (
        db.query(DoaFileSnapshot)
        .filter(DoaFileSnapshot.tenant_id == tenant.id)
        .all()
    )
    assert len(rows) == len(result.snapshots)
    assert len(rows) >= 2
    assert all(0.0 <= row.doa_score <= 1.0 for row in rows)


def test_apply_github_telemetry_uses_doa_ownership(db, tenant):
    _seed(db, tenant.id)
    activities = load_fixture_activities()
    for activity in activities:
        for file_change in activity.files:
            if "payments" in file_change.path:
                file_change.component_id = "comp-payments"
            elif "auth" in file_change.path:
                file_change.component_id = "comp-auth"

    apply_github_telemetry(db, tenant.id, activities)
    assert has_doa_ownership()
    assert get_all_bus_factors()


def test_evidence_mentions_doa(db, tenant):
    _seed(db, tenant.id)
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
    assert any("DOA" in item["title"] or "DOA" in item["description"] for item in items)


def test_kra_exposes_bus_factor(db, tenant):
    _seed(db, tenant.id)
    activities = load_fixture_activities()
    for activity in activities:
        for file_change in activity.files:
            file_change.component_id = "comp-payments"

    apply_github_telemetry(db, tenant.id, activities)

    class Emp:
        id = "emp-eng-001"
        name = "Ben"
        role = "Engineer"

    class Comp:
        id = "comp-payments"
        name = "Payments"
        description = ""

    class Asn:
        employee_id = "emp-eng-001"
        component_id = "comp-payments"
        codebase_share_pct = 50.0

    graph: KraAnalyticsResponse = _build_graph([Emp()], [Comp()], [Asn()])
    payments = next(node for node in graph.nodes if node.id == "comp-payments")
    assert payments.bus_factor is not None


def test_signals_use_doa_when_available(db, tenant):
    _seed(db, tenant.id)
    employee = db.query(__import__("app.models.operational", fromlist=["Employee"]).Employee).filter_by(id="emp-eng-001").one()
    activities = load_fixture_activities()
    for activity in activities:
        for file_change in activity.files:
            file_change.component_id = "comp-payments"

    apply_github_telemetry(db, tenant.id, activities)
    signals = build_signals_for_employee(
        employee,
        all_employees=[employee],
        total_components=1,
        codebase_share_pct=10.0,
        jira_backlog_boost=0,
        github_connected=True,
    )
    assert signals.uses_doa_ownership is True
    assert signals.max_github_ownership_pct > 0


def test_compute_doa_from_blame_snapshots(db, tenant):
    from app.services.github_code import BlameRange, GitHubCodeFileSnapshot
    from app.services.github_doa import (
        compute_doa_from_code_snapshots,
        dominant_blame_author_login,
        persist_doa_from_code_snapshots,
    )
    from app.services.integration_telemetry import apply_github_blame_telemetry

    _seed(db, tenant.id)
    db.add(
        Component(
            id="comp-api",
            tenant_id=tenant.id,
            name="API",
            description="",
        )
    )
    db.commit()

    snap = GitHubCodeFileSnapshot(
        repository_url="https://github.com/acme/repo",
        file_path="backend/app/main.py",
        ref="abc123",
        component_id="comp-api",
        blame_ranges=[
            BlameRange(1, 80, "benrivera", "sha1"),
            BlameRange(81, 100, "carapatel", "sha2"),
        ],
        primary_authors=["benrivera", "carapatel"],
    )

    assert dominant_blame_author_login(snap) == "benrivera"

    result = compute_doa_from_code_snapshots(db, tenant.id, [snap])
    assert "comp-api" in result.ownership
    assert result.ownership["comp-api"]["emp-eng-001"] > result.ownership["comp-api"]["emp-eng-002"]

    persist_doa_from_code_snapshots(db, tenant.id, [snap])
    rows = (
        db.query(DoaFileSnapshot)
        .filter(DoaFileSnapshot.tenant_id == tenant.id)
        .all()
    )
    assert len(rows) == 2

    ownership = apply_github_blame_telemetry(db, tenant.id, [snap])
    assert ownership["comp-api"]["emp-eng-001"] > 50


def test_persist_doa_from_code_snapshots_dedupes_same_path_across_refs(db, tenant):
    from app.services.github_code import BlameRange, GitHubCodeFileSnapshot
    from app.services.github_doa import persist_doa_from_code_snapshots

    _seed(db, tenant.id)
    db.add(
        Component(
            id="comp-api",
            tenant_id=tenant.id,
            name="API",
            description="",
        )
    )
    db.commit()

    shared_path = ".gitignore"
    snapshots = [
        GitHubCodeFileSnapshot(
            repository_url="https://github.com/acme/repo",
            file_path=shared_path,
            ref="main",
            component_id="comp-api",
            blame_ranges=[BlameRange(1, 10, "benrivera", "sha1")],
            primary_authors=["benrivera"],
        ),
        GitHubCodeFileSnapshot(
            repository_url="https://github.com/acme/repo",
            file_path=shared_path,
            ref="feature-branch",
            component_id="comp-api",
            blame_ranges=[BlameRange(1, 5, "benrivera", "sha2")],
            primary_authors=["benrivera"],
        ),
    ]

    persist_doa_from_code_snapshots(db, tenant.id, snapshots)
    rows = (
        db.query(DoaFileSnapshot)
        .filter(
            DoaFileSnapshot.tenant_id == tenant.id,
            DoaFileSnapshot.file_path == shared_path,
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].employee_id == "emp-eng-001"
    assert rows[0].doa_score == 1.0
