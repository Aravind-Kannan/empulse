"""Employee delete cleans ERA and other dependents before FK delete."""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch

from app.models.operational import (
    Component,
    EraAlert,
    EraDepartureOrphanBaseline,
    EraEvidenceMitigation,
    EraRiskSnapshot,
    Employee,
)
from app.services.role_evolution import delete_employee_with_cognee_sync

from tests.conftest import add_employee


def test_delete_employee_clears_era_dependents(db, tenant):
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-delete-era",
        name="Aravind Kannan",
        email="aravind@acme.com",
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
        EraRiskSnapshot(
            tenant_id=tenant.id,
            employee_id=employee.id,
            snapshot_date=date.today(),
            risk_factor_score=0.5,
            risk_level="medium",
        )
    )
    db.add(
        EraEvidenceMitigation(
            tenant_id=tenant.id,
            employee_id=employee.id,
            evidence_id="ev-1",
            mitigation_status="open",
        )
    )
    db.add(
        EraDepartureOrphanBaseline(
            tenant_id=tenant.id,
            employee_id=employee.id,
            component_id="comp-auth",
            file_path="src/main.py",
            doa_score=0.8,
        )
    )
    db.add(
        EraAlert(
            tenant_id=tenant.id,
            rule_id="high-risk",
            severity="high",
            title="Risk alert",
            description="test",
            employee_id=employee.id,
            dedupe_key="risk:emp-delete-era",
        )
    )
    db.commit()

    with patch(
        "app.services.role_evolution.ingest_org_chart_to_cognee",
        new=AsyncMock(
            return_value={
                "cognee_dataset": "empulse_tenant_test",
                "graph_nodes_created": 0,
                "graph_edges_created": 0,
            }
        ),
    ):
        result = asyncio.run(
            delete_employee_with_cognee_sync(db, employee.id, tenant)
        )

    assert result.employee_id == employee.id
    assert (
        db.query(Employee)
        .filter(Employee.id == employee.id, Employee.tenant_id == tenant.id)
        .one_or_none()
        is None
    )
    assert (
        db.query(EraRiskSnapshot)
        .filter(
            EraRiskSnapshot.employee_id == employee.id,
            EraRiskSnapshot.tenant_id == tenant.id,
        )
        .count()
        == 0
    )
    assert (
        db.query(EraEvidenceMitigation)
        .filter(
            EraEvidenceMitigation.employee_id == employee.id,
            EraEvidenceMitigation.tenant_id == tenant.id,
        )
        .count()
        == 0
    )
    assert (
        db.query(EraDepartureOrphanBaseline)
        .filter(
            EraDepartureOrphanBaseline.employee_id == employee.id,
            EraDepartureOrphanBaseline.tenant_id == tenant.id,
        )
        .count()
        == 0
    )
    alert = (
        db.query(EraAlert)
        .filter(
            EraAlert.dedupe_key == "risk:emp-delete-era",
            EraAlert.tenant_id == tenant.id,
        )
        .one()
    )
    assert alert.employee_id is None
