"""ERA API v2 contract tests (Step 03)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.era_analytics import get_era_metrics, get_era_employee_detail

from tests.conftest import add_employee


@pytest.fixture()
def client():
    return TestClient(app)


def test_get_era_metrics_returns_team_summary_envelope(db, tenant):
    with patch("app.services.era_analytics.get_settings") as mock_settings:
        mock_settings.return_value.era_v2_scoring = True
        response = get_era_metrics(db, tenant)

    assert response.computed_at is not None
    assert response.team_summary is not None
    assert response.team_summary.avg_risk_score >= 0
    assert isinstance(response.warnings, list)
    assert isinstance(response.sync_freshness, dict)
    assert isinstance(response.unmapped_activity, list)


def test_demo_mode_when_acme_fallback(db, tenant):
    response = get_era_metrics(db, tenant)
    assert response.demo_mode is True
    assert "demo_data" in response.warnings
    assert len(response.employees) > 0


def test_v2_employee_has_dimensions_and_evidence(db, tenant):
    with patch("app.services.era_analytics.get_settings") as mock_settings:
        mock_settings.return_value.era_v2_scoring = True
        response = get_era_metrics(db, tenant)

    assert response.demo_mode is True
    sample = next(item for item in response.employees if item.dimensions)
    assert sample.dimensions is not None
    assert sample.identity_coverage
    assert sample.data_completeness_pct > 0
    assert len(sample.evidence) <= 5


def test_employee_detail_endpoint_returns_full_evidence(client, db, tenant):
    with patch("app.services.era_analytics.get_settings") as mock_settings:
        mock_settings.return_value.era_v2_scoring = True
        list_response = get_era_metrics(db, tenant)
    employee_id = list_response.employees[0].employee_id

    http_response = client.get(f"/api/analytics/era/{employee_id}")
    assert http_response.status_code == 200
    payload = http_response.json()
    assert payload["employee"]["employee_id"] == employee_id
    assert "evidence" in payload
    assert payload["evidence_total_count"] >= len(payload["evidence"])


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
    with patch("app.services.era_analytics.get_settings") as mock_settings:
        mock_settings.return_value.era_v2_scoring = True
        response = get_era_metrics(db, tenant)

    assert response.demo_mode is False
    assert len(response.employees) == 1
    assert response.employees[0].identity_coverage
    assert response.employees[0].dimensions is not None
