"""ERA API response metadata: team summary, sync freshness, identity coverage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.operational import Assignment, Component, Employee, EmployeeIdentity
from app.schemas.era import (
    EraAffectedComponent,
    EraEmployeeMetrics,
    EraRecoveryEstimate,
    EraTeamSummary,
    EraUnmappedActivityCount,
)
from app.services.era.types import DIMENSION_KEYS
from app.services.identity_mapping import PROVIDERS
from app.services.integration_config_store import get_github_config, get_jira_config
from app.services.integration_telemetry import (
    get_github_ownership,
    get_sync_freshness,
    has_github_sync,
    has_jira_sync,
    is_github_spof,
)
from app.services.unmapped_activity import get_unmapped_counts_by_provider

STALE_SYNC_HOURS = 24


def build_identity_coverage(
    db: Session,
    tenant_id,
    employee_id: str,
    *,
    github_connected: bool,
) -> dict[str, str]:
    rows = (
        db.query(EmployeeIdentity)
        .filter(
            EmployeeIdentity.tenant_id == tenant_id,
            EmployeeIdentity.employee_id == employee_id,
        )
        .all()
    )
    saved = {row.provider: row.confidence for row in rows}
    coverage: dict[str, str] = {}
    for provider in PROVIDERS:
        if provider in saved:
            confidence = saved[provider]
            coverage[provider] = (
                confidence if confidence in {"confirmed", "high"} else "confirmed"
            )
        elif provider == "github" and github_connected:
            coverage[provider] = "high"
        else:
            coverage[provider] = "missing"
    return coverage


def compute_data_completeness_pct(identity_coverage: dict[str, str]) -> float:
    if not identity_coverage:
        return 0.0
    connected = sum(
        1 for level in identity_coverage.values() if level in {"confirmed", "high"}
    )
    return round((connected / len(PROVIDERS)) * 100, 1)


def build_affected_components(
    employee: Employee,
    *,
    github_connected: bool,
) -> list[EraAffectedComponent]:
    ownership = get_github_ownership() if github_connected else {}
    components: list[EraAffectedComponent] = []
    seen: set[str] = set()

    for assignment in employee.assignments:
        component = assignment.component
        if component.id in seen:
            continue
        seen.add(component.id)
        owner_pct = ownership.get(component.id, {}).get(employee.id)
        criticality = getattr(component, "criticality", "tier2_core")
        components.append(
            EraAffectedComponent(
                id=component.id,
                name=component.name,
                spof=is_github_spof(component.id) if github_connected else False,
                criticality=criticality,
                ownership_pct=owner_pct,
            )
        )
    return components


def build_team_summary(employees: list[EraEmployeeMetrics]) -> EraTeamSummary:
    active = [employee for employee in employees if not employee.excluded]
    if not active:
        return EraTeamSummary(
            avg_risk_score=0.0,
            high_risk_count=0,
            medium_risk_count=0,
            low_risk_count=0,
            spof_component_count=0,
            open_p1_count=0,
            undocumented_incident_count=0,
            top_risk_driver="knowledge",
            estimated_recovery_weeks=EraRecoveryEstimate(min=1, max=1),
            data_health_pct=0.0,
        )

    avg_risk = sum(employee.risk_factor_score for employee in active) / len(active)
    high = sum(1 for employee in active if employee.risk_level == "high")
    medium = sum(1 for employee in active if employee.risk_level == "medium")
    low = sum(1 for employee in active if employee.risk_level == "low")
    spof_count = len(
        {
            component.id
            for employee in active
            for component in employee.affected_components
            if component.spof
        }
    )
    open_p1 = sum(
        1
        for employee in active
        for component in employee.affected_components
        if component.criticality == "tier1_revenue"
    )
    undocumented = sum(employee.undocumented_solved_incidents for employee in active)
    data_health = sum(employee.data_completeness_pct for employee in active) / len(
        active
    )

    dimension_avgs: dict[str, float] = {key: 0.0 for key in DIMENSION_KEYS}
    dimension_counts = 0
    for employee in active:
        if not employee.dimensions:
            continue
        dimension_counts += 1
        dimension_avgs["knowledge"] += employee.dimensions.knowledge
        dimension_avgs["operational"] += employee.dimensions.operational
        dimension_avgs["documentation"] += employee.dimensions.documentation
        dimension_avgs["structural"] += employee.dimensions.structural
        dimension_avgs["burnout"] += employee.dimensions.burnout

    top_driver = "knowledge"
    if dimension_counts:
        for key in dimension_avgs:
            dimension_avgs[key] /= dimension_counts
        top_driver = max(dimension_avgs, key=dimension_avgs.get)

    recovery_mins: list[int] = []
    recovery_maxs: list[int] = []
    for employee in active:
        if employee.recovery_estimate_weeks:
            recovery_mins.append(employee.recovery_estimate_weeks.min)
            recovery_maxs.append(employee.recovery_estimate_weeks.max)

    return EraTeamSummary(
        avg_risk_score=round(avg_risk, 1),
        high_risk_count=high,
        medium_risk_count=medium,
        low_risk_count=low,
        spof_component_count=spof_count,
        open_p1_count=open_p1,
        undocumented_incident_count=undocumented,
        top_risk_driver=top_driver,
        estimated_recovery_weeks=EraRecoveryEstimate(
            min=min(recovery_mins) if recovery_mins else 1,
            max=max(recovery_maxs) if recovery_maxs else 1,
        ),
        data_health_pct=round(data_health, 1),
    )


def build_unmapped_activity(db: Session, tenant_id) -> list[EraUnmappedActivityCount]:
    return [
        EraUnmappedActivityCount(provider=row.provider, count=row.count)
        for row in get_unmapped_counts_by_provider(db, tenant_id)
    ]


def build_sync_freshness() -> dict[str, str | None]:
    freshness = get_sync_freshness()
    return {
        "github": freshness.get("github"),
        "jira": freshness.get("jira"),
        "slack": freshness.get("slack"),
        "notion": freshness.get("notion"),
    }


def build_warnings(
    db: Session,
    tenant_id,
    *,
    demo_mode: bool,
) -> list[str]:
    warnings: list[str] = []
    now = datetime.now(UTC)
    freshness = get_sync_freshness()

    if get_github_config(db, tenant_id) and not has_github_sync():
        warnings.append("github_not_synced")
    github_at = freshness.get("github")
    if github_at:
        synced = datetime.fromisoformat(github_at)
        if synced.tzinfo is None:
            synced = synced.replace(tzinfo=UTC)
        if now - synced > timedelta(hours=STALE_SYNC_HOURS):
            warnings.append("github_stale")

    if get_jira_config(db, tenant_id) and not has_jira_sync():
        warnings.append("jira_not_synced")
    jira_at = freshness.get("jira")
    if jira_at:
        synced = datetime.fromisoformat(jira_at)
        if synced.tzinfo is None:
            synced = synced.replace(tzinfo=UTC)
        if now - synced > timedelta(hours=STALE_SYNC_HOURS):
            warnings.append("jira_stale")

    unmapped = build_unmapped_activity(db, tenant_id)
    if any(row.count > 0 for row in unmapped):
        warnings.append("partial_identity")

    if not demo_mode:
        employee_count = (
            db.query(Employee.id)
            .filter(Employee.tenant_id == tenant_id)
            .count()
        )
        if employee_count:
            component_count = (
                db.query(Component.id)
                .filter(Component.tenant_id == tenant_id)
                .count()
            )
            assigned_employee_count = (
                db.query(Assignment.employee_id)
                .join(Employee, Employee.id == Assignment.employee_id)
                .filter(Employee.tenant_id == tenant_id)
                .distinct()
                .count()
            )
            if component_count == 0:
                warnings.append(
                    "No components in org chart — add components and assignments "
                    "so ERA can score employees differently."
                )
            elif assigned_employee_count == 0:
                warnings.append(
                    "No component assignments — ERA scores will be identical "
                    "until employees own components."
                )

    if demo_mode:
        warnings.append("demo_data")

    return warnings
