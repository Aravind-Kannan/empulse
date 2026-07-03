from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session, joinedload

from app.models.operational import Assignment, Component, Employee
from app.schemas.era import (
    EraAffectedComponent,
    EraAnalyticsResponse,
    EraDimensions,
    EraDimensionFactorSummary,
    EraDimensionSummary,
    EraEmployeeDetailResponse,
    EraEmployeeMetrics,
    EraEvidenceItem,
    EraEvidenceSource,
    EraRecoveryEstimate,
    EraReviewNetworkEdge,
    EraReviewNetworkMetrics,
    EraReviewNetworkResponse,
    EraRiskyChangeItem,
    EraTeamRiskyChangesResponse,
)
from app.schemas.org import ACME_ORG_CHART
from app.services.cognee_era_intelligence import build_employee_detail_intelligence
from app.services.era.evidence_ids import normalize_evidence_ids
from app.services.era_mitigations import (
    apply_mitigation_overlays,
    attach_suggested_mitigations,
    count_open_mitigations,
    ensure_mitigation_records,
    evaluate_mitigation_rules,
    update_evidence_mitigation,
)
from app.services.era_snapshots import (
    apply_trends_to_employees,
    get_employee_risk_history,
    get_team_risk_history,
    manager_team_rollup,
    team_avg_trend_7d,
)
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
    _undocumented_solved_incidents,
    build_signals_for_employee,
    build_signals_from_acme_employee,
)
from app.services.github_evidence import merge_github_evidence
from app.services.jira_evidence import merge_jira_evidence
from app.services.integration_config_store import (
    get_jira_config,
    get_notion_config,
    get_slack_config,
)
from app.services.integration_telemetry import (
    get_jira_backlog_boost,
    get_review_network,
    get_team_risky_changes,
    has_github_sync,
    has_jira_sync,
    has_notion_sync,
    has_slack_sync,
    has_review_network,
    hydrate_integration_telemetry,
    hydrate_github_telemetry_from_db,
    hydrate_notion_telemetry_from_db,
)
from app.services.notion_evidence import merge_notion_evidence
from app.services.slack_evidence import merge_slack_evidence
from app.services.role_utils import is_leadership_role


def _jira_connected(db: Session, tenant_id) -> bool:
    return get_jira_config(db, tenant_id) is not None and has_jira_sync()


def _notion_connected(db: Session, tenant_id) -> bool:
    return get_notion_config(db, tenant_id) is not None and has_notion_sync()


def _slack_connected(db: Session, tenant_id) -> bool:
    return get_slack_config(db, tenant_id) is not None and has_slack_sync()


def _merge_integration_evidence(
    db: Session,
    tenant_id,
    employee_id: str,
    employee_name: str,
    base_evidence: list[dict],
    *,
    component_names: dict[str, str],
    github_connected: bool,
    jira_connected: bool,
    notion_connected: bool,
    slack_connected: bool,
    limit: int,
) -> list[dict]:
    merged = merge_github_evidence(
        employee_id,
        employee_name,
        base_evidence,
        component_names=component_names,
        github_connected=github_connected,
        limit=limit,
        db=db,
        tenant_id=tenant_id,
    )
    merged = merge_jira_evidence(
        employee_id,
        employee_name,
        merged,
        jira_connected=jira_connected,
        limit=limit,
    )
    return merge_slack_evidence(
        employee_id,
        employee_name,
        merge_notion_evidence(
            employee_id,
            employee_name,
            merged,
            notion_connected=notion_connected,
            component_names=component_names,
            limit=limit,
        ),
        slack_connected=slack_connected,
        limit=limit,
    )


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
            mitigation_status=item.get("mitigation_status"),
            suggested_mitigation=item.get("suggested_mitigation"),
            mitigation_assignee_id=item.get("mitigation_assignee_id"),
            mitigation_due_date=item.get("mitigation_due_date"),
            mitigation_notes=item.get("mitigation_notes"),
        )
        for item in items
    ]


