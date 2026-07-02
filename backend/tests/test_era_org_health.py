"""ERA Step 18 — orphan files and org health tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.models.operational import (
    Component,
    DoaFileSnapshot,
    EraDepartureOrphanBaseline,
    EraTeamHealthSnapshot,
    Employee,
    FileRiskSnapshot,
)
from app.schemas.era import EraEmployeeMetrics
from app.schemas.role_evolution import EmployeeUpdateRequest
from app.services.era.org_health import compute_org_health
from app.services.era_analytics import get_era_metrics
from app.services.era_snapshots import snapshot_era_metrics
from app.services.github_orphans import (
    count_orphan_files,
    list_orphan_files,
    snapshot_departure_orphan_baseline,
)
from app.services.role_evolution import update_employee_with_role_evolution

from tests.conftest import add_employee


def test_departure_baseline_and_orphan_count_increases(db, tenant):
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-orphan-owner",
        name="Orphan Owner",
        email="orphan@acme.com",
    )
    db.add(
        Component(
            id="comp-auth",
            tenant_id=tenant.id,
            name="Auth Service",
            description="",
        )
    )
    now = datetime.now(UTC)
    db.add(
        DoaFileSnapshot(
            tenant_id=tenant.id,
            component_id="comp-auth",
            file_path="src/auth/session.rs",
            employee_id=employee.id,
            doa_score=0.9,
            is_author=True,
            last_touch_at=now - timedelta(days=10),
            decay_score=0.1,
            computed_at=now,
        )
    )
    db.commit()

    created = snapshot_departure_orphan_baseline(db, tenant.id, employee.id)
    assert created == 1
    db.commit()

    assert count_orphan_files(db, tenant.id) == 0

    employee.active = False
    db.commit()

    orphans = list_orphan_files(db, tenant.id)
    assert len(orphans) == 1
    assert orphans[0].file_path == "src/auth/session.rs"


def test_marking_employee_inactive_triggers_baseline(db, tenant):
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-depart",
        name="Departing Engineer",
        email="depart@acme.com",
    )
    db.add(
        Component(
            id="comp-pay",
            tenant_id=tenant.id,
            name="Payments",
            description="",
        )
    )
    now = datetime.now(UTC)
    db.add(
        DoaFileSnapshot(
            tenant_id=tenant.id,
            component_id="comp-pay",
            file_path="payments/handler.ts",
            employee_id=employee.id,
            doa_score=0.82,
            is_author=True,
            last_touch_at=now - timedelta(days=5),
            decay_score=0.1,
            computed_at=now,
        )
    )
    db.commit()

    with patch(
        "app.services.role_evolution.ingest_org_chart_to_cognee",
        new=AsyncMock(
            return_value={
                "cognee_dataset": "test",
                "graph_nodes_created": 0,
                "graph_edges_created": 0,
            }
        ),
    ):
        asyncio.run(
            update_employee_with_role_evolution(
                db,
                employee.id,
                EmployeeUpdateRequest(active=False),
                tenant,
            )
        )

    rows = (
        db.query(EraDepartureOrphanBaseline)
        .filter(EraDepartureOrphanBaseline.tenant_id == tenant.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].file_path == "payments/handler.ts"


def test_org_health_score_in_range(db, tenant):
    for index in range(3):
        add_employee(
            db,
            tenant.id,
            employee_id=f"emp-health-{index}",
            name=f"Health {index}",
            email=f"health{index}@acme.com",
        )
    db.add(
        Component(
            id="comp-auth",
            tenant_id=tenant.id,
            name="Auth",
            description="",
        )
    )
    db.add(
        FileRiskSnapshot(
            tenant_id=tenant.id,
            component_id="comp-auth",
            repo_path="acme/auth",
            file_path="src/main.rs",
            churn_score=5,
            contributor_count=3,
            bus_factor=3,
            quadrant="healthy",
            computed_at=datetime.now(UTC),
        )
    )
    db.commit()

    result = compute_org_health(db, tenant.id)
    assert 0 <= result.score <= 100


def test_team_summary_includes_org_health(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-summary",
        name="Summary Engineer",
        email="summary@acme.com",
    )
    response = get_era_metrics(db, tenant)
    assert 0 <= response.team_summary.org_health_score <= 100
    assert response.team_summary.orphan_file_count >= 0


def test_team_health_snapshot_persists_orphan_count(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-snap-health",
        name="Snap Health",
        email="snaphealth@acme.com",
    )
    with patch("app.services.era_analytics.get_era_metrics") as mock_metrics:
        mock_metrics.return_value = type(
            "Resp",
            (),
            {
                "employees": [
                    EraEmployeeMetrics(
                        employee_id="emp-snap-health",
                        name="Snap Health",
                        role="Engineer",
                        email="snaphealth@acme.com",
                        unresolved_issues=0,
                        open_tasks=0,
                        undocumented_solved_incidents=0,
                        codebase_share_pct=10.0,
                        risk_factor_score=40.0,
                        risk_level="medium",
                    )
                ]
            },
        )()
        snapshot_era_metrics(db, tenant)

    row = (
        db.query(EraTeamHealthSnapshot)
        .filter(EraTeamHealthSnapshot.tenant_id == tenant.id)
        .one()
    )
    assert 0 <= row.org_health_score <= 100
    assert row.orphan_file_count >= 0
