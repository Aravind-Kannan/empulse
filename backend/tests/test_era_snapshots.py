"""ERA Step 11 — snapshot and trend tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

import pytest

from app.models.operational import Employee, EraRiskSnapshot
from app.services.era_snapshots import (
    apply_trends_to_employees,
    snapshot_era_metrics,
    team_avg_trend_7d,
    trend_7d,
)
from app.schemas.era import EraEmployeeMetrics

from tests.conftest import add_employee


def test_trend_7d_requires_two_points():
    assert trend_7d(50.0, [50.0]) is None
    assert trend_7d(55.0, [50.0, 52.0, 54.0]) == 5.0


def test_trend_7d_uses_seventh_point_when_available():
    scores = [float(i) for i in range(1, 10)]
    assert trend_7d(scores[-1], scores) == round(scores[-1] - scores[-7], 1)


def test_snapshot_idempotent_same_day(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-snap-001",
        name="Snapshot Engineer",
        email="snap@acme.com",
    )
    with patch("app.services.era_analytics.get_era_metrics") as mock_metrics:
        mock_metrics.return_value.employees = [
            EraEmployeeMetrics(
                employee_id="emp-snap-001",
                name="Snapshot Engineer",
                role="Engineer",
                email="snap@acme.com",
                unresolved_issues=0,
                open_tasks=0,
                undocumented_solved_incidents=0,
                codebase_share_pct=10.0,
                risk_factor_score=42.0,
                risk_level="medium",
            )
        ]
        first = snapshot_era_metrics(db, tenant)
        second = snapshot_era_metrics(db, tenant)

    assert first == 1
    assert second == 1
    rows = (
        db.query(EraRiskSnapshot)
        .filter(
            EraRiskSnapshot.tenant_id == tenant.id,
            EraRiskSnapshot.employee_id == "emp-snap-001",
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].risk_factor_score == 42.0


def test_apply_trends_to_employees(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-trend-001",
        name="Trend Engineer",
        email="trend@acme.com",
    )
    today = datetime.now(UTC).date()
    db.add(
        EraRiskSnapshot(
            tenant_id=tenant.id,
            employee_id="emp-trend-001",
            snapshot_date=today - timedelta(days=7),
            risk_factor_score=40.0,
            risk_level="medium",
            dimensions_json={},
            computed_at=datetime.now(UTC),
        )
    )
    db.add(
        EraRiskSnapshot(
            tenant_id=tenant.id,
            employee_id="emp-trend-001",
            snapshot_date=today - timedelta(days=1),
            risk_factor_score=45.0,
            risk_level="medium",
            dimensions_json={},
            computed_at=datetime.now(UTC),
        )
    )
    db.commit()

    employees = [
        EraEmployeeMetrics(
            employee_id="emp-trend-001",
            name="Trend Engineer",
            role="Engineer",
            email="trend@acme.com",
            unresolved_issues=0,
            open_tasks=0,
            undocumented_solved_incidents=0,
            codebase_share_pct=10.0,
            risk_factor_score=50.0,
            risk_level="medium",
        )
    ]
    updated = apply_trends_to_employees(db, tenant.id, employees)
    assert updated[0].trend_7d == 10.0


def test_team_avg_trend_7d(db, tenant):
    today = date.today()
    for offset, score in ((7, 30.0), (1, 35.0)):
        employee_id = f"emp-team-{offset}"
        add_employee(
            db,
            tenant.id,
            employee_id=employee_id,
            name=f"Engineer {offset}",
            email=f"eng{offset}@acme.com",
        )
        db.add(
            EraRiskSnapshot(
                tenant_id=tenant.id,
                employee_id=employee_id,
                snapshot_date=today - timedelta(days=offset),
                risk_factor_score=score,
                risk_level="low",
                dimensions_json={},
                computed_at=datetime.now(UTC),
            )
        )
    db.commit()
    assert team_avg_trend_7d(db, tenant.id, 40.0) == 10.0


def test_manager_rollup_excludes_leadership(db, tenant):
    manager = add_employee(
        db,
        tenant.id,
        employee_id="emp-manager",
        name="Alice Manager",
        email="alice@acme.com",
    )
    manager.role = "Manager"
    add_employee(
        db,
        tenant.id,
        employee_id="emp-report",
        name="Ben Engineer",
        email="ben@acme.com",
    )
    report = db.query(Employee).filter_by(id="emp-report").one()
    report.manager_id = "emp-manager"
    db.commit()

    from app.services.era_snapshots import manager_team_rollup

    with patch("app.services.era_analytics.get_era_metrics") as mock_metrics:
        mock_metrics.return_value.employees = [
            EraEmployeeMetrics(
                employee_id="emp-report",
                name="Ben Engineer",
                role="Engineer",
                email="ben@acme.com",
                unresolved_issues=0,
                open_tasks=0,
                undocumented_solved_incidents=0,
                codebase_share_pct=10.0,
                risk_factor_score=80.0,
                risk_level="high",
            )
        ]
        rollup = manager_team_rollup(db, tenant, "emp-manager")

    assert rollup is not None
    assert rollup.high_risk_report_count == 1
    assert rollup.manager_exposure_bonus == 5
    assert len(rollup.reports) == 1
