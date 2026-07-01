"""Build EmployeeSignals from operational DB models and telemetry."""

from __future__ import annotations

from app.models.operational import Assignment, Component, Employee
from app.services.era.composite import criticality_multiplier
from app.services.era.signals import EmployeeSignals
from app.services.integration_telemetry import get_github_ownership, is_github_spof
from app.services.role_utils import is_leadership_role


def _undocumented_solved_incidents(employee_id: str, role: str) -> int:
    if is_leadership_role(role):
        return 0
    return sum(ord(char) for char in employee_id) % 6


def _direct_reports(employee_id: str, employees: list[Employee]) -> int:
    return sum(1 for employee in employees if employee.manager_id == employee_id)


def _max_github_ownership(employee_id: str, component_ids: set[str]) -> float:
    ownership = get_github_ownership()
    if not ownership:
        return 0.0
    values = [
        ownership.get(component_id, {}).get(employee_id, 0.0)
        for component_id in component_ids
    ]
    return max(values) if values else 0.0


def _spof_count(component_ids: set[str]) -> int:
    return sum(1 for component_id in component_ids if is_github_spof(component_id))


def build_signals_for_employee(
    employee: Employee,
    *,
    all_employees: list[Employee],
    total_components: int,
    codebase_share_pct: float,
    jira_backlog_boost: int,
    github_connected: bool = False,
) -> EmployeeSignals:
    assignments: list[Assignment] = employee.assignments
    component_ids = {assignment.component_id for assignment in assignments}
    components: list[Component] = [assignment.component for assignment in assignments]

    open_tasks = sum(component.open_tasks_count for component in components)
    unresolved_issues = sum(component.unresolved_incidents for component in components)
    owned_count = len(component_ids)
    breadth_pct = (owned_count / total_components) * 100 if total_components else 0.0
    criticalities = [getattr(component, "criticality", "tier2_core") for component in components]
    max_crit_mult = max(
        (criticality_multiplier(value) for value in criticalities),
        default=1.0,
    )

    max_ownership = _max_github_ownership(employee.id, component_ids)
    if max_ownership == 0.0:
        max_ownership = codebase_share_pct

    return EmployeeSignals(
        employee_id=employee.id,
        name=employee.name,
        role=employee.role,
        email=employee.email,
        tenure_months=employee.tenure_years * 12,
        direct_reports=_direct_reports(employee.id, all_employees),
        unresolved_issues=unresolved_issues + jira_backlog_boost,
        open_tasks=open_tasks,
        undocumented_solved_incidents=_undocumented_solved_incidents(
            employee.id, employee.role
        ),
        codebase_share_pct=codebase_share_pct,
        jira_backlog_boost=jira_backlog_boost,
        max_github_ownership_pct=max_ownership,
        spof_component_count=_spof_count(component_ids),
        assignment_breadth_pct=round(breadth_pct, 1),
        owned_component_count=owned_count,
        max_criticality_multiplier=max_crit_mult,
        github_connected=github_connected,
        identity_coverage_github="confirmed" if github_connected else "missing",
        component_names=[component.name for component in components],
    )


def build_signals_from_acme_employee(
    employee,
    *,
    all_employees: list,
    component_by_id: dict,
    assignments: list,
    total_components: int,
    codebase_share_pct: float,
    jira_backlog_boost: int,
) -> EmployeeSignals:
    component_ids = {assignment.component_id for assignment in assignments}
    components = [component_by_id[cid] for cid in component_ids]
    open_tasks = sum(component.open_tasks_count for component in components)
    unresolved = sum(component.unresolved_incidents for component in components)
    direct_reports = sum(1 for item in all_employees if item.manager_id == employee.id)
    owned_count = len(component_ids)
    breadth_pct = (owned_count / total_components) * 100 if total_components else 0.0

    return EmployeeSignals(
        employee_id=employee.id,
        name=employee.name,
        role=employee.role,
        email=employee.email,
        tenure_months=employee.tenure_years * 12,
        direct_reports=direct_reports,
        unresolved_issues=unresolved + jira_backlog_boost,
        open_tasks=open_tasks,
        undocumented_solved_incidents=_undocumented_solved_incidents(
            employee.id, employee.role
        ),
        codebase_share_pct=codebase_share_pct,
        jira_backlog_boost=jira_backlog_boost,
        max_github_ownership_pct=codebase_share_pct,
        spof_component_count=0,
        assignment_breadth_pct=round(breadth_pct, 1),
        owned_component_count=owned_count,
        github_connected=False,
        identity_coverage_github="missing",
        component_names=[component.name for component in components],
    )
