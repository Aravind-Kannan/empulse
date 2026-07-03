"""KRA ownership link tests — no mixed sources, normalized org-chart shares."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.integration_telemetry import reset_telemetry_for_tests
from app.services.kra_analytics import (
    _build_graph,
    _normalize_share_percentages,
    _ownership_links_for_component,
)


class _ComponentView:
    def __init__(self, comp_id: str, name: str, description: str = ""):
        self.id = comp_id
        self.name = name
        self.description = description


class _AssignmentView:
    def __init__(self, employee_id: str, component_id: str, share: float):
        self.employee_id = employee_id
        self.component_id = component_id
        self.codebase_share_pct = share


def test_normalize_share_percentages_rescales_over_100():
    normalized = _normalize_share_percentages(
        {"emp-a": 100.0, "emp-b": 20.0},
    )
    assert normalized["emp-a"] == 83.3
    assert normalized["emp-b"] == 16.7
    assert round(sum(normalized.values()), 1) == 100.0


def test_github_managed_component_uses_github_only_not_assignments():
    component = _ComponentView(
        "comp-docs",
        "empulse / notion-docs",
        "AUTO:github:Aravind-Kannan/empulse:notion-docs/",
    )
    assignments = [
        _AssignmentView("emp-backup", "comp-docs", 20.0),
        _AssignmentView("emp-primary", "comp-docs", 100.0),
    ]
    github_ownership = {
        "comp-docs": {"emp-primary": 100.0},
    }

    links = _ownership_links_for_component(
        component,
        assignments,
        github_ownership,
        github_synced=True,
    )

    assert len(links) == 1
    assert links[0].source == "emp-primary"
    assert links[0].codebase_share_pct == 100.0
    assert links[0].ownership_source == "github"


def test_org_chart_assignments_normalize_when_no_github_telemetry():
    component = _ComponentView(
        "comp-docs",
        "empulse / notion-docs",
        "AUTO:github:Aravind-Kannan/empulse:notion-docs/",
    )
    assignments = [
        _AssignmentView("emp-a", "comp-docs", 100.0),
        _AssignmentView("emp-b", "comp-docs", 20.0),
    ]

    links = _ownership_links_for_component(
        component,
        assignments,
        {},
        github_synced=True,
    )

    assert len(links) == 2
    assert links[0].ownership_source == "org_chart"
    shares = {link.source: link.codebase_share_pct for link in links}
    assert round(sum(shares.values()), 1) == 100.0


def test_build_graph_does_not_exceed_100_for_manual_component():
    reset_telemetry_for_tests()
    graph = _build_graph(
        [SimpleNamespace(id="emp-a", name="A", role="Team Member")],
        [_ComponentView("comp-manual", "Auth Service", "Owned by platform")],
        [_AssignmentView("emp-a", "comp-manual", 100.0)],
    )
    shares = [
        link.codebase_share_pct
        for link in graph.links
        if link.target == "comp-manual"
    ]
    assert sum(shares) == 100.0
