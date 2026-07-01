from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models.operational import Assignment, Component, Employee
from app.schemas.era import (
    EraAffectedComponent,
    EraAnalyticsResponse,
    EraDimensions,
    EraEmployeeDetailResponse,
    EraEmployeeMetrics,
    EraEvidenceItem,
    EraEvidenceSource,
    EraRecoveryEstimate,
)
from app.schemas.org import ACME_ORG_CHART
from app.services.cognee_era_metrics import (
    calculate_graph_contribution_share,
    total_component_count,
)
from app.services.era.engine import score_employee
from app.services.era.metadata import (
    build_affected_components,
    build_identity_coverage,
    build_sync_freshness,
    build_team_summary,
    build_unmapped_activity,
    build_warnings,
    compute_data_completeness_pct,
)
from app.services.era.normalize import build_tenant_percentiles
from app.services.era.signals_builder import (
    build_signals_for_employee,
    build_signals_from_acme_employee,
)
from app.services.integration_telemetry import get_jira_backlog_boost, has_github_sync
from app.services.role_utils import is_leadership_role


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
    if is_leadership_role(role):
        return 0
    return sum(ord(char) for char in employee_id) % 6


def _evidence_dicts_to_models(items: list[dict]) -> list[EraEvidenceItem]:
    return [
        EraEvidenceItem(
            id=item["id"],
            dimension=item["dimension"],
            severity=item["severity"],
            title=item["title"],
            description=item["description"],
            impact_points=item["impact_points"],
            sources=[
                EraEvidenceSource(**source) for source in item.get("sources", [])
            ],
            synthetic=item.get("synthetic", False),
        )
        for item in items
    ]


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


def _score_result_to_metrics(
    signals,
    score_result,
    *,
    identity_coverage: dict[str, str] | None = None,
    affected_components=None,
) -> EraEmployeeMetrics:
    partial = {
        key: score_result.partial_dimensions.get(key, False)
        for key in ("knowledge", "operational", "documentation", "structural", "burnout")
        if score_result.partial_dimensions.get(key)
    }
    dimensions = EraDimensions(
        knowledge=score_result.dimensions["knowledge"],
        operational=score_result.dimensions["operational"],
        documentation=score_result.dimensions["documentation"],
        structural=score_result.dimensions["structural"],
        burnout=score_result.dimensions["burnout"],
        partial=partial,
    )
    evidence = _evidence_dicts_to_models(score_result.evidence)
    coverage = identity_coverage or {}
    recovery = None
    if score_result.recovery_estimate_weeks:
        recovery = EraRecoveryEstimate(**score_result.recovery_estimate_weeks)

    return EraEmployeeMetrics(
        employee_id=signals.employee_id,
        name=signals.name,
        role=signals.role,
        email=signals.email,
        unresolved_issues=signals.unresolved_issues,
        open_tasks=signals.open_tasks,
        undocumented_solved_incidents=signals.undocumented_solved_incidents,
        codebase_share_pct=signals.codebase_share_pct,
        risk_factor_score=score_result.composite,
        risk_level=score_result.risk_level,
        jira_backlog_boost=signals.jira_backlog_boost,
        dimensions=dimensions,
        evidence=evidence,
        evidence_total_count=score_result.evidence_total_count,
        affected_components=affected_components or [],
        identity_coverage=coverage,
        data_completeness_pct=compute_data_completeness_pct(coverage),
        recovery_estimate_weeks=recovery,
        departure_watchlist=score_result.departure_watchlist,
        excluded=score_result.excluded,
        exclusion_reason=score_result.exclusion_reason,
        trend_7d=None,
    )


def _enrich_v1_metric(
    db: Session,
    tenant,
    employee: Employee,
    metric: EraEmployeeMetrics,
    *,
    github_connected: bool,
) -> EraEmployeeMetrics:
    coverage = build_identity_coverage(
        db,
        tenant.id,
        employee.id,
        github_connected=github_connected,
    )
    affected = build_affected_components(employee, github_connected=github_connected)
    return metric.model_copy(
        update={
            "affected_components": affected,
            "identity_coverage": coverage,
            "data_completeness_pct": compute_data_completeness_pct(coverage),
        }
    )