def _finalize_evidence_with_mitigations(
    db: Session,
    tenant,
    employee: Employee,
    metric: EraEmployeeMetrics,
    evidence: list[dict],
    *,
    backup_candidate_count: int,
) -> tuple[list[dict], list]:
    items = attach_suggested_mitigations(normalize_evidence_ids(evidence))
    checklist = evaluate_mitigation_rules(
        metric,
        db=db,
        tenant_id=tenant.id,
        employee=employee,
        backup_candidate_count=backup_candidate_count,
    )
    ensure_mitigation_records(db, tenant.id, employee.id, checklist, items)
    return apply_mitigation_overlays(db, tenant.id, employee.id, items, checklist)


def patch_era_evidence_mitigation(
    db: Session,
    tenant,
    evidence_id: str,
    *,
    employee_id: str,
    mitigation_status: str,
    assignee_id: str | None = None,
    due_date=None,
    notes: str | None = None,
):
    employee = (
        db.query(Employee)
        .filter(Employee.tenant_id == tenant.id, Employee.id == employee_id)
        .one_or_none()
    )
    if employee is None:
        return None
    try:
        row = update_evidence_mitigation(
            db,
            tenant.id,
            employee_id,
            evidence_id,
            mitigation_status=mitigation_status,
            assignee_id=assignee_id,
            due_date=due_date,
            notes=notes,
        )
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    return row


def _evidence_models_to_dicts(items: list[EraEvidenceItem]) -> list[dict]:
    return [
        {
            "id": item.id,
            "dimension": item.dimension,
            "severity": item.severity,
            "title": item.title,
            "description": item.description,
            "impact_points": item.impact_points,
            "sources": [source.model_dump() for source in item.sources],
            "synthetic": item.synthetic,
            "mitigation_status": item.mitigation_status,
            "suggested_mitigation": item.suggested_mitigation,
            "mitigation_assignee_id": item.mitigation_assignee_id,
            "mitigation_due_date": item.mitigation_due_date,
            "mitigation_notes": item.mitigation_notes,
        }
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
        else _undocumented_solved_incidents(employee_id, role, notion_connected=False)
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


def _dimension_summaries_to_models(
    raw: dict[str, dict] | None,
) -> dict[str, EraDimensionSummary]:
    if not raw:
        return {}
    return {
        key: EraDimensionSummary(
            score=summary.get("score", 0.0),
            partial=summary.get("partial", False),
            headline=summary.get("headline", ""),
            top_factors=[
                EraDimensionFactorSummary(**factor)
                for factor in summary.get("top_factors", [])
            ],
        )
        for key, summary in raw.items()
    }


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
        dimension_summaries=_dimension_summaries_to_models(
            score_result.dimension_summaries
        ),
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
        identity_warning=any(level == "medium" for level in coverage.values()),
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
            "identity_warning": any(level == "medium" for level in coverage.values()),
        }
    )


