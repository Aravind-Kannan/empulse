"""SPOF reason payloads on KRA graph nodes."""

from __future__ import annotations

import pytest

from app.services.integration_telemetry import reset_telemetry_for_tests
from app.services.kra_analytics import _build_graph, _compute_spof_reasons
from app.schemas.kra import KraLink


@pytest.fixture(autouse=True)
def _reset():
    reset_telemetry_for_tests()
    yield
    reset_telemetry_for_tests()


class _EmployeeView:
    def __init__(self, emp_id: str, name: str, role: str = "Team Member"):
        self.id = emp_id
        self.name = name
        self.role = role


class _ComponentView:
    def __init__(self, comp_id: str, name: str):
        self.id = comp_id
        self.name = name
        self.description = ""


class _AssignmentView:
    def __init__(self, employee_id: str, component_id: str, share: float):
        self.employee_id = employee_id
        self.component_id = component_id
        self.codebase_share_pct = share


def test_compute_spof_reasons_dominant_owner_with_two_owners():
    reasons = _compute_spof_reasons(
        "comp-docs",
        structural_spof=False,
        github_verified=True,
        bus_factor=2,
        owner_count=2,
        links=[
            KraLink(source="emp-a", target="comp-docs", codebase_share_pct=90.0),
            KraLink(source="emp-b", target="comp-docs", codebase_share_pct=10.0),
        ],
        employee_names={"emp-a": "Aravind", "emp-b": "Sanyog"},
        github_synced=True,
    )
    kinds = {reason.kind for reason in reasons}
    assert "dominant_owner" in kinds
    dominant = next(reason for reason in reasons if reason.kind == "dominant_owner")
    assert "Aravind" in dominant.detail
    assert "90%" in dominant.detail
    assert "Sanyog 10%" in dominant.detail


def test_compute_spof_reasons_low_bus_factor():
    reasons = _compute_spof_reasons(
        "comp-docs",
        structural_spof=False,
        github_verified=True,
        bus_factor=1,
        owner_count=2,
        links=[
            KraLink(source="emp-a", target="comp-docs", codebase_share_pct=70.0),
            KraLink(source="emp-b", target="comp-docs", codebase_share_pct=15.0),
        ],
        employee_names={"emp-a": "Aravind", "emp-b": "Sanyog"},
        github_synced=True,
    )
    kinds = {reason.kind for reason in reasons}
    assert "low_bus_factor" in kinds
    assert "dominant_owner" not in kinds


def test_build_graph_attaches_spof_reasons_for_single_owner():
    graph = _build_graph(
        [_EmployeeView("emp-a", "Aravind Kannan"), _EmployeeView("emp-b", "Sanyog Kave")],
        [_ComponentView("comp-docs", "Notion Docs")],
        [_AssignmentView("emp-a", "comp-docs", 100.0)],
    )
    node = next(node for node in graph.nodes if node.id == "comp-docs")
    assert node.is_spof is True
    assert any(reason.kind == "single_owner" for reason in node.spof_reasons)
