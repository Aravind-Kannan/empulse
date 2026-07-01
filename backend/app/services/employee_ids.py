"""Tenant-scoped employee and component IDs for multi-tenant org charts."""

from __future__ import annotations

import re
import uuid

from app.schemas.org import OrgChartIngestRequest


def tenant_prefix(tenant_id: uuid.UUID) -> str:
    return str(tenant_id).replace("-", "")[:8]


def employee_id_from_email(email: str, tenant_id: uuid.UUID) -> str:
    local = email.split("@")[0].lower()
    slug = re.sub(r"[^a-z0-9]+", "-", local).strip("-") or "member"
    return f"emp-{tenant_prefix(tenant_id)}-{slug}"


def scope_employee_id(raw_id: str, tenant_id: uuid.UUID) -> str:
    prefix = tenant_prefix(tenant_id)
    scoped_prefix = f"emp-{prefix}-"
    if raw_id.startswith(scoped_prefix):
        return raw_id
    local = raw_id.removeprefix("emp-")
    return f"{scoped_prefix}{local}"


def scope_component_id(raw_id: str, tenant_id: uuid.UUID) -> str:
    prefix = tenant_prefix(tenant_id)
    scoped_prefix = f"comp-{prefix}-"
    if raw_id.startswith(scoped_prefix):
        return raw_id
    local = raw_id.removeprefix("comp-")
    return f"{scoped_prefix}{local}"


def scope_org_chart_to_tenant(
    payload: OrgChartIngestRequest,
    tenant_id: uuid.UUID,
) -> OrgChartIngestRequest:
    """
    Prefix employee/component IDs with the tenant so they remain unique
    across workspaces (employees.id is a global primary key).
    """
    employee_id_map = {
        employee.id: scope_employee_id(employee.id, tenant_id)
        for employee in payload.employees
    }
    component_id_map = {
        component.id: scope_component_id(component.id, tenant_id)
        for component in payload.components
    }

    employees = [
        employee.model_copy(
            update={
                "id": employee_id_map[employee.id],
                "manager_id": employee_id_map.get(employee.manager_id)
                if employee.manager_id
                else None,
            }
        )
        for employee in payload.employees
    ]
    components = [
        component.model_copy(update={"id": component_id_map[component.id]})
        for component in payload.components
    ]
    assignments = [
        assignment.model_copy(
            update={
                "employee_id": employee_id_map[assignment.employee_id],
                "component_id": component_id_map.get(
                    assignment.component_id,
                    scope_component_id(assignment.component_id, tenant_id),
                ),
            }
        )
        for assignment in payload.assignments
    ]

    return payload.model_copy(
        update={
            "employees": employees,
            "components": components,
            "assignments": assignments,
        }
    )