def _wrap_response(
    db: Session,
    tenant,
    employees: list[EraEmployeeMetrics],
    *,
    demo_mode: bool,
) -> EraAnalyticsResponse:
    from app.services.era.org_health import compute_org_health
    from app.services.era_snapshots import team_avg_trend_7d
    from app.services.github_file_risk import count_critical_files
    from app.services.github_orphans import (
        build_orphan_evidence_items,
        count_orphan_files,
        orphan_delta_90d,
    )
    from app.services.integration_telemetry import count_team_open_p1_issues
    from app.services.jira_evidence import build_team_unassigned_p1_evidence_items
    from app.models.operational import EraAlert, EraTeamReview

    employees_with_trends = apply_trends_to_employees(db, tenant.id, employees)
    team_summary = build_team_summary(employees_with_trends)
    avg_trend = team_avg_trend_7d(db, tenant.id, team_summary.avg_risk_score)
    health = compute_org_health(db, tenant.id)
    orphan_count = count_orphan_files(db, tenant.id)
    latest_review = (
        db.query(EraTeamReview)
        .filter(EraTeamReview.tenant_id == tenant.id)
        .order_by(EraTeamReview.reviewed_at.desc())
        .first()
    )
    unacknowledged_alert_count = (
        db.query(EraAlert)
        .filter(
            EraAlert.tenant_id == tenant.id,
            EraAlert.acknowledged_at.is_(None),
        )
        .count()
    )
    team_summary = team_summary.model_copy(
        update={
            "avg_risk_trend_7d": avg_trend,
            "org_health_score": health.score,
            "orphan_file_count": orphan_count,
            "orphan_delta_90d": orphan_delta_90d(db, tenant.id),
            "org_health_caution": health.caution_small_team,
            "open_p1_count": count_team_open_p1_issues(),
            "critical_hotspot_count": count_critical_files(db, tenant.id),
            "last_risk_review_at": (
                latest_review.reviewed_at if latest_review is not None else None
            ),
            "unacknowledged_alert_count": unacknowledged_alert_count,
        }
    )
    team_evidence_raw = (
        build_orphan_evidence_items(db, tenant.id, limit=10)
        + build_team_unassigned_p1_evidence_items(db, tenant.id, limit=10)
    )
    team_evidence = _evidence_dicts_to_models(
        normalize_evidence_ids(team_evidence_raw),
    )
    return EraAnalyticsResponse(
        computed_at=datetime.now(UTC),
        demo_mode=demo_mode,
        warnings=build_warnings(db, tenant.id, demo_mode=demo_mode),
        team_summary=team_summary,
        employees=employees_with_trends,
        unmapped_activity=build_unmapped_activity(db, tenant.id),
        sync_freshness=build_sync_freshness(),
        team_risk_history_30d=get_team_risk_history(db, tenant.id, days=30),
        team_evidence=team_evidence,
    )


def _compute_v2_metrics(
    db: Session,
    tenant,
    employees: list[Employee],
    total_components: int,
    *,
    github_connected: bool,
    jira_connected: bool = False,
    notion_connected: bool = False,
    slack_connected: bool = False,
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
                jira_connected=jira_connected,
                notion_connected=notion_connected,
                slack_connected=slack_connected,
            )
        )

    tenant_stats = build_tenant_percentiles(signals_list)
    metrics: list[EraEmployeeMetrics] = []
    for signals in signals_list:
        employee = employee_by_id[signals.employee_id]
        score_result = score_employee(signals, tenant_stats, evidence_limit=5)
        component_names = {
            assignment.component.id: assignment.component.name
            for assignment in employee.assignments
        }
        merged_evidence = _merge_integration_evidence(
            db,
            tenant.id,
            signals.employee_id,
            signals.name,
            score_result.evidence,
            component_names=component_names,
            github_connected=github_connected,
            jira_connected=jira_connected,
            notion_connected=notion_connected,
            slack_connected=slack_connected,
            limit=5,
        )
        merged_evidence = normalize_evidence_ids(merged_evidence)
        score_result.evidence = merged_evidence
        score_result.evidence_total_count = len(score_result.all_evidence)
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
    return _fallback_acme_metrics_v2()


