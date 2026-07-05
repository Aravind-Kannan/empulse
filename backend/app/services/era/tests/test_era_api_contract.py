"""ERA API v2 contract tests (Step 03)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.operational import Assignment, Component, EmployeeIdentity
from app.services.era_analytics import get_era_metrics, get_era_employee_detail
from app.tenancy import TENANT_HEADER

from tests.conftest import add_employee


@pytest.fixture()
def client(db):
    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _tenant_headers(tenant_id: uuid.UUID) -> dict[str, str]:
    return {TENANT_HEADER: str(tenant_id)}


def _seed_component(db, tenant_id, *, component_id: str, name: str) -> None:
    db.add(
        Component(
            id=component_id,
            tenant_id=tenant_id,
            name=name,
            description="",
            criticality="tier2_core",
        )
    )
    db.commit()


def test_get_era_metrics_returns_team_summary_envelope(db, tenant):
    response = get_era_metrics(db, tenant)

    assert response.computed_at is not None
    assert response.team_summary is not None
    assert response.team_summary.avg_risk_score >= 0
    assert isinstance(response.warnings, list)
    assert isinstance(response.sync_freshness, dict)
    assert isinstance(response.unmapped_activity, list)


def test_empty_org_returns_no_demo_employees(db, tenant):
    response = get_era_metrics(db, tenant)
    assert response.demo_mode is False
    assert response.employees == []
    assert "no_org_chart" in response.warnings


def test_v2_employee_has_dimensions_and_evidence(db, tenant):
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-era-001",
        name="ERA Engineer",
        email="era@acme.com",
    )
    _seed_component(db, tenant.id, component_id="comp-era", name="ERA Component")
    db.add(
        Assignment(
            tenant_id=tenant.id,
            employee_id=employee.id,
            component_id="comp-era",
            codebase_share_pct=80.0,
        )
    )
    db.add(
        EmployeeIdentity(
            tenant_id=tenant.id,
            employee_id=employee.id,
            provider="github",
            provider_username_or_id="era-engineer",
            provider_display_label="era-engineer",
            confidence="confirmed",
        )
    )
    db.commit()

    response = get_era_metrics(db, tenant)

    assert response.demo_mode is False
    sample = next(item for item in response.employees if item.dimensions)
    assert sample.dimensions is not None
    assert sample.dimension_summaries
    assert "knowledge" in sample.dimension_summaries
    assert sample.dimension_summaries["knowledge"].headline
    assert sample.identity_coverage
    assert sample.data_completeness_pct > 0
    assert len(sample.evidence) <= 5


def test_employee_detail_endpoint_returns_full_evidence(client, db, tenant):
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-era-detail",
        name="Detail Engineer",
        email="detail@acme.com",
    )
    _seed_component(db, tenant.id, component_id="comp-detail", name="Detail Component")
    db.add(
        Assignment(
            tenant_id=tenant.id,
            employee_id=employee.id,
            component_id="comp-detail",
            codebase_share_pct=70.0,
        )
    )
    db.add(
        EmployeeIdentity(
            tenant_id=tenant.id,
            employee_id=employee.id,
            provider="github",
            provider_username_or_id="detail-engineer",
            provider_display_label="detail-engineer",
            confidence="confirmed",
        )
    )
    db.commit()

    http_response = client.get(
        f"/api/analytics/era/{employee.id}",
        headers=_tenant_headers(tenant.id),
    )
    assert http_response.status_code == 200
    payload = http_response.json()
    assert payload["employee"]["employee_id"] == employee.id
    assert "evidence" in payload
    assert payload["evidence_total_count"] >= len(payload["evidence"])
    assert payload["identity_mappings"]["github"]["level"] == "confirmed"
    assert payload["identity_mappings"]["github"]["display_label"] == "detail-engineer"


def test_employee_detail_not_found(client):
    response = client.get("/api/analytics/era/does-not-exist")
    assert response.status_code == 404


def test_list_endpoint_via_http(client):
    response = client.get("/api/analytics/era")
    assert response.status_code == 200
    payload = response.json()
    assert "team_summary" in payload
    assert "employees" in payload
    assert "computed_at" in payload


def test_v2_metrics_with_persisted_employees(db, tenant):
    """Regression: build_identity_coverage must not raise when DB has employees."""
    add_employee(
        db,
        tenant.id,
        employee_id="emp-persisted-001",
        name="Persisted Engineer",
        email="persisted@acme.com",
    )
    response = get_era_metrics(db, tenant)

    assert response.demo_mode is False
    assert len(response.employees) == 1
    assert response.employees[0].identity_coverage
    assert response.employees[0].dimensions is not None


def test_era_open_p1_issues_endpoint(db, tenant, client):
    from app.services.integration_telemetry import apply_jira_telemetry
    from app.services.jira_client import load_fixture_issues
    from app.services.era_analytics import get_era_open_p1_issues

    from tests.test_jira_telemetry import _seed

    _seed(db, tenant.id)
    apply_jira_telemetry(db, tenant.id, load_fixture_issues())

    service = get_era_open_p1_issues(db, tenant)
    response = client.get("/api/analytics/era/open-p1-issues")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] == service.total_count
    assert len(payload["issues"]) == service.total_count
    if service.total_count:
        issue = payload["issues"][0]
        assert "issue_key" in issue
        assert "priority" in issue
