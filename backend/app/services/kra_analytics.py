from collections import defaultdict

from sqlalchemy.orm import Session, joinedload

from app.models.operational import Assignment, Component, Employee
from app.schemas.kra import KraAnalyticsResponse, KraLink, KraNode
from app.schemas.org import ACME_ORG_CHART
from app.services.integration_telemetry import (
    get_all_bus_factors,
    get_github_ownership,
    has_github_sync,
    is_github_spof,
)
from app.services.role_utils import is_leadership_role

DOCUMENTATION_SOURCES: dict[str, list[str]] = {
    "comp-payments": [
        "Notion: Payment Gateway Runbook",
        "Slack: #payments-oncall",
    ],
    "comp-auth": [
        "Notion: Auth Service Architecture",
        "Slack: #identity-team",
    ],
    "comp-notifications": [
        "Notion: Notification Hub Playbook",
        "Slack: #comms-infra",
    ],
}


def _doc_sources_for_component(component_id: str, name: str) -> list[str]:
    return DOCUMENTATION_SOURCES.get(
        component_id,
        [f"Notion: {name} Overview"],
    )


def _build_graph(
    employees: list,
    components: list,
    assignments: list,
) -> KraAnalyticsResponse:
    nodes: list[KraNode] = []
    links: list[KraLink] = []

    employee_ids_with_assignments: set[str] = set()
    for assignment in assignments:
        employee_ids_with_assignments.add(assignment.employee_id)

    for employee in employees:
        if is_leadership_role(employee.role):
            continue
        nodes.append(
            KraNode(
                id=employee.id,
                label=employee.name,
                type="engineer",
                role=employee.role,
            )
        )

    component_nodes: list[KraNode] = []
    for component in components:
        component_nodes.append(
            KraNode(
                id=component.id,
                label=component.name,
                type="component",
                description=component.description,
                documentation_sources=_doc_sources_for_component(
                    component.id, component.name
                ),
            )
        )
    nodes.extend(component_nodes)

    for assignment in assignments:
        links.append(
            KraLink(
                source=assignment.employee_id,
                target=assignment.component_id,
                relationship="owns",
                codebase_share_pct=assignment.codebase_share_pct,
            )
        )

    if has_github_sync():
        github_ownership = get_github_ownership()
        links = [
            link
            for link in links
            if link.target not in github_ownership
        ]
        for component_id, contributors in github_ownership.items():
            for employee_id, share_pct in contributors.items():
                links.append(
                    KraLink(
                        source=employee_id,
                        target=component_id,
                        relationship="owns",
                        codebase_share_pct=share_pct,
                    )
                )

    engineers_by_component: dict[str, set[str]] = defaultdict(set)
    for link in links:
        engineers_by_component[link.target].add(link.source)

    bus_factors = get_all_bus_factors() if has_github_sync() else {}

    for node in nodes:
        if node.type != "component":
            continue
        structural_spof = len(engineers_by_component.get(node.id, set())) <= 1
        github_spof = is_github_spof(node.id)
        node.is_spof = structural_spof or github_spof
        node.github_verified_spof = github_spof
        node.bus_factor = bus_factors.get(node.id)

    return KraAnalyticsResponse(nodes=nodes, links=links)


def _fallback_acme_graph() -> KraAnalyticsResponse:
    return _build_graph(
        ACME_ORG_CHART.employees,
        ACME_ORG_CHART.components,
        ACME_ORG_CHART.assignments,
    )


def get_kra_graph(db: Session, tenant) -> KraAnalyticsResponse:
    employees = db.query(Employee).filter(Employee.tenant_id == tenant.id).all()
    components = db.query(Component).filter(Component.tenant_id == tenant.id).all()
    assignments = (
        db.query(Assignment)
        .filter(Assignment.tenant_id == tenant.id)
        .options(joinedload(Assignment.employee), joinedload(Assignment.component))
        .all()
    )

    if not employees or not components:
        return _fallback_acme_graph()

    class _EmployeeView:
        def __init__(self, emp: Employee):
            self.id = emp.id
            self.name = emp.name
            self.role = emp.role

    class _ComponentView:
        def __init__(self, comp: Component):
            self.id = comp.id
            self.name = comp.name
            self.description = comp.description

    class _AssignmentView:
        def __init__(self, asn: Assignment):
            self.employee_id = asn.employee_id
            self.component_id = asn.component_id
            self.codebase_share_pct = asn.codebase_share_pct

    return _build_graph(
        [_EmployeeView(e) for e in employees],
        [_ComponentView(c) for c in components],
        [_AssignmentView(a) for a in assignments],
    )


def assign_backup_engineer(
    db: Session,
    *,
    tenant,
    component_id: str,
    employee_id: str,
    codebase_share_pct: float,
) -> bool:
    component = (
        db.query(Component)
        .filter(Component.id == component_id, Component.tenant_id == tenant.id)
        .first()
    )
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.tenant_id == tenant.id)
        .first()
    )
    if not component or not employee:
        raise ValueError("Unknown component or employee.")

    existing = (
        db.query(Assignment)
        .filter(
            Assignment.component_id == component_id,
            Assignment.employee_id == employee_id,
            Assignment.tenant_id == tenant.id,
        )
        .first()
    )
    if existing:
        return False

    db.add(
        Assignment(
            tenant_id=tenant.id,
            employee_id=employee_id,
            component_id=component_id,
            codebase_share_pct=codebase_share_pct,
        )
    )
    db.commit()
    return True


def is_component_spof_resolved(db: Session, tenant, component_id: str) -> bool:
    graph = get_kra_graph(db, tenant)
    for node in graph.nodes:
        if node.id == component_id and node.type == "component":
            return not node.is_spof
    return True