def get_era_metrics(db: Session, tenant) -> EraAnalyticsResponse:
    hydrate_integration_telemetry(db, tenant.id)
    github_connected = has_github_sync()
    jira_connected = _jira_connected(db, tenant.id)
    notion_connected = _notion_connected(db, tenant.id)
    slack_connected = _slack_connected(db, tenant.id)
    employees = (
        db.query(Employee)
        .filter(Employee.tenant_id == tenant.id, Employee.active.is_(True))
        .options(joinedload(Employee.assignments).joinedload(Assignment.component))
        .all()
    )

    if not employees:
        metrics = _fallback_acme_metrics()
        return _wrap_response(db, tenant, metrics, demo_mode=True)

    total_components = total_component_count(
        db.query(Component).filter(Component.tenant_id == tenant.id).all()
    )
    metrics = _compute_v2_metrics(
        db,
        tenant,
        employees,
        total_components,
        github_connected=github_connected,
        jira_connected=jira_connected,
        notion_connected=notion_connected,
        slack_connected=slack_connected,
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
    hydrate_integration_telemetry(db, tenant.id)
    github_connected = has_github_sync()
    jira_connected = _jira_connected(db, tenant.id)
    notion_connected = _notion_connected(db, tenant.id)
    slack_connected = _slack_connected(db, tenant.id)
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
            backup_candidates=[],
            warnings=[],
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
            backup_candidates=[],
            warnings=[],
        )

    backup_candidates: list = []
    detail_warnings: list[str] = []
    blast_radius_narrative: str | None = None
    mitigations = []
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

    signals = build_signals_for_employee(
        employee,
        all_employees=all_employees,
        total_components=total_components,
        codebase_share_pct=codebase_share_pct,
        jira_backlog_boost=jira_boost,
        github_connected=github_connected,
        jira_connected=jira_connected,
        notion_connected=notion_connected,
        slack_connected=slack_connected,
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
                jira_connected=jira_connected,
                notion_connected=notion_connected,
                slack_connected=slack_connected,
            )
        )
    tenant_stats = build_tenant_percentiles([signals, *peer_signals])
    score_result = score_employee(signals, tenant_stats, evidence_limit=1000)
    component_names = {
        assignment.component.id: assignment.component.name
        for assignment in employee.assignments
    }
    merged = _merge_integration_evidence(
        db,
        tenant.id,
        signals.employee_id,
        signals.name,
        score_result.all_evidence,
        component_names=component_names,
        github_connected=github_connected,
        jira_connected=jira_connected,
        notion_connected=notion_connected,
        slack_connected=slack_connected,
        limit=1000,
    )
    score_result.all_evidence = merged
    score_result.evidence = merged[:5]
    score_result.evidence_total_count = len(merged)
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
    intelligence = build_employee_detail_intelligence(
        db,
        tenant.id,
        employee,
        merged,
        affected,
        jira_connected=jira_connected,
        notion_connected=notion_connected,
        recovery_estimate=metric.recovery_estimate_weeks,
    )
    merged = intelligence.enriched_evidence
    if intelligence.recovery_estimate:
        metric.recovery_estimate_weeks = intelligence.recovery_estimate
    backup_candidates = intelligence.backup_candidates
    detail_warnings = intelligence.warnings
    blast_radius_narrative = intelligence.blast_radius_narrative
    merged, mitigations = _finalize_evidence_with_mitigations(
        db,
        tenant,
        employee,
        metric,
        merged,
        backup_candidate_count=len(backup_candidates),
    )
    all_evidence = _evidence_dicts_to_models(merged)

    page = all_evidence[offset : offset + limit]
    risk_history = get_employee_risk_history(db, tenant.id, employee_id, days=30)
    [metric] = apply_trends_to_employees(db, tenant.id, [metric])
    return EraEmployeeDetailResponse(
        computed_at=datetime.now(UTC),
        employee=metric,
        evidence=page,
        evidence_total_count=len(all_evidence),
        limit=limit,
        offset=offset,
        backup_candidates=backup_candidates,
        warnings=detail_warnings,
        blast_radius_narrative=blast_radius_narrative,
        risk_history_30d=risk_history,
        mitigations=mitigations,
        open_mitigations_count=count_open_mitigations(mitigations),
    )


def get_era_manager_rollup(db: Session, tenant, manager_id: str):
    return manager_team_rollup(db, tenant, manager_id)


