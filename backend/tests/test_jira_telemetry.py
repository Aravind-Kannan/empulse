"""Jira telemetry tests (ERA Step 05)."""

from __future__ import annotations

import uuid

import pytest

from app.models.operational import Assignment, Component, Employee, EmployeeIdentity
from app.schemas.integrations import JiraConfigRequest
from app.services.jira_client import load_fixture_issues
from app.services.jira_evidence import build_jira_evidence_items
from app.services.integration_config_store import save_jira_config
from app.services.integration_telemetry import (
    apply_jira_telemetry,
    get_jira_backlog_boost,
    get_jira_employee_signals,
    get_jira_open_tasks,
    has_jira_sync,
    reset_telemetry_for_tests,
)
from app.services.era.signals_builder import build_signals_for_employee

from tests.conftest import add_employee


@pytest.fixture(autouse=True)
def _reset():
    reset_telemetry_for_tests()
    yield
    reset_telemetry_for_tests()


def _seed(db, tenant_id: uuid.UUID):
    for employee_id, jira_id, email in (
        ("emp-eng-001", "jira-ben", "ben@acme.com"),
        ("emp-eng-002", "jira-cara", "cara@acme.com"),
        ("emp-eng-003", "jira-diego", "diego@acme.com"),
    ):
        add_employee(db, tenant_id, employee_id=employee_id, name=employee_id, email=email)
        db.add(
            EmployeeIdentity(
                tenant_id=tenant_id,
                employee_id=employee_id,
                provider="jira",
                provider_username_or_id=jira_id,
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
    db.add(
        Assignment(
            tenant_id=tenant_id,
            employee_id="emp-eng-001",
            component_id="comp-payments",
            codebase_share_pct=70.0,
        )
    )
    db.add(
        Assignment(
            tenant_id=tenant_id,
            employee_id="emp-eng-002",
            component_id="comp-auth",
            codebase_share_pct=80.0,
        )
    )
    db.commit()


def test_apply_jira_telemetry_unassigned_p1_boost(db, tenant):
    _seed(db, tenant.id)
    issues = load_fixture_issues()
    apply_jira_telemetry(db, tenant.id, issues)
    assert has_jira_sync()
    boost = get_jira_backlog_boost("emp-eng-001")
    assert boost == 2


def test_apply_jira_telemetry_open_tasks_for_assignee(db, tenant):
    _seed(db, tenant.id)
    issues = load_fixture_issues()
    apply_jira_telemetry(db, tenant.id, issues)
    ben_tasks = get_jira_open_tasks("emp-eng-001")
    assert ben_tasks == 2


def test_component_counts_updated_from_jira(db, tenant):
    _seed(db, tenant.id)
    issues = load_fixture_issues()
    apply_jira_telemetry(db, tenant.id, issues)
    payments = (
        db.query(Component)
        .filter(Component.id == "comp-payments", Component.tenant_id == tenant.id)
        .one()
    )
    assert payments.open_tasks_count >= 1
    assert payments.unresolved_incidents >= 1


def test_jira_evidence_includes_browse_url(db, tenant):
    _seed(db, tenant.id)
    issues = load_fixture_issues()
    apply_jira_telemetry(db, tenant.id, issues)
    items = build_jira_evidence_items(
        "emp-eng-001",
        "Ben",
        jira_connected=True,
    )
    assert items
    assert items[0]["sources"][0]["url"].startswith("https://")
    assert "browse/" in items[0]["sources"][0]["url"]


def test_signals_use_jira_open_tasks(db, tenant):
    _seed(db, tenant.id)
    employee = db.query(Employee).filter_by(id="emp-eng-001").one()
    issues = load_fixture_issues()
    apply_jira_telemetry(db, tenant.id, issues)
    signals = build_signals_for_employee(
        employee,
        all_employees=[employee],
        total_components=2,
        codebase_share_pct=50.0,
        jira_backlog_boost=get_jira_backlog_boost("emp-eng-001"),
        jira_connected=True,
    )
    assert signals.open_tasks == 2
    assert signals.jira_backlog_boost == 2
    assert signals.sole_epic_owner_count == 1


def test_fixture_loader_maps_issue_urls(db, tenant):
    issues = load_fixture_issues("https://acme.atlassian.net")
    eng201 = next(item for item in issues if item.issue_key == "ENG-201")
    assert eng201.issue_url == "https://acme.atlassian.net/browse/ENG-201"


def test_jira_sync_via_integration_config(db, tenant):
    _seed(db, tenant.id)
    save_jira_config(
        db,
        tenant.id,
        JiraConfigRequest(
            site_url="https://acme.atlassian.net",
            project_keys="ENG,OPS",
            api_token="test-token",
        ),
    )
    from app.services.integration_sync import fetch_and_map_jira_issues

    components = {
        row.id: row
        for row in db.query(Component).filter(Component.tenant_id == tenant.id).all()
    }
    config = JiraConfigRequest(
        site_url="https://acme.atlassian.net",
        project_keys="ENG,OPS",
        api_token="test-token",
    )
    issues = fetch_and_map_jira_issues(config, components, use_fixture=True)
    apply_jira_telemetry(db, tenant.id, issues)
    assert has_jira_sync()
    assert get_jira_employee_signals("emp-eng-001") is not None