def _wrap_response(
    db: Session,
    tenant,
    employees: list[EraEmployeeMetrics],
    *,
    demo_mode: bool,
) -> EraAnalyticsResponse:
    return EraAnalyticsResponse(
        computed_at=datetime.now(UTC),
        demo_mode=demo_mode,
        warnings=build_warnings(db, tenant.id, demo_mode=demo_mode),
        team_summary=build_team_summary(employees),
        employees=employees,
        unmapped_activity=build_unmapped_activity(db, tenant.id),
        sync_freshness=build_sync_freshness(),
    )


def _compute_v2_metrics(
    db: Session,
    tenant,
    employees: list[Employee],
    total_components: int,
    *,
    github_connected: bool,
) -> list[EraEmployeeMetrics]:
    signals_list = []
    employee_by_id = {employee.id: employee for employee in employees}

    for employee in employees:
        if is_leadership_role(employee.role):
            continue
        jira_boost = get_jira_backlog_boost(employee.id)
        codebase_share_pct = calculate_graph_contribution_share(
            employee_id=employee.id,
            assignments=employee.assignments,
            total_components=total_components,
            jira_backlog_boost=jira_boost,
        )
        signals_list.append(
            build_signals_for_employee(
                employee,
                all_employees=employees,
                total_components=total_components,
                codebase_share_pct=codebase_share_pct,
                jira_backlog_boost=jira_boost,
                github_connected=github_connected,
            )
        )

    tenant_stats = build_tenant_percentiles(signals_list)
    metrics: list[EraEmployeeMetrics] = []
    for signals in signals_list:
        employee = employee_by_id[signals.employee_id]
        score_result = score_employee(signals, tenant_stats, evidence_limit=5)
        coverage = build_identity_coverage(
            db,
            tenant.id,
            employee.id,
            github_connected=github_connected,
        )
        affected = build_affected_components(employee, github_connected=github_connected)
        metrics.append(
            _score_result_to_metrics(
                signals,
                score_result,
                identity_coverage=coverage,
                affected_components=affected,
            )
        )

    metrics.sort(
        key=lambda item: (
            -item.risk_factor_score,
            -(item.dimensions.knowledge if item.dimensions else 0),
        )
    )
    return metrics


def _fallback_acme_metrics_v1() -> list[EraEmployeeMetrics]:
    component_by_id = {c.id: c for c in ACME_ORG_CHART.components}
    total_components = total_component_count(ACME_ORG_CHART.components)
    metrics: list[EraEmployeeMetrics] = []

    for employee in ACME_ORG_CHART.employees:
        assignments = [
            a for a in ACME_ORG_CHART.assignments if a.employee_id == employee.id
        ]
        assignment_views = [
            type(
                "AssignmentView",
                (),
                {
                    "component_id": a.component_id,
                    "component": component_by_id[a.component_id],
                },
            )()
            for a in assignments
        ]
        open_tasks = sum(
            component_by_id[a.component_id].open_tasks_count for a in assignments
        )
        unresolved_issues = sum(
            component_by_id[a.component_id].unresolved_incidents for a in assignments
        )
        codebase_share_pct = calculate_graph_contribution_share(
            employee_id=employee.id,
            assignments=assignment_views,  # type: ignore[arg-type]
            total_components=total_components,
            jira_backlog_boost=get_jira_backlog_boost(employee.id),
        )
        coverage = {provider: "high" for provider in ("github", "jira", "slack", "notion")}
        affected = [
            EraAffectedComponent(
                id=component_by_id[a.component_id].id,
                name=component_by_id[a.component_id].name,
                spof=False,
                criticality="tier2_core",
            )
            for a in assignments
        ]

        metric = _metrics_from_counts(
            employee_id=employee.id,
            name=employee.name,
            role=employee.role,
            email=employee.email,
            unresolved_issues=unresolved_issues,
            open_tasks=open_tasks,
            codebase_share_pct=codebase_share_pct,
            jira_backlog_boost=get_jira_backlog_boost(employee.id),
        )
        metrics.append(
            metric.model_copy(
                update={
                    "identity_coverage": coverage,
                    "data_completeness_pct": compute_data_completeness_pct(coverage),
                    "affected_components": affected,
                }
            )
        )

    return metrics


