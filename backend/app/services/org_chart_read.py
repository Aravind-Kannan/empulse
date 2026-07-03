from sqlalchemy.orm import Session

from app.models.operational import Assignment, Component, Employee
from app.models.tenant import Tenant
from app.schemas.org import (
    AssignmentSchema,
    ComponentSchema,
    EmployeeSchema,
    OrgChartIngestRequest,
)


def load_org_chart(db: Session, tenant: Tenant) -> OrgChartIngestRequest:
    tenant_id = tenant.id
    employees = (
        db.query(Employee)
        .filter(Employee.tenant_id == tenant_id)
        .order_by(Employee.name)
        .all()
    )
    if not employees:
        return OrgChartIngestRequest(
            company=tenant.company_name,
            employees=[],
            components=[],
            assignments=[],
        )

    components = (
        db.query(Component)
        .filter(Component.tenant_id == tenant_id)
        .order_by(Component.name)
        .all()
    )
    assignments = (
        db.query(Assignment).filter(Assignment.tenant_id == tenant_id).all()
    )

    return OrgChartIngestRequest(
        company=tenant.company_name,
        employees=[
            EmployeeSchema(
                id=employee.id,
                name=employee.name,
                role=employee.role,
                email=employee.email,
                tenure_years=employee.tenure_years,
                manager_id=employee.manager_id,
                team_name=employee.team_name,
            )
            for employee in employees
        ],
        components=[
            ComponentSchema(
                id=component.id,
                name=component.name,
                description=component.description,
                tags=getattr(component, "tags", "") or "",
                criticality=getattr(component, "criticality", "tier2_core"),
                open_tasks_count=component.open_tasks_count,
                unresolved_incidents=component.unresolved_incidents,
            )
            for component in components
        ],
        assignments=[
            AssignmentSchema(
                employee_id=assignment.employee_id,
                component_id=assignment.component_id,
                codebase_share_pct=assignment.codebase_share_pct,
            )
            for assignment in assignments
        ],
    )
