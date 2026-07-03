"""KRA Metric 1 — critical SPOF count tests."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.operational import Assignment, Component
from app.services.integration_telemetry import reset_telemetry_for_tests
from app.services.kra_metrics import compute_critical_spof_count, invalidate_kra_summary_cache

from tests.conftest import add_employee


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_telemetry():
    reset_telemetry_for_tests()
    invalidate_kra_summary_cache()
    yield
    reset_telemetry_for_tests()
    invalidate_kra_summary_cache()


def _seed_component(
    db,
    tenant_id: uuid.UUID,
    *,
    component_id: str,
    name: str,
    criticality: str,
) -> None:
    db.add(
        Component(
            id=component_id,
            tenant_id=tenant_id,
            name=name,
            description="",
            criticality=criticality,
        )
    )
    db.commit()


def test_tier1_bus_factor_one_counted(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-owner",
        name="Owner",
        email="owner@acme.com",
    )
    _seed_component(
        db,
        tenant.id,
        component_id="comp-payments",
        name="Payment Gateway",
        criticality="tier1_revenue",
    )
    db.add(
        Assignment(
            tenant_id=tenant.id,
            employee_id="emp-owner",
            component_id="comp-payments",
            codebase_share_pct=90.0,
        )
    )
    db.commit()

    with patch("app.services.kra_metrics.has_github_sync", return_value=True), patch(
        "app.services.kra_metrics.get_all_bus_factors",
        return_value={"comp-payments": 1},
    ), patch(
        "app.services.kra_metrics.get_github_ownership",
        return_value={"comp-payments": {"emp-owner": 90.0}},
    ):
        result = compute_critical_spof_count(db, tenant.id)

    assert result.count == 1
    assert result.components[0].component_id == "comp-payments"
    assert result.components[0].github_verified is True


def test_tier1_bus_factor_three_two_owners_not_counted(db, tenant):
    for index, employee_id in enumerate(("emp-a", "emp-b"), start=1):
        add_employee(
            db,
            tenant.id,
            employee_id=employee_id,
            name=f"Engineer {index}",
            email=f"{employee_id}@acme.com",
        )
    _seed_component(
        db,
        tenant.id,
        component_id="comp-payments",
        name="Payment Gateway",
        criticality="tier1_revenue",
    )
    for employee_id in ("emp-a", "emp-b"):
        db.add(
            Assignment(
                tenant_id=tenant.id,
                employee_id=employee_id,
                component_id="comp-payments",
                codebase_share_pct=50.0,
            )
        )
    db.commit()

    with patch("app.services.kra_metrics.has_github_sync", return_value=True), patch(
        "app.services.kra_metrics.get_all_bus_factors",
        return_value={"comp-payments": 3},
    ), patch(
        "app.services.kra_metrics.get_github_ownership",
        return_value={
            "comp-payments": {"emp-a": 50.0, "emp-b": 50.0},
        },
    ):
        result = compute_critical_spof_count(db, tenant.id)

    assert result.count == 0


def test_tier3_bus_factor_one_not_counted(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-owner",
        name="Owner",
        email="owner@acme.com",
    )
    _seed_component(
        db,
        tenant.id,
        component_id="comp-support",
        name="Support Tool",
        criticality="tier3_support",
    )
    db.add(
        Assignment(
            tenant_id=tenant.id,
            employee_id="emp-owner",
            component_id="comp-support",
            codebase_share_pct=100.0,
        )
    )
    db.commit()

    with patch("app.services.kra_metrics.has_github_sync", return_value=True), patch(
        "app.services.kra_metrics.get_all_bus_factors",
        return_value={"comp-support": 1},
    ), patch(
        "app.services.kra_metrics.get_github_ownership",
        return_value={"comp-support": {"emp-owner": 100.0}},
    ):
        result = compute_critical_spof_count(db, tenant.id)

    assert result.count == 0


def test_no_github_assignment_only_path(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-owner",
        name="Owner",
        email="owner@acme.com",
    )
    _seed_component(
        db,
        tenant.id,
        component_id="comp-payments",
        name="Payment Gateway",
        criticality="tier1_revenue",
    )
    db.add(
        Assignment(
            tenant_id=tenant.id,
            employee_id="emp-owner",
            component_id="comp-payments",
            codebase_share_pct=100.0,
        )
    )
    db.commit()

    with patch("app.services.kra_metrics.has_github_sync", return_value=False):
        result = compute_critical_spof_count(db, tenant.id)

    assert result.count == 1
    assert result.components[0].github_verified is False
    assert result.data_completeness.github == "missing"
    assert result.data_completeness.is_partial is True


def test_summary_endpoint_returns_200_with_coverage(client):
    response = client.get("/api/analytics/kra/summary")
    assert response.status_code == 200
    payload = response.json()
    assert "critical_spof" in payload
    assert "count" in payload["critical_spof"]
    assert "components" in payload["critical_spof"]
    coverage = payload["critical_spof"]["data_completeness"]
    assert coverage["github"] in {"confirmed", "partial", "missing"}
    assert "is_partial" in coverage
