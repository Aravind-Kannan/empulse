"""ERA daily risk snapshots and trend calculations (Step 11)."""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.operational import Employee, EraRiskSnapshot, EraTeamHealthSnapshot
from app.schemas.era import (
    EraEmployeeMetrics,
    EraManagerRollupReport,
    EraManagerRollupResponse,
    EraRiskHistoryPoint,
)
from app.services.role_utils import is_leadership_role

logger = logging.getLogger(__name__)

SNAPSHOT_VERSION = 1
RETENTION_DAYS = 365


def trend_7d(current: float, snapshots: list[float]) -> float | None:
    if len(snapshots) < 2:
        return None
    week_ago = snapshots[-7] if len(snapshots) >= 7 else snapshots[0]
    return round(current - week_ago, 1)


def _utc_today() -> date:
    return datetime.now(UTC).date()


def _dimensions_to_json(metric: EraEmployeeMetrics) -> dict:
    if not metric.dimensions:
        return {}
    return {
        "knowledge": metric.dimensions.knowledge,
        "operational": metric.dimensions.operational,
        "documentation": metric.dimensions.documentation,
        "structural": metric.dimensions.structural,
        "burnout": metric.dimensions.burnout,
        "partial": metric.dimensions.partial,
    }


def _upsert_snapshot(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    metric: EraEmployeeMetrics,
    snapshot_date: date,
    computed_at: datetime,
) -> None:
    values = {
        "tenant_id": tenant_id,
        "employee_id": metric.employee_id,
        "snapshot_date": snapshot_date,
        "risk_factor_score": metric.risk_factor_score,
        "risk_level": metric.risk_level,
        "dimensions_json": _dimensions_to_json(metric),
        "snapshot_version": SNAPSHOT_VERSION,
        "computed_at": computed_at,
    }
    stmt = insert(EraRiskSnapshot).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_era_risk_snapshot",
        set_={
            "risk_factor_score": values["risk_factor_score"],
            "risk_level": values["risk_level"],
            "dimensions_json": values["dimensions_json"],
            "snapshot_version": values["snapshot_version"],
            "computed_at": values["computed_at"],
        },
    )
    db.execute(stmt)


def prune_old_snapshots(db: Session, tenant_id: uuid.UUID) -> int:
    cutoff = _utc_today() - timedelta(days=RETENTION_DAYS)
    deleted = (
        db.query(EraRiskSnapshot)
        .filter(
            EraRiskSnapshot.tenant_id == tenant_id,
            EraRiskSnapshot.snapshot_date < cutoff,
        )
        .delete(synchronize_session=False)
    )
    return deleted


def snapshot_era_metrics(db: Session, tenant) -> int:
    """Persist today's ERA scores for each active employee (idempotent upsert)."""
    from app.services.era_analytics import get_era_metrics
    from app.services.era.org_health import compute_org_health
    from app.services.github_orphans import count_orphan_files, orphan_delta_90d

    response = get_era_metrics(db, tenant)
    snapshot_date = _utc_today()
    computed_at = datetime.now(UTC)
    count = 0
    for metric in response.employees:
        if metric.excluded:
            continue
        _upsert_snapshot(
            db,
            tenant_id=tenant.id,
            metric=metric,
            snapshot_date=snapshot_date,
            computed_at=computed_at,
        )
        count += 1

    health = compute_org_health(db, tenant.id)
    orphan_count = count_orphan_files(db, tenant.id)
    orphan_delta = orphan_delta_90d(db, tenant.id)
    _upsert_team_health_snapshot(
        db,
        tenant_id=tenant.id,
        snapshot_date=snapshot_date,
        org_health_score=health.score,
        orphan_file_count=orphan_count,
        orphan_delta_90d=orphan_delta,
        computed_at=computed_at,
    )

    prune_old_snapshots(db, tenant.id)
    prune_old_team_health_snapshots(db, tenant.id)
    db.commit()
    return count


