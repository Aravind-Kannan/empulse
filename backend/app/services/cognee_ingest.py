from typing import Any
import uuid

from pydantic import SkipValidation
from sqlalchemy.orm import Session

from cognee.infrastructure.engine import DataPoint
from cognee.infrastructure.engine.models.Edge import Edge

from app.models.operational import (
    Assignment,
    Component,
    DoaFileSnapshot,
    Employee,
    EmployeeIdentity,
    EraAlert,
    EraDepartureOrphanBaseline,
    EraEvidenceMitigation,
    EraRiskSnapshot,
    FileRiskSnapshot,
    GitHubOwnershipSnapshot,
    NotionDocSnapshot,
    RoleHistory,
)
from app.schemas.org import OrgChartIngestRequest
from app.services.employee_ids import scope_org_chart_to_tenant
from app.services.role_utils import is_leadership_role
from app.ontology.relations import REL_OWNS, REL_REPORTS_TO
from app.ontology.spec import validate_relation
from app.services.tenant_cognee import tenant_add_and_cognify, tenant_add_data_points
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
    owns: SkipValidation[Any] = None
    metadata: dict = {"index_fields": ["name", "role", "team_name"]}


class GraphComponent(DataPoint):
    external_id: str
    name: str
    description: str
    open_tasks_count: int
    unresolved_incidents: int
    metadata: dict = {"index_fields": ["name", "description"]}


def _delete_employee_dependents(
    db: Session,
    tenant_id: uuid.UUID,
    employee_id: str,
) -> None:
    db.query(Assignment).filter(
        Assignment.tenant_id == tenant_id,
        Assignment.employee_id == employee_id,
    ).delete(synchronize_session=False)
    db.query(EmployeeIdentity).filter(
        EmployeeIdentity.tenant_id == tenant_id,
        EmployeeIdentity.employee_id == employee_id,
    ).delete(synchronize_session=False)
    db.query(RoleHistory).filter(
        RoleHistory.tenant_id == tenant_id,
        RoleHistory.employee_id == employee_id,
    ).delete(synchronize_session=False)
    db.query(GitHubOwnershipSnapshot).filter(
        GitHubOwnershipSnapshot.tenant_id == tenant_id,
        GitHubOwnershipSnapshot.employee_id == employee_id,
    ).delete(synchronize_session=False)
    db.query(DoaFileSnapshot).filter(
        DoaFileSnapshot.tenant_id == tenant_id,
        DoaFileSnapshot.employee_id == employee_id,
    ).delete(synchronize_session=False)
    db.query(FileRiskSnapshot).filter(
        FileRiskSnapshot.tenant_id == tenant_id,
        FileRiskSnapshot.primary_owner_employee_id == employee_id,
    ).update(
        {
            FileRiskSnapshot.primary_owner_employee_id: None,
            FileRiskSnapshot.primary_owner_doa_pct: None,
        },
        synchronize_session=False,
    )
    db.query(NotionDocSnapshot).filter(
        NotionDocSnapshot.tenant_id == tenant_id,
        NotionDocSnapshot.owner_employee_id == employee_id,
    ).update(
        {NotionDocSnapshot.owner_employee_id: None},
        synchronize_session=False,
    )
    db.query(EraEvidenceMitigation).filter(
        EraEvidenceMitigation.tenant_id == tenant_id,
        EraEvidenceMitigation.mitigation_assignee_id == employee_id,
    ).update(
        {EraEvidenceMitigation.mitigation_assignee_id: None},
        synchronize_session=False,
    )
    db.query(EraEvidenceMitigation).filter(
        EraEvidenceMitigation.tenant_id == tenant_id,
        EraEvidenceMitigation.employee_id == employee_id,
    ).delete(synchronize_session=False)
    db.query(EraRiskSnapshot).filter(
        EraRiskSnapshot.tenant_id == tenant_id,
        EraRiskSnapshot.employee_id == employee_id,
    ).delete(synchronize_session=False)
    db.query(EraDepartureOrphanBaseline).filter(
        EraDepartureOrphanBaseline.tenant_id == tenant_id,
        EraDepartureOrphanBaseline.employee_id == employee_id,
    ).delete(synchronize_session=False)
    db.query(EraAlert).filter(
        EraAlert.tenant_id == tenant_id,
        EraAlert.employee_id == employee_id,
    ).update(
        {EraAlert.employee_id: None},
        synchronize_session=False,
    )


def _delete_component_dependents(
    db: Session,
    tenant_id: uuid.UUID,
    component_id: str,
) -> None:
    db.query(Assignment).filter(
        Assignment.tenant_id == tenant_id,
        Assignment.component_id == component_id,
    ).delete(synchronize_session=False)
    db.query(GitHubOwnershipSnapshot).filter(
        GitHubOwnershipSnapshot.tenant_id == tenant_id,
        GitHubOwnershipSnapshot.component_id == component_id,
    ).delete(synchronize_session=False)
    db.query(DoaFileSnapshot).filter(
        DoaFileSnapshot.tenant_id == tenant_id,
        DoaFileSnapshot.component_id == component_id,
    ).delete(synchronize_session=False)
    db.query(FileRiskSnapshot).filter(
        FileRiskSnapshot.tenant_id == tenant_id,
        FileRiskSnapshot.component_id == component_id,
    ).delete(synchronize_session=False)
    db.query(NotionDocSnapshot).filter(
        NotionDocSnapshot.tenant_id == tenant_id,
        NotionDocSnapshot.component_id == component_id,
    ).update(
        {NotionDocSnapshot.component_id: None},
        synchronize_session=False,
    )


def persist_org_chart(
    db: Session,
    payload: OrgChartIngestRequest,
    tenant_id: uuid.UUID,
) -> OrgChartIngestRequest:
    payload = scope_org_chart_to_tenant(payload, tenant_id)

    new_employee_ids = {employee.id for employee in payload.employees}
    new_component_ids = {component.id for component in payload.components}

    existing_employees = (
        db.query(Employee).filter(Employee.tenant_id == tenant_id).all()
    )
    existing_components = (
        db.query(Component).filter(Component.tenant_id == tenant_id).all()
    )

    for employee in existing_employees:
        if employee.id in new_employee_ids:
            continue
        _delete_employee_dependents(db, tenant_id, employee.id)
        db.delete(employee)

    for component in existing_components:
        if component.id in new_component_ids:
            continue
        _delete_component_dependents(db, tenant_id, component.id)
        db.delete(component)

    db.flush()
    db.query(Employee).filter(Employee.tenant_id == tenant_id).update(
        {Employee.manager_id: None}, synchronize_session=False
    )
    db.flush()

    for component in payload.components:
        row = db.get(Component, component.id)
        if row is None:
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
            continue
        row.name = component.name
        row.description = component.description
        row.open_tasks_count = component.open_tasks_count
        row.unresolved_incidents = component.unresolved_incidents

    for employee in payload.employees:
        row = db.get(Employee, employee.id)
        if row is None:
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
            continue
        row.name = employee.name
        row.role = employee.role
        row.email = employee.email
        row.tenure_years = employee.tenure_years
        row.manager_id = employee.manager_id
        row.team_name = employee.team_name

    db.flush()
    db.query(Assignment).filter(Assignment.tenant_id == tenant_id).delete(
        synchronize_session=False
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
    return payload


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
                Edge(relationship_type=validate_relation(REL_REPORTS_TO)),
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
        employee_node.owns = (
            Edge(relationship_type=validate_relation(REL_OWNS)),
            owned_components if len(owned_components) > 1 else owned_components[0],
        )
        edge_count += 2

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
    await tenant_add_data_points(tenant_id, data_points)

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
