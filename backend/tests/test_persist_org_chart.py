"""Org chart persistence with identity-mapping foreign keys."""

from __future__ import annotations

import uuid

from app.models.operational import Component, Employee, EmployeeIdentity
from app.schemas.org import (
    AssignmentSchema,
    ComponentSchema,
    EmployeeSchema,
    OrgChartIngestRequest,
)
from app.services.cognee_ingest import persist_org_chart
from app.services.employee_ids import scope_employee_id


def _payload(
  employees: list[EmployeeSchema],
  *,
  components: list[ComponentSchema] | None = None,
  assignments: list[AssignmentSchema] | None = None,
) -> OrgChartIngestRequest:
    return OrgChartIngestRequest(
        company="Test Co",
        employees=employees,
        components=components or [],
        assignments=assignments or [],
    )


def test_persist_org_chart_removes_employee_with_identities(db, tenant):
    keep = EmployeeSchema(
        id="emp-keep",
        name="Keep Me",
        role="Engineer",
        email="keep@example.com",
        tenure_years=2.0,
    )
    remove = EmployeeSchema(
        id="emp-remove",
        name="Remove Me",
        role="Engineer",
        email="remove@example.com",
        tenure_years=1.0,
    )
    persist_org_chart(db, _payload([keep, remove]), tenant.id)

    keep_id = scope_employee_id("emp-keep", tenant.id)
    remove_id = scope_employee_id("emp-remove", tenant.id)

    db.add(
        EmployeeIdentity(
            tenant_id=tenant.id,
            employee_id=remove_id,
            provider="slack",
            provider_username_or_id="U123",
            confidence="confirmed",
        )
    )
    db.add(
        EmployeeIdentity(
            tenant_id=tenant.id,
            employee_id=keep_id,
            provider="github",
            provider_username_or_id="keep-user",
            confidence="confirmed",
        )
    )
    db.commit()

    persist_org_chart(db, _payload([keep]), tenant.id)

    remaining = db.query(Employee).filter(Employee.tenant_id == tenant.id).all()
    assert {employee.id for employee in remaining} == {keep_id}

    identities = db.query(EmployeeIdentity).filter(
        EmployeeIdentity.tenant_id == tenant.id
    ).all()
    assert len(identities) == 1
    assert identities[0].employee_id == keep_id
    assert identities[0].provider == "github"


def test_persist_org_chart_upserts_existing_employee_and_preserves_identities(
    db, tenant
):
    employee = EmployeeSchema(
        id="emp-ramdeprasad",
        name="Ramprasad R",
        role="Engineer",
        email="ram@example.com",
        tenure_years=3.0,
        manager_id=None,
    )
    persist_org_chart(db, _payload([employee]), tenant.id)

    employee_id = scope_employee_id("emp-ramdeprasad", tenant.id)
    db.add(
        EmployeeIdentity(
            tenant_id=tenant.id,
            employee_id=employee_id,
            provider="jira",
            provider_username_or_id="jira-123",
            confidence="confirmed",
        )
    )
    db.commit()

    updated = employee.model_copy(
        update={
            "name": "Ramprasad Ravi",
            "role": "Staff Engineer",
            "manager_id": None,
        }
    )
    persist_org_chart(db, _payload([updated]), tenant.id)

    row = db.get(Employee, employee_id)
    assert row is not None
    assert row.name == "Ramprasad Ravi"
    assert row.role == "Staff Engineer"

    identity = (
        db.query(EmployeeIdentity)
        .filter(
            EmployeeIdentity.tenant_id == tenant.id,
            EmployeeIdentity.employee_id == employee_id,
        )
        .one()
    )
    assert identity.provider_username_or_id == "jira-123"


def test_persist_org_chart_replaces_assignments(db, tenant):
    component = ComponentSchema(
        id="comp-auth",
        name="Auth Service",
        description="Identity",
    )
    employee = EmployeeSchema(
        id="emp-a",
        name="Alex",
        role="Engineer",
        email="alex@example.com",
        tenure_years=1.0,
    )
    persist_org_chart(
        db,
        _payload(
            [employee],
            components=[component],
            assignments=[
                AssignmentSchema(
                    employee_id="emp-a",
                    component_id="comp-auth",
                    codebase_share_pct=40.0,
                )
            ],
        ),
        tenant.id,
    )

    persist_org_chart(
        db,
        _payload([employee], components=[component], assignments=[]),
        tenant.id,
    )

    from app.models.operational import Assignment

    assignments = db.query(Assignment).filter(Assignment.tenant_id == tenant.id).all()
    assert assignments == []
