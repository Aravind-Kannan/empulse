from sqlalchemy.orm import Session, joinedload

from app.models.operational import Assignment, Employee
from app.schemas.era import EraAnalyticsResponse, EraEmployeeMetrics
from app.schemas.org import ACME_ORG_CHART
from app.services.integration_telemetry import get_jira_backlog_boost


def _risk_level(score: float) -> str:
    if score > 75:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _calculate_risk_score(
    unresolved_issues: int,
    open_tasks: int,
    undocumented_solved_incidents: int,
    codebase_share_pct: float,
) -> float:
    raw = (
        (unresolved_issues * 5)
        + (open_tasks * 3)
        + (undocumented_solved_incidents * 10)
        + (codebase_share_pct * 0.4)
    )
    return min(100.0, float(raw))


def _undocumented_solved_incidents(employee_id: str, role: str) -> int:
    if role.lower() == "manager":
        return 0
    return sum(ord(char) for char in employee_id) % 6


def _metrics_from_counts(
    *,
    employee_id: str,
    name: str,
    role: str,
    email: str,
    unresolved_issues: int,
    open_tasks: int,
    codebase_share_pct: float,
    undocumented_solved_incidents: int | None = None,
    jira_backlog_boost: int = 0,
) -> EraEmployeeMetrics:
    undocumented = (
        undocumented_solved_incidents
        if undocumented_solved_incidents is not None
        else _undocumented_solved_incidents(employee_id, role)
    )
    adjusted_unresolved = unresolved_issues + jira_backlog_boost
    score = _calculate_risk_score(
        adjusted_unresolved,
        open_tasks,
        undocumented,
        codebase_share_pct,
    )
    return EraEmployeeMetrics(
        employee_id=employee_id,
        name=name,
        role=role,
        email=email,
        unresolved_issues=adjusted_unresolved,
        open_tasks=open_tasks,
        undocumented_solved_incidents=undocumented,
        codebase_share_pct=codebase_share_pct,
        risk_factor_score=round(score, 1),
        risk_level=_risk_level(score),
        jira_backlog_boost=jira_backlog_boost,
    )


def _fallback_acme_metrics() -> list[EraEmployeeMetrics]:
    component_by_id = {c.id: c for c in ACME_ORG_CHART.components}
    metrics: list[EraEmployeeMetrics] = []

    for employee in ACME_ORG_CHART.employees:
        assignments = [
            a for a in ACME_ORG_CHART.assignments if a.employee_id == employee.id
        ]
        open_tasks = sum(
            component_by_id[a.component_id].open_tasks_count for a in assignments
        )
        unresolved_issues = sum(
            component_by_id[a.component_id].unresolved_incidents for a in assignments
        )
        codebase_share_pct = min(
            100.0, sum(a.codebase_share_pct for a in assignments)
        )

        metrics.append(
            _metrics_from_counts(
                employee_id=employee.id,
                name=employee.name,
                role=employee.role,
                email=employee.email,
                unresolved_issues=unresolved_issues,
                open_tasks=open_tasks,
                codebase_share_pct=codebase_share_pct,
                jira_backlog_boost=get_jira_backlog_boost(employee.id),
            )
        )

    return metrics


def get_era_metrics(db: Session) -> EraAnalyticsResponse:
    employees = (
        db.query(Employee)
        .options(joinedload(Employee.assignments).joinedload(Assignment.component))
        .all()
    )

    if not employees:
        return EraAnalyticsResponse(employees=_fallback_acme_metrics())

    metrics: list[EraEmployeeMetrics] = []
    for employee in employees:
        open_tasks = sum(
            assignment.component.open_tasks_count for assignment in employee.assignments
        )
        unresolved_issues = sum(
            assignment.component.unresolved_incidents
            for assignment in employee.assignments
        )
        codebase_share_pct = min(
            100.0, sum(assignment.codebase_share_pct for assignment in employee.assignments)
        )

        metrics.append(
            _metrics_from_counts(
                employee_id=employee.id,
                name=employee.name,
                role=employee.role,
                email=employee.email,
                unresolved_issues=unresolved_issues,
                open_tasks=open_tasks,
                codebase_share_pct=codebase_share_pct,
                jira_backlog_boost=get_jira_backlog_boost(employee.id),
            )
        )

    return EraAnalyticsResponse(employees=metrics)