def _fallback_acme_metrics_v2() -> list[EraEmployeeMetrics]:
    component_by_id = {c.id: c for c in ACME_ORG_CHART.components}
    total_components = total_component_count(ACME_ORG_CHART.components)
    employees = ACME_ORG_CHART.employees
    signals_list = []

    for employee in employees:
        if is_leadership_role(employee.role):
            continue
        assignments = [
            a for a in ACME_ORG_CHART.assignments if a.employee_id == employee.id
        ]
        assignment_views = [
            type(
                "AssignmentView",
                (),
                {
                    "component_id": a.component_id,
                    "component": component_by_id[a.component_id],
                },
            )()
            for a in assignments
        ]
        jira_boost = get_jira_backlog_boost(employee.id)
        codebase_share_pct = calculate_graph_contribution_share(
            employee_id=employee.id,
            assignments=assignment_views,  # type: ignore[arg-type]
            total_components=total_components,
            jira_backlog_boost=jira_boost,
        )
        signals_list.append(
            build_signals_from_acme_employee(
                employee,
                all_employees=employees,
                component_by_id=component_by_id,
                assignments=assignments,
                total_components=total_components,
                codebase_share_pct=codebase_share_pct,
                jira_backlog_boost=jira_boost,
            )
        )

    tenant_stats = build_tenant_percentiles(signals_list)
    metrics: list[EraEmployeeMetrics] = []
    for signals in signals_list:
        score_result = score_employee(signals, tenant_stats, evidence_limit=5)
        coverage = {provider: "high" for provider in ("github", "jira", "slack", "notion")}

        affected = [
            EraAffectedComponent(
                id=component_by_id[a.component_id].id,
                name=component_by_id[a.component_id].name,
                spof=False,
                criticality="tier2_core",
            )
            for a in ACME_ORG_CHART.assignments
            if a.employee_id == signals.employee_id
        ]
        metrics.append(
            _score_result_to_metrics(
                signals,
                score_result,
                identity_coverage=coverage,
                affected_components=affected,
            )
        )
    metrics.sort(
        key=lambda item: (
            -item.risk_factor_score,
            -(item.dimensions.knowledge if item.dimensions else 0),
        )
    )
    return metrics


def _fallback_acme_metrics() -> list[EraEmployeeMetrics]:
    if get_settings().era_v2_scoring:
        return _fallback_acme_metrics_v2()
    return _fallback_acme_metrics_v1()


def get_era_metrics(db: Session, tenant) -> EraAnalyticsResponse:
    use_v2 = get_settings().era_v2_scoring
    github_connected = has_github_sync()
    employees = (
        db.query(Employee)
        .filter(Employee.tenant_id == tenant.id)
        .options(joinedload(Employee.assignments).joinedload(Assignment.component))
        .all()
    )

    if not employees:
        metrics = _fallback_acme_metrics()
        return _wrap_response(db, tenant, metrics, demo_mode=True)

    if not use_v2:
        total_components = total_component_count(
            db.query(Component).filter(Component.tenant_id == tenant.id).all()
        )
        metrics: list[EraEmployeeMetrics] = []
        for employee in employees:
            if is_leadership_role(employee.role):
                continue
            open_tasks = sum(
                assignment.component.open_tasks_count for assignment in employee.assignments
            )
            unresolved_issues = sum(
                assignment.component.unresolved_incidents
                for assignment in employee.assignments
            )
            jira_boost = get_jira_backlog_boost(employee.id)
            codebase_share_pct = calculate_graph_contribution_share(
                employee_id=employee.id,
                assignments=employee.assignments,
                total_components=total_components,
                jira_backlog_boost=jira_boost,
            )
            metric = _metrics_from_counts(
                employee_id=employee.id,
                name=employee.name,
                role=employee.role,
                email=employee.email,
                unresolved_issues=unresolved_issues,
                open_tasks=open_tasks,
                codebase_share_pct=codebase_share_pct,
                jira_backlog_boost=jira_boost,
            )
            metrics.append(
                _enrich_v1_metric(
                    db,
                    tenant,
                    employee,
                    metric,
                    github_connected=github_connected,
                )
            )
        metrics.sort(key=lambda item: -item.risk_factor_score)
        return _wrap_response(db, tenant, metrics, demo_mode=False)

    total_components = total_component_count(
        db.query(Component).filter(Component.tenant_id == tenant.id).all()
    )
    metrics = _compute_v2_metrics(
        db,
        tenant,
        employees,
        total_components,
        github_connected=github_connected,
    )
    return _wrap_response(db, tenant, metrics, demo_mode=False)


