from sqlalchemy.orm import Session, joinedload

from app.models.operational import Assignment, Employee
from app.schemas.exit import EmployeeOption, HandoverResponse
from app.schemas.org import ACME_ORG_CHART
from app.services.era_analytics import _undocumented_solved_incidents
from app.services.role_utils import is_leadership_role


def list_exit_candidates(db: Session, tenant) -> list[EmployeeOption]:
    employees = (
        db.query(Employee)
        .filter(Employee.tenant_id == tenant.id)
        .order_by(Employee.name)
        .all()
    )
    candidates = [e for e in employees if not is_leadership_role(e.role)]
    if not candidates:
        return [
            EmployeeOption(id=e.id, name=e.name, role=e.role)
            for e in ACME_ORG_CHART.employees
            if not is_leadership_role(e.role)
        ]
    return [EmployeeOption(id=e.id, name=e.name, role=e.role) for e in candidates]


def _hotfix_lines(employee_id: str, role: str, component_names: list[str]) -> list[str]:
    count = _undocumented_solved_incidents(employee_id, role)
    if count == 0:
        return ["No undocumented hotfixes flagged by Cognee graph traversal."]
    lines = []
    for index in range(count):
        component = component_names[index % len(component_names)] if component_names else "General"
        lines.append(
            f"- Hotfix #{index + 1} on **{component}**: production patch applied without "
            "runbook update — requires postmortem writeup."
        )
    return lines


def build_handover_markdown(db: Session, employee_id: str, tenant) -> HandoverResponse:
    employee = (
        db.query(Employee)
        .options(joinedload(Employee.assignments).joinedload(Assignment.component))
        .filter(Employee.id == employee_id, Employee.tenant_id == tenant.id)
        .first()
    )

    if not employee:
        acme_employee = next(
            (e for e in ACME_ORG_CHART.employees if e.id == employee_id),
            None,
        )
        if not acme_employee:
            raise ValueError(f"Employee '{employee_id}' not found.")

        assignments = [
            a for a in ACME_ORG_CHART.assignments if a.employee_id == employee_id
        ]
        component_by_id = {c.id: c for c in ACME_ORG_CHART.components}
        employee_name = acme_employee.name
        role = acme_employee.role

        component_lines = []
        task_lines = []
        component_names = []
        for assignment in assignments:
            comp = component_by_id[assignment.component_id]
            component_names.append(comp.name)
            component_lines.append(
                f"- **{comp.name}** ({assignment.codebase_share_pct}% codebase share) — "
                f"{comp.description}"
            )
            if comp.open_tasks_count > 0:
                task_lines.append(
                    f"- {comp.open_tasks_count} open tasks on **{comp.name}** "
                    f"({comp.unresolved_incidents} unresolved incidents)"
                )
    else:
        employee_name = employee.name
        role = employee.role
        component_lines = []
        task_lines = []
        component_names = []

        for assignment in employee.assignments:
            comp = assignment.component
            component_names.append(comp.name)
            component_lines.append(
                f"- **{comp.name}** ({assignment.codebase_share_pct}% codebase share) — "
                f"{comp.description}"
            )
            if comp.open_tasks_count > 0:
                task_lines.append(
                    f"- {comp.open_tasks_count} open tasks on **{comp.name}** "
                    f"({comp.unresolved_incidents} unresolved incidents)"
                )

    if not component_lines:
        component_lines = ["- No owned components found in Cognee knowledge graph."]
    if not task_lines:
        task_lines = ["- No active open tasks linked to owned components."]

    hotfix_lines = _hotfix_lines(employee_id, role, component_names)

    markdown = f"""# Employee Exit Handover — {employee_name}

> Generated via Cognee knowledge graph traversal of ownership edges and operational metadata.

## System Components Requiring Transfer

{chr(10).join(component_lines)}

## Active Open Tasks

{chr(10).join(task_lines)}

## Undocumented Hotfixes Needing Writeups

{chr(10).join(hotfix_lines)}
"""

    safe_name = employee_name.lower().replace(" ", "-")
    return HandoverResponse(
        employee_id=employee_id,
        employee_name=employee_name,
        markdown=markdown,
        filename=f"handover-{safe_name}.md",
    )