def refresh_era_after_integration_sync(db: Session, tenant_id: uuid.UUID) -> None:
    """Persist ERA snapshots and evaluate alerts after integration sync completes."""
    from app.models.tenant import Tenant
    from app.services.era_alerts import sync_era_alerts
    from app.services.era_analytics import get_era_metrics

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).one_or_none()
    if tenant is None:
        logger.warning("ERA post-sync refresh skipped: tenant %s not found", tenant_id)
        return

    try:
        snapshot_era_metrics(db, tenant)
    except Exception:
        logger.exception("ERA snapshot failed after integration sync (tenant=%s)", tenant_id)

    try:
        demo_mode = get_era_metrics(db, tenant).demo_mode
        sync_era_alerts(db, tenant, demo_mode=demo_mode)
    except Exception:
        logger.exception("ERA alert sync failed after integration sync (tenant=%s)", tenant_id)


def _upsert_team_health_snapshot(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    snapshot_date: date,
    org_health_score: float,
    orphan_file_count: int,
    orphan_delta_90d: int,
    computed_at: datetime,
) -> None:
    values = {
        "tenant_id": tenant_id,
        "snapshot_date": snapshot_date,
        "org_health_score": org_health_score,
        "orphan_file_count": orphan_file_count,
        "orphan_delta_90d": orphan_delta_90d,
        "computed_at": computed_at,
    }
    stmt = insert(EraTeamHealthSnapshot).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_era_team_health_snapshot",
        set_={
            "org_health_score": values["org_health_score"],
            "orphan_file_count": values["orphan_file_count"],
            "orphan_delta_90d": values["orphan_delta_90d"],
            "computed_at": values["computed_at"],
        },
    )
    db.execute(stmt)


def prune_old_team_health_snapshots(db: Session, tenant_id: uuid.UUID) -> int:
    cutoff = _utc_today() - timedelta(days=RETENTION_DAYS)
    return (
        db.query(EraTeamHealthSnapshot)
        .filter(
            EraTeamHealthSnapshot.tenant_id == tenant_id,
            EraTeamHealthSnapshot.snapshot_date < cutoff,
        )
        .delete(synchronize_session=False)
    )


def _scores_by_employee(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    days: int,
    employee_ids: list[str] | None = None,
) -> dict[str, list[float]]:
    cutoff = _utc_today() - timedelta(days=days - 1)
    query = (
        db.query(EraRiskSnapshot)
        .filter(
            EraRiskSnapshot.tenant_id == tenant_id,
            EraRiskSnapshot.snapshot_date >= cutoff,
        )
        .order_by(EraRiskSnapshot.snapshot_date.asc())
    )
    if employee_ids is not None:
        query = query.filter(EraRiskSnapshot.employee_id.in_(employee_ids))
    rows = query.all()
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[row.employee_id].append(row.risk_factor_score)
    return grouped


def apply_trends_to_employees(
    db: Session,
    tenant_id: uuid.UUID,
    employees: list[EraEmployeeMetrics],
) -> list[EraEmployeeMetrics]:
    active_ids = [employee.employee_id for employee in employees if not employee.excluded]
    if not active_ids:
        return employees
    history = _scores_by_employee(db, tenant_id, days=30, employee_ids=active_ids)
    updated: list[EraEmployeeMetrics] = []
    for employee in employees:
        if employee.excluded:
            updated.append(employee)
            continue
        scores = history.get(employee.employee_id, [])
        trend = trend_7d(employee.risk_factor_score, scores)
        updated.append(employee.model_copy(update={"trend_7d": trend}))
    return updated


def team_avg_trend_7d(
    db: Session,
    tenant_id: uuid.UUID,
    current_avg: float,
) -> float | None:
    history = get_team_risk_history(db, tenant_id, days=30)
    scores = [point.risk_factor_score for point in history]
    return trend_7d(current_avg, scores)


