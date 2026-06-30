from typing import Any
import uuid

from pydantic import SkipValidation
from sqlalchemy.orm import Session

from cognee.infrastructure.engine import DataPoint
from cognee.infrastructure.engine.models.Edge import Edge
from cognee.tasks.storage import add_data_points

from app.models.operational import Assignment, Component, Employee
from app.schemas.org import OrgChartIngestRequest
from app.services.role_utils import is_leadership_role
from app.services.tenant_cognee import tenant_add_and_cognify
from app.tenancy import tenant_dataset_name


class GraphEmployee(DataPoint):
    external_id: str
    name: str
    role: str
    email: str
    tenure_years: float
    team_name: str | None = None
    reportsTo: SkipValidation[Any] = None
    directReportOf: SkipValidation[Any] = None
    manages: SkipValidation[Any] = None
    ownsComponent: SkipValidation[Any] = None
    metadata: dict = {"index_fields": ["name", "role", "team_name"]}


class GraphComponent(DataPoint):
    external_id: str
    name: str
    description: str
    open_tasks_count: int
    unresolved_incidents: int
    metadata: dict = {"index_fields": ["name", "description"]}


def persist_org_chart(
    db: Session,
    payload: OrgChartIngestRequest,
    tenant_id: uuid.UUID,
) -> None:
    db.query(Assignment).filter(Assignment.tenant_id == tenant_id).delete()
    db.flush()
    db.query(Employee).filter(Employee.tenant_id == tenant_id).update(
        {Employee.manager_id: None}, synchronize_session=False
    )
    db.query(Employee).filter(Employee.tenant_id == tenant_id).delete()
    db.query(Component).filter(Component.tenant_id == tenant_id).delete()
    db.flush()

    for component in payload.components:
        db.add(
            Component(
                id=component.id,
                tenant_id=tenant_id,
                name=component.name,
                description=component.description,
                open_tasks_count=component.open_tasks_count,
                unresolved_incidents=component.unresolved_incidents,
            )
        )

    for employee in payload.employees:
        db.add(
            Employee(
                id=employee.id,
                tenant_id=tenant_id,
                name=employee.name,
                role=employee.role,
                email=employee.email,
                tenure_years=employee.tenure_years,
                manager_id=employee.manager_id,
                team_name=employee.team_name,
            )
        )

    for assignment in payload.assignments:
        db.add(
            Assignment(
                tenant_id=tenant_id,
                employee_id=assignment.employee_id,
                component_id=assignment.component_id,
                codebase_share_pct=assignment.codebase_share_pct,
            )
        )

    db.commit()


def _build_org_narrative(payload: OrgChartIngestRequest) -> str:
    lines = [f"Organization: {payload.company}"]
    for employee in payload.employees:
        manager = next(
            (e.name for e in payload.employees if e.id == employee.manager_id),
            None,
        )
        team = f", team={employee.team_name}" if employee.team_name else ""
        lines.append(
            f"{employee.name} ({employee.role}, {employee.email}, "
            f"{employee.tenure_years} years{team}) reports to {manager or 'no one'}."
        )
    for component in payload.components:
        lines.append(
            f"Component {component.name}: {component.description} "
            f"({component.open_tasks_count} open tasks, "
            f"{component.unresolved_incidents} unresolved incidents)."
        )
    for assignment in payload.assignments:
        employee = next(e for e in payload.employees if e.id == assignment.employee_id)
        component = next(c for c in payload.components if c.id == assignment.component_id)
        lines.append(
            f"{employee.name} owns component {component.name} in the engineering graph."
        )
    return "\n".join(lines)


def assign_org_graph_edges(
    payload: OrgChartIngestRequest,
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
) -> int:
    edge_count = 0
    reports_by_manager: dict[str, list[GraphEmployee]] = {}

    for employee in payload.employees:
        node = employee_nodes.get(employee.id)
        if not node:
            continue

        if employee.manager_id and employee.manager_id in employee_nodes:
            manager_node = employee_nodes[employee.manager_id]
            node.reportsTo = (
                Edge(relationship_type="reportsTo"),
                manager_node,
            )
            node.directReportOf = (
                Edge(relationship_type="directReportOf"),
                manager_node,
            )
            edge_count += 2
            reports_by_manager.setdefault(employee.manager_id, []).append(node)

    for manager_id, report_nodes in reports_by_manager.items():
        manager_node = employee_nodes.get(manager_id)
        if not manager_node:
            continue

        manager = next(
            (employee for employee in payload.employees if employee.id == manager_id),
            None,
        )
        if not manager:
            continue

        if is_leadership_role(manager.role) or report_nodes:
            manager_node.manages = (
                Edge(relationship_type="manages"),
                report_nodes if len(report_nodes) > 1 else report_nodes[0],
            )
            edge_count += 1

    assignments_by_employee: dict[str, list] = {}
    for assignment in payload.assignments:
        assignments_by_employee.setdefault(assignment.employee_id, []).append(assignment)

    for employee_id, employee_assignments in assignments_by_employee.items():
        employee_node = employee_nodes.get(employee_id)
        if not employee_node:
            continue

        owned_components = [
            component_nodes[assignment.component_id]
            for assignment in employee_assignments
            if assignment.component_id in component_nodes
        ]
        if not owned_components:
            continue

        employee_node.ownsComponent = (
            Edge(relationship_type="ownsComponent"),
            owned_components if len(owned_components) > 1 else owned_components[0],
        )
        edge_count += 1

    return edge_count


async def ingest_org_chart_to_cognee(
    payload: OrgChartIngestRequest,
    *,
    tenant_id: uuid.UUID,
    custom_prompt: str | None = None,
    supplemental_narrative: str | None = None,
) -> dict[str, int | str]:
    employee_nodes: dict[str, GraphEmployee] = {}
    component_nodes: dict[str, GraphComponent] = {}

    for employee in payload.employees:
        employee_nodes[employee.id] = GraphEmployee(
            external_id=employee.id,
            name=employee.name,
            role=employee.role,
            email=employee.email,
            tenure_years=employee.tenure_years,
            team_name=employee.team_name,
        )

    for component in payload.components:
        component_nodes[component.id] = GraphComponent(
            external_id=component.id,
            name=component.name,
            description=component.description,
            open_tasks_count=component.open_tasks_count,
            unresolved_incidents=component.unresolved_incidents,
        )

    edge_count = assign_org_graph_edges(payload, employee_nodes, component_nodes)

    data_points = list(employee_nodes.values()) + list(component_nodes.values())
    await add_data_points(data_points)

    dataset = tenant_dataset_name(tenant_id)
    narrative = _build_org_narrative(payload)
    if supplemental_narrative:
        narrative = f"{supplemental_narrative}\n\n{narrative}"

    await tenant_add_and_cognify(
        narrative,
        tenant_id,
        custom_prompt=custom_prompt
        or (
            "Extract organizational relationships including reporting lines, "
            "management scope, and component ownership for an engineering team."
        ),
    )

    return {
        "cognee_dataset": dataset,
        "graph_nodes_created": len(data_points),
        "graph_edges_created": edge_count,
    }
