"""ERA v2 scoring engine unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.era.composite import compute_composite, risk_level
from app.services.era.dimensions import (
    compute_documentation,
    compute_knowledge,
    compute_operational,
    compute_structural,
)
from app.services.era.engine import score_employee
from app.services.era.normalize import TenantPercentiles, build_tenant_percentiles
from app.services.era.signals import EmployeeSignals
from app.services.era.types import DIMENSION_KEYS
from app.services.role_utils import is_leadership_role

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _alice_signals(**overrides) -> EmployeeSignals:
    base = dict(
        employee_id="emp-alice-chen",
        name="Alice Chen",
        role="Principal Engineer",
        email="alice.chen@acme.com",
        tenure_months=78,
        direct_reports=3,
        unresolved_issues=2,
        open_tasks=6,
        undocumented_solved_incidents=2,
        codebase_share_pct=82.0,
        max_github_ownership_pct=82.0,
        spof_component_count=0,
        assignment_breadth_pct=25.0,
        components_without_docs=1,
        stale_runbook_count=1,
        sprint_points=14,
        after_hours_commits=3,
        github_connected=True,
        identity_coverage_github="confirmed",
    )
    base.update(overrides)
    return EmployeeSignals(**base)


def test_alice_walkthrough_golden_file():
    payload = json.loads((FIXTURES_DIR / "alice_walkthrough.json").read_text())
    dimensions = {key: float(value) for key, value in payload["dimensions"].items()}
    signals = _alice_signals(
        tenure_months=payload["tenure_months"],
        role=payload["role"],
        direct_reports=3,
    )

    composite, _ = compute_composite(
        dimensions,
        signals,
        role_profile=payload["role_profile"],
    )
    assert composite == pytest.approx(payload["expected"]["risk_factor_score"], abs=0.5)
    assert risk_level(composite) == payload["expected"]["risk_level"]


def test_leadership_role_excluded_from_scoring():
    signals = EmployeeSignals(
        employee_id="emp-manager-001",
        name="Alice Chen",
        role="Manager",
        email="alice.chen@acme.com",
        tenure_months=78,
    )
    result = score_employee(signals, TenantPercentiles())
    assert result.excluded is True
    assert result.exclusion_reason == "leadership_role"
    assert is_leadership_role("Manager")


def test_frank_high_knowledge_scores_high():
    """Frank walkthrough: high knowledge concentration → composite >= 75%."""
    dimensions = {
        "knowledge": 95.0,
        "operational": 82.0,
        "documentation": 65.0,
        "structural": 35.0,
        "burnout": 55.0,
    }
    signals = EmployeeSignals(
        employee_id="emp-support-001",
        name="Frank Osei",
        role="Support",
        email="frank.osei@acme.com",
        tenure_months=33,
        max_github_ownership_pct=82.0,
        spof_component_count=2,
        github_connected=True,
        identity_coverage_github="confirmed",
    )
    composite, _ = compute_composite(dimensions, signals, role_profile="ic")
    assert dimensions["knowledge"] >= 75
    assert composite >= 75
    assert risk_level(composite) == "high"


def test_github_missing_marks_knowledge_partial_and_renormalizes():
    signals = _alice_signals(
        github_connected=False,
        identity_coverage_github="missing",
        max_github_ownership_pct=0.0,
        codebase_share_pct=40.0,
        direct_reports=0,
    )
    peer = _alice_signals(
        employee_id="emp-peer",
        name="Peer",
        email="peer@acme.com",
        github_connected=True,
    )
    tenant_stats = build_tenant_percentiles([signals, peer])
    result = score_employee(signals, tenant_stats)
    assert result.partial_dimensions.get("knowledge") is True
    assert result.dimensions["knowledge"] < 80


def test_evidence_limited_to_top_five():
    signals = _alice_signals()
    tenant_stats = build_tenant_percentiles([signals])
    result = score_employee(signals, tenant_stats)
    assert len(result.evidence) <= 5
    impacts = [item["impact_points"] for item in result.evidence]
    assert impacts == sorted(impacts, reverse=True)


def test_documentation_dimension_formula():
    signals = EmployeeSignals(
        employee_id="e1",
        name="Test",
        role="Engineer",
        email="t@acme.com",
        tenure_months=12,
        undocumented_solved_incidents=2,
        components_without_docs=1,
        stale_runbook_count=1,
    )
    result = compute_documentation(signals)
    assert result.score == min(100.0, 2 * 10 + 1 * 12 + 1 * 5)


def test_structural_excludes_leadership_role():
    signals = EmployeeSignals(
        employee_id="e1",
        name="Director",
        role="Director of Engineering",
        email="d@acme.com",
        tenure_months=120,
        direct_reports=8,
    )
    result = compute_structural(signals)
    assert result.excluded is True


def test_operational_uses_percentile_normalization():
    low = EmployeeSignals(
        employee_id="low",
        name="Low",
        role="Engineer",
        email="low@acme.com",
        tenure_months=12,
        unresolved_issues=1,
        open_tasks=2,
    )
    high = EmployeeSignals(
        employee_id="high",
        name="High",
        role="Engineer",
        email="high@acme.com",
        tenure_months=12,
        unresolved_issues=10,
        open_tasks=20,
    )
    tenant_stats = build_tenant_percentiles([low, high])
    low_result = compute_operational(low, tenant_stats)
    high_result = compute_operational(high, tenant_stats)
    assert high_result.score > low_result.score


def test_knowledge_includes_criticality_multiplier():
    signals = EmployeeSignals(
        employee_id="e1",
        name="Owner",
        role="Engineer",
        email="o@acme.com",
        tenure_months=24,
        max_github_ownership_pct=70.0,
        assignment_breadth_pct=20.0,
        max_criticality_multiplier=1.5,
        github_connected=True,
        identity_coverage_github="confirmed",
    )
    result = compute_knowledge(signals, TenantPercentiles(employee_count=2))
    baseline = EmployeeSignals(
        employee_id="e2",
        name="Owner2",
        role="Engineer",
        email="o2@acme.com",
        tenure_months=24,
        max_github_ownership_pct=70.0,
        assignment_breadth_pct=20.0,
        max_criticality_multiplier=1.0,
        github_connected=True,
        identity_coverage_github="confirmed",
    )
    baseline_result = compute_knowledge(baseline, TenantPercentiles(employee_count=2))
    assert result.score > baseline_result.score
