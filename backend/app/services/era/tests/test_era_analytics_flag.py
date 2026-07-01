"""ERA analytics orchestrator tests for v1/v2 feature flag."""

from __future__ import annotations

from unittest.mock import patch

from app.schemas.org import ACME_ORG_CHART
from app.services.era_analytics import _fallback_acme_metrics, _metrics_from_counts


def test_v1_formula_unchanged_when_flag_off():
    with patch("app.services.era_analytics.get_settings") as mock_settings:
        mock_settings.return_value.era_v2_scoring = False
        metrics = _fallback_acme_metrics()
    assert metrics
    assert all(item.dimensions is None for item in metrics)
    assert all(not item.evidence for item in metrics)


def test_v2_returns_dimensions_when_flag_on():
    with patch("app.services.era_analytics.get_settings") as mock_settings:
        mock_settings.return_value.era_v2_scoring = True
        metrics = _fallback_acme_metrics()
    ic_metrics = [item for item in metrics if item.role not in ("Manager",)]
    assert ic_metrics
    assert all(item.dimensions is not None for item in ic_metrics)
    assert all(len(item.evidence) <= 5 for item in ic_metrics)


def test_leadership_not_in_v2_acme_list():
    with patch("app.services.era_analytics.get_settings") as mock_settings:
        mock_settings.return_value.era_v2_scoring = True
        metrics = _fallback_acme_metrics()
    names = {item.name for item in metrics}
    assert "Alice Chen" not in names
    assert len(metrics) == len(ACME_ORG_CHART.employees) - 1


def test_legacy_fields_populated_in_v2():
    with patch("app.services.era_analytics.get_settings") as mock_settings:
        mock_settings.return_value.era_v2_scoring = True
        metrics = _fallback_acme_metrics()
    sample = metrics[0]
    assert sample.unresolved_issues >= 0
    assert sample.open_tasks >= 0
    assert sample.codebase_share_pct >= 0
    assert sample.risk_factor_score >= 0
    assert sample.risk_level in {"low", "medium", "high"}


def test_v1_legacy_score_formula():
    metric = _metrics_from_counts(
        employee_id="emp-eng-001",
        name="Ben Rivera",
        role="Engineer",
        email="ben.rivera@acme.com",
        unresolved_issues=3,
        open_tasks=5,
        codebase_share_pct=40.0,
        undocumented_solved_incidents=2,
    )
    expected = min(100.0, 3 * 5 + 5 * 3 + 2 * 10 + 40 * 0.4)
    assert metric.risk_factor_score == round(expected, 1)