def get_employee_risk_history(
    db: Session,
    tenant_id: uuid.UUID,
    employee_id: str,
    *,
    days: int = 30,
) -> list[EraRiskHistoryPoint]:
    cutoff = _utc_today() - timedelta(days=days - 1)
    rows = (
        db.query(EraRiskSnapshot)
        .filter(
            EraRiskSnapshot.tenant_id == tenant_id,
            EraRiskSnapshot.employee_id == employee_id,
            EraRiskSnapshot.snapshot_date >= cutoff,
        )
        .order_by(EraRiskSnapshot.snapshot_date.asc())
        .all()
    )
    return [
        EraRiskHistoryPoint(
            snapshot_date=row.snapshot_date.isoformat(),
            risk_factor_score=row.risk_factor_score,
        )
        for row in rows
    ]


def get_team_risk_history(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    days: int = 30,
) -> list[EraRiskHistoryPoint]:
    cutoff = _utc_today() - timedelta(days=days - 1)
    risk_rows = (
        db.query(
            EraRiskSnapshot.snapshot_date,
            func.avg(EraRiskSnapshot.risk_factor_score).label("avg_score"),
        )
        .filter(
            EraRiskSnapshot.tenant_id == tenant_id,
            EraRiskSnapshot.snapshot_date >= cutoff,
        )
        .group_by(EraRiskSnapshot.snapshot_date)
        .order_by(EraRiskSnapshot.snapshot_date.asc())
        .all()
    )
    health_rows = (
        db.query(EraTeamHealthSnapshot)
        .filter(
            EraTeamHealthSnapshot.tenant_id == tenant_id,
            EraTeamHealthSnapshot.snapshot_date >= cutoff,
        )
        .order_by(EraTeamHealthSnapshot.snapshot_date.asc())
        .all()
    )
    health_by_date = {row.snapshot_date: row for row in health_rows}
    points: list[EraRiskHistoryPoint] = []
    for row in risk_rows:
        health = health_by_date.get(row.snapshot_date)
        points.append(
            EraRiskHistoryPoint(
                snapshot_date=row.snapshot_date.isoformat(),
                risk_factor_score=round(float(row.avg_score), 1),
                org_health_score=health.org_health_score if health else None,
                orphan_file_count=health.orphan_file_count if health else None,
            )
        )
    return points


def manager_team_rollup(
    db: Session,
    tenant,
    manager_id: str,
) -> EraManagerRollupResponse | None:
    manager = (
        db.query(Employee)
        .filter(Employee.tenant_id == tenant.id, Employee.id == manager_id)
        .one_or_none()
    )
    if manager is None:
        return None

    reports = (
        db.query(Employee)
        .filter(Employee.tenant_id == tenant.id, Employee.manager_id == manager_id)
        .all()
    )
    if not reports:
        return EraManagerRollupResponse(
            computed_at=datetime.now(UTC),
            manager_id=manager_id,
            manager_name=manager.name,
            team_avg_risk=0.0,
            high_risk_report_count=0,
            manager_exposure_bonus=0,
            reports=[],
        )

    from app.services.era_analytics import get_era_metrics

    metrics_response = get_era_metrics(db, tenant)
    metrics_by_id = {
        employee.employee_id: employee for employee in metrics_response.employees
    }

    report_metrics: list[EraManagerRollupReport] = []
    risk_scores: list[float] = []
    high_risk_count = 0
    for report in reports:
        if is_leadership_role(report.role):
            continue
        metric = metrics_by_id.get(report.id)
        if metric is None or metric.excluded:
            continue
        risk_scores.append(metric.risk_factor_score)
        if metric.risk_level == "high":
            high_risk_count += 1
        report_metrics.append(
            EraManagerRollupReport(
                employee_id=report.id,
                name=report.name,
                role=report.role,
                risk_factor_score=metric.risk_factor_score,
                risk_level=metric.risk_level,
                trend_7d=metric.trend_7d,
            )
        )

    team_avg = round(sum(risk_scores) / len(risk_scores), 1) if risk_scores else 0.0
    exposure_bonus = min(15, high_risk_count * 5)
    return EraManagerRollupResponse(
        computed_at=datetime.now(UTC),
        manager_id=manager_id,
        manager_name=manager.name,
        team_avg_risk=team_avg,
        high_risk_report_count=high_risk_count,
        manager_exposure_bonus=exposure_bonus,
        reports=report_metrics,
    )