def get_era_employee_detail(
    db: Session,
    tenant,
    employee_id: str,
    *,
    limit: int = 20,
    offset: int = 0,
) -> EraEmployeeDetailResponse | None:
    use_v2 = get_settings().era_v2_scoring
    github_connected = has_github_sync()
    employee = (
        db.query(Employee)
        .filter(
            Employee.tenant_id == tenant.id,
            Employee.id == employee_id,
        )
        .options(joinedload(Employee.assignments).joinedload(Assignment.component))
        .one_or_none()
    )

    if employee is None and not db.query(Employee).filter(Employee.tenant_id == tenant.id).count():
        fallback = next(
            (item for item in _fallback_acme_metrics() if item.employee_id == employee_id),
            None,
        )
        if fallback is None:
            return None
        evidence = fallback.evidence
        return EraEmployeeDetailResponse(
            computed_at=datetime.now(UTC),
            employee=fallback,
            evidence=evidence,
            evidence_total_count=fallback.evidence_total_count or len(evidence),
            limit=limit,
            offset=offset,
        )

    if employee is None:
        return None

    if is_leadership_role(employee.role):
        metric = EraEmployeeMetrics(
            employee_id=employee.id,
            name=employee.name,
            role=employee.role,
            email=employee.email,
            unresolved_issues=0,
            open_tasks=0,
            undocumented_solved_incidents=0,
            codebase_share_pct=0.0,
            risk_factor_score=0.0,
            risk_level="low",
            excluded=True,
            exclusion_reason="leadership_role",
        )
        return EraEmployeeDetailResponse(
            computed_at=datetime.now(UTC),
            employee=metric,
            evidence=[],
            evidence_total_count=0,
            limit=limit,
            offset=offset,
        )

    total_components = total_component_count(
        db.query(Component).filter(Component.tenant_id == tenant.id).all()
    )
    all_employees = (
        db.query(Employee)
        .filter(Employee.tenant_id == tenant.id)
        .options(joinedload(Employee.assignments).joinedload(Assignment.component))
        .all()
    )
    jira_boost = get_jira_backlog_boost(employee.id)
    codebase_share_pct = calculate_graph_contribution_share(
        employee_id=employee.id,
        assignments=employee.assignments,
        total_components=total_components,
        jira_backlog_boost=jira_boost,
    )

    if use_v2:
        signals = build_signals_for_employee(
            employee,
            all_employees=all_employees,
            total_components=total_components,
            codebase_share_pct=codebase_share_pct,
            jira_backlog_boost=jira_boost,
            github_connected=github_connected,
        )
        peer_signals = []
        for peer in all_employees:
            if is_leadership_role(peer.role) or peer.id == employee.id:
                continue
            peer_signals.append(
                build_signals_for_employee(
                    peer,
                    all_employees=all_employees,
                    total_components=total_components,
                    codebase_share_pct=calculate_graph_contribution_share(
                        employee_id=peer.id,
                        assignments=peer.assignments,
                        total_components=total_components,
                        jira_backlog_boost=get_jira_backlog_boost(peer.id),
                    ),
                    jira_backlog_boost=get_jira_backlog_boost(peer.id),
                    github_connected=github_connected,
                )
            )
        tenant_stats = build_tenant_percentiles([signals, *peer_signals])
        score_result = score_employee(signals, tenant_stats, evidence_limit=1000)
        coverage = build_identity_coverage(
            db, tenant.id, employee.id, github_connected=github_connected
        )
        affected = build_affected_components(employee, github_connected=github_connected)
        metric = _score_result_to_metrics(
            signals,
            score_result,
            identity_coverage=coverage,
            affected_components=affected,
        )
        all_evidence = _evidence_dicts_to_models(score_result.all_evidence)
    else:
        open_tasks = sum(a.component.open_tasks_count for a in employee.assignments)
        unresolved = sum(a.component.unresolved_incidents for a in employee.assignments)
        metric = _enrich_v1_metric(
            db,
            tenant,
            employee,
            _metrics_from_counts(
                employee_id=employee.id,
                name=employee.name,
                role=employee.role,
                email=employee.email,
                unresolved_issues=unresolved,
                open_tasks=open_tasks,
                codebase_share_pct=codebase_share_pct,
                jira_backlog_boost=jira_boost,
            ),
            github_connected=github_connected,
        )
        all_evidence = list(metric.evidence)

    page = all_evidence[offset : offset + limit]
    return EraEmployeeDetailResponse(
        computed_at=datetime.now(UTC),
        employee=metric,
        evidence=page,
        evidence_total_count=len(all_evidence),
        limit=limit,
        offset=offset,
    )
