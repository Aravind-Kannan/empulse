"""Tests for tenant operational data wipe."""

from __future__ import annotations

from app.models.operational import Assignment, Component, Employee, IncidentRecord
from app.services.tenant_workspace_wipe import wipe_tenant_operational_data


def test_wipe_removes_employees_components_and_incidents(db, tenant):
    employee = Employee(
        id="emp-1",
        tenant_id=tenant.id,
        name="Alice",
        role="Engineer",
        email="alice@example.com",
        tenure_years=2.0,
    )
    component = Component(
        id="comp-1",
        tenant_id=tenant.id,
        name="Payments",
        description="",
    )
    assignment = Assignment(
        tenant_id=tenant.id,
        employee_id="emp-1",
        component_id="comp-1",
        codebase_share_pct=100.0,
    )
    incident = IncidentRecord(
        id="inc-1",
        tenant_id=tenant.id,
        title="Outage",
        status="open",
        system_scope="payments",
    )
    db.add_all([employee, component, assignment, incident])
    db.commit()

    result = wipe_tenant_operational_data(db, tenant.id)

    assert result["counts"]["employees"] == 1
    assert result["counts"]["components"] == 1
    assert result["counts"]["assignments"] == 1
    assert result["counts"]["incidents"] == 1
    assert result["total_rows_removed"] >= 4
    assert db.query(Employee).filter(Employee.tenant_id == tenant.id).count() == 0
    assert db.query(Component).filter(Component.tenant_id == tenant.id).count() == 0
    assert db.query(IncidentRecord).filter(IncidentRecord.tenant_id == tenant.id).count() == 0