def _parse_since_days(since: str | None, default: int = 90) -> int:
    if not since:
        return default
    cleaned = since.strip().lower()
    if cleaned.endswith("d"):
        try:
            return max(1, min(365, int(cleaned[:-1])))
        except ValueError:
            return default
    try:
        return max(1, min(365, int(cleaned)))
    except ValueError:
        return default


def _ensure_review_network(db: Session, tenant_id) -> bool:
    if has_review_network():
        return True
    if hydrate_github_telemetry_from_db(db, tenant_id):
        return has_review_network()
    from app.services.github_client import activities_from_mock_feed
    from app.services.integration_telemetry import apply_github_telemetry

    if not has_github_sync():
        apply_github_telemetry(db, tenant_id, activities_from_mock_feed())
    return has_review_network()


def get_era_review_network(
    db: Session,
    tenant,
    employee_id: str,
) -> EraReviewNetworkResponse | None:
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.tenant_id == tenant.id)
        .one_or_none()
    )
    if employee is None:
        return None

    _ensure_review_network(db, tenant.id)
    network = get_review_network()
    window_days = network.window_days if network else 90
    incoming: list[EraReviewNetworkEdge] = []
    metrics_model: EraReviewNetworkMetrics | None = None

    if network:
        from app.services.github_reviews import employee_review_subgraph

        subgraph = employee_review_subgraph(network, employee_id)
        metrics = subgraph["metrics"]
        if metrics:
            metrics_model = EraReviewNetworkMetrics(
                employee_id=metrics.employee_id,
                review_concentration_pct=metrics.review_concentration_pct,
                reviews_given_count=metrics.reviews_given_count,
                reviews_received_count=metrics.reviews_received_count,
                sole_reviewer_count=metrics.sole_reviewer_count,
                unique_reviewers_on_prs=metrics.unique_reviewers_on_prs,
                isolation_score=metrics.isolation_score,
                backup_review_score=metrics.backup_review_score,
                recent_pr_count=metrics.recent_pr_count,
                no_backup_pr_urls=metrics.no_backup_pr_urls,
                top_reviewer_employee_id=metrics.top_reviewer_employee_id,
                top_reviewer_login=metrics.top_reviewer_login,
            )
        for edge in subgraph["incoming_reviewers"]:
            incoming.append(
                EraReviewNetworkEdge(
                    reviewer_employee_id=edge.reviewer_employee_id,
                    author_employee_id=edge.author_employee_id,
                    review_count=edge.review_count,
                    reviewer_login=edge.reviewer_login,
                    author_login=edge.author_login,
                )
            )

    return EraReviewNetworkResponse(
        computed_at=datetime.now(UTC),
        employee_id=employee_id,
        window_days=window_days,
        metrics=metrics_model,
        incoming_reviewers=incoming,
    )


def get_era_team_risky_changes(
    db: Session,
    tenant,
    *,
    since: str | None = "90d",
) -> EraTeamRiskyChangesResponse:
    window_days = _parse_since_days(since)
    _ensure_review_network(db, tenant.id)
    network = get_review_network()

    employee_names: dict[str, str] = {
        row.id: row.name
        for row in db.query(Employee).filter(Employee.tenant_id == tenant.id).all()
    }

    items: list[EraRiskyChangeItem] = []
    for risky in get_team_risky_changes():
        author_name = None
        if risky.author_employee_id:
            author_name = employee_names.get(risky.author_employee_id)
        items.append(
            EraRiskyChangeItem(
                pr_number=risky.pr_number,
                pr_url=risky.pr_url,
                author_employee_id=risky.author_employee_id,
                author_login=risky.author_login,
                author_name=author_name,
                severity=risky.severity,
                rule=risky.rule,
                title=risky.title,
                description=risky.description,
                merged_at=risky.merged_at,
                impact_points=risky.impact_points,
            )
        )

    return EraTeamRiskyChangesResponse(
        computed_at=datetime.now(UTC),
        window_days=network.window_days if network else window_days,
        items=items,
    )
