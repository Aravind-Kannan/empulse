"""ERA Step 12 mitigation tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.era import EraDimensions, EraEmployeeMetrics
from app.services.era.evidence_ids import normalize_evidence_ids, stable_evidence_id
from app.services.era_mitigations import (
    MITIGATION_RULES,
    attach_suggested_mitigations,
    count_open_mitigations,
    evaluate_mitigation_rules,
    update_evidence_mitigation,
)
from app.services.era.tests.test_scoring_engine import _alice_signals
from app.services.era.engine import score_employee
from app.services.era.normalize import TenantPercentiles

from tests.conftest import add_employee


@pytest.fixture()
def client():
    return TestClient(app)


def _high_k_metric(*, departure_watchlist: bool = False) -> EraEmployeeMetrics:
    signals = _alice_signals(
        name="Frank Osei",
        employee_id="emp-frank",
        email="frank.osei@acme.com",
        role="Support",
        max_github_ownership_pct=90.0,
        spof_component_count=2,
    )
    result = score_employee(signals, TenantPercentiles())
    dimensions = EraDimensions(**result.dimensions)
    dimensions = dimensions.model_copy(update={"knowledge": 75.0})
    return EraEmployeeMetrics(
        employee_id=signals.employee_id,
        name=signals.name,
        role=signals.role,
        email=signals.email,
        unresolved_issues=signals.unresolved_issues,
        open_tasks=signals.open_tasks,
        undocumented_solved_incidents=signals.undocumented_solved_incidents,
        codebase_share_pct=signals.codebase_share_pct,
        risk_factor_score=result.composite,
        risk_level=result.risk_level,
        dimensions=dimensions,
        departure_watchlist=departure_watchlist,
    )


def test_stable_evidence_id_is_deterministic():
    first = stable_evidence_id(
        dimension="knowledge",
        title="SPOF on Payment Gateway",
        component_id="comp-payments",
    )
    second = stable_evidence_id(
        dimension="knowledge",
        title="SPOF on Payment Gateway",
        component_id="comp-payments",
    )
    assert first == second
    assert first.startswith("ev-")


def test_normalize_evidence_ids_replaces_legacy_ids():
    items = normalize_evidence_ids(
        [
            {
                "id": "emp-1-knowledge-old-0",
                "dimension": "knowledge",
                "title": "High ownership",
                "description": "x",
                "impact_points": 20.0,
                "sources": [],
            }
        ]
    )
    assert items[0]["id"].startswith("ev-")


def test_frank_high_k_triggers_codeowners_rule(db, tenant):
    metric = _high_k_metric()
    items = evaluate_mitigation_rules(
        metric,
        db=db,
        tenant_id=tenant.id,
        employee=None,
        backup_candidate_count=0,
    )
    actions = {item.title for item in items}
    assert "Add backup owner in CODEOWNERS" in actions


def test_frank_with_backup_triggers_pairing_rule(db, tenant):
    metric = _high_k_metric()
    items = evaluate_mitigation_rules(
        metric,
        db=db,
        tenant_id=tenant.id,
        employee=None,
        backup_candidate_count=2,
    )
    actions = {item.title for item in items}
    assert "Pair on next 2 PRs with backup engineer" in actions
    assert "Add backup owner in CODEOWNERS" not in actions


def test_high_severity_evidence_gets_suggested_mitigation():
    items = attach_suggested_mitigations(
        [
            {
                "dimension": "knowledge",
                "severity": "high",
                "title": "SPOF ownership",
                "impact_points": 30,
            }
        ]
    )
    assert items[0]["suggested_mitigation"] == "Add backup owner in CODEOWNERS"


def test_patch_mitigation_persists(db, tenant):
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-mit-001",
        name="Mit Engineer",
        email="mit@acme.com",
    )
    evidence_id = stable_evidence_id(
        dimension="mitigation",
        title="Add backup owner in CODEOWNERS",
    )
    update_evidence_mitigation(
        db,
        tenant.id,
        employee.id,
        evidence_id,
        mitigation_status="open",
        suggested_mitigation="Add backup owner in CODEOWNERS",
    )
    row = update_evidence_mitigation(
        db,
        tenant.id,
        employee.id,
        evidence_id,
        mitigation_status="done",
    )
    assert row.mitigation_status == "done"

    row_again = update_evidence_mitigation(
        db,
        tenant.id,
        employee.id,
        evidence_id,
        mitigation_status="done",
    )
    assert row_again.mitigation_status == "done"


def test_dismissed_hidden_from_open_count(db, tenant):
    items = evaluate_mitigation_rules(
        _high_k_metric(),
        db=db,
        tenant_id=tenant.id,
        employee=None,
        backup_candidate_count=0,
    )
    open_count = count_open_mitigations(items)
    assert open_count >= 1
    dismissed = [item.model_copy(update={"mitigation_status": "dismissed"}) for item in items]
    assert count_open_mitigations(dismissed) < open_count


def test_rule_catalog_has_expected_entries():
    assert len(MITIGATION_RULES) >= 5
