from typing import Any

from pydantic import SkipValidation
from sqlalchemy.orm import Session

from cognee.infrastructure.engine import DataPoint
from cognee.infrastructure.engine.models.Edge import Edge
from cognee.tasks.storage import add_data_points

from app.config import get_settings, run_cognee_add_and_cognify
from app.models.operational import Assignment, Component, Employee
from app.schemas.org import OrgChartIngestRequest


class GraphEmployee(DataPoint):
    external_id: str
    name: str
    role: str
    email: str
    tenure_years: float
    reportsTo: SkipValidation[Any] = None
    manages: SkipValidation[Any] = None
    ownsComponent: SkipValidation[Any] = None
    metadata: dict = {"index_fields": ["name", "role"]}


class GraphComponent(DataPoint):
    external_id: str
    name: str
    description: str
    open_tasks_count: int
    unresolved_incidents: int
    metadata: dict = {"index_fields": ["name", "description"]}


def persist_org_chart(db: Session, payload: OrgChartIngestRequest) -> None:
    db.query(Assignment).delete()
    db.flush()
    db.query(Employee).update({Employee.manager_id: None}, synchronize_session=False)
    db.query(Employee).delete()
    db.query(Component).delete()
    db.flush()

    for component in payload.components:
        db.add(
            Component(
                id=component.id,
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
                name=employee.name,
                role=employee.role,
                email=employee.email,
                tenure_years=employee.tenure_years,
                manager_id=employee.manager_id,
            )
        )

    for assignment in payload.assignments:
        db.add(
            Assignment(
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
        lines.append(
            f"{employee.name} ({employee.role}, {employee.email}, "
            f"{employee.tenure_years} years) reports to {manager or 'no one'}."
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
            f"{employee.name} owns {assignment.codebase_share_pct}% of {component.name}."
        )
    return "\n".join(lines)


async def ingest_org_chart_to_cognee(payload: OrgChartIngestRequest) -> dict[str, int | str]:
    settings = get_settings()
    employee_nodes: dict[str, GraphEmployee] = {}
    component_nodes: dict[str, GraphComponent] = {}

    for employee in payload.employees:
        employee_nodes[employee.id] = GraphEmployee(
            external_id=employee.id,
            name=employee.name,
            role=employee.role,
            email=employee.email,
            tenure_years=employee.tenure_years,
        )

    for component in payload.components:
        component_nodes[component.id] = GraphComponent(
            external_id=component.id,
            name=component.name,
            description=component.description,
            open_tasks_count=component.open_tasks_count,
            unresolved_incidents=component.unresolved_incidents,
        )

    edge_count = 0

    for employee in payload.employees:
        node = employee_nodes[employee.id]
        if employee.manager_id and employee.manager_id in employee_nodes:
            manager_node = employee_nodes[employee.manager_id]
            node.reportsTo = (
                Edge(relationship_type="reportsTo"),
                manager_node,
            )
            edge_count += 1

    manager_ids = {
        employee.manager_id
        for employee in payload.employees
        if employee.manager_id is not None
    }
    for manager_id in manager_ids:
        if manager_id not in employee_nodes:
            continue
        manager_node = employee_nodes[manager_id]
        reports = [
            employee_nodes[report.id]
            for report in payload.employees
            if report.manager_id == manager_id
        ]
        if reports:
            manager_node.manages = (
                Edge(relationship_type="manages"),
                reports if len(reports) > 1 else reports[0],
            )
            edge_count += 1

    for assignment in payload.assignments:
        employee_node = employee_nodes.get(assignment.employee_id)
        component_node = component_nodes.get(assignment.component_id)
        if not employee_node or not component_node:
            continue
        employee_node.ownsComponent = (
            Edge(
                relationship_type="ownsComponent",
                properties={"codebase_share_pct": assignment.codebase_share_pct},
            ),
            component_node,
        )
        edge_count += 1

    data_points = list(employee_nodes.values()) + list(component_nodes.values())
    await add_data_points(data_points)

    await run_cognee_add_and_cognify(
        _build_org_narrative(payload),
        dataset_name=settings.cognee_dataset_name,
        custom_prompt=(
            "Extract organizational relationships including reporting lines, "
            "management scope, and component ownership for an engineering team."
        ),
    )

    return {
        "cognee_dataset": settings.cognee_dataset_name,
        "graph_nodes_created": len(data_points),
        "graph_edges_created": edge_count,
    }
