"""Tests for org anchor DataPoint identity (GraphEmployee, GraphComponent)."""

from __future__ import annotations

from app.services.cognee_ingest import GraphComponent, GraphEmployee


def test_graph_employee_reuses_stable_id_for_same_external_id():
    first = GraphEmployee(
        external_id="emp-00000000-alice",
        name="Alice Chen",
        role="Engineer",
        email="alice@acme.com",
        tenure_years=2.0,
    )
    second = GraphEmployee(
        external_id="emp-00000000-alice",
        name="Alice Chen",
        role="Staff Engineer",
        email="alice@acme.com",
        tenure_years=3.0,
        github_id="gh-alice",
    )

    assert first.id == second.id
    assert first.id == GraphEmployee.id_for("emp-00000000-alice")


def test_graph_employee_differs_by_external_id():
    alice = GraphEmployee(
        external_id="emp-00000000-alice",
        name="Alice",
        role="Engineer",
        email="alice@acme.com",
        tenure_years=1.0,
    )
    bob = GraphEmployee(
        external_id="emp-00000000-bob",
        name="Bob",
        role="Engineer",
        email="bob@acme.com",
        tenure_years=1.0,
    )

    assert alice.id != bob.id


def test_graph_component_reuses_stable_id_for_same_external_id():
    first = GraphComponent(
        external_id="comp-00000000-api",
        name="API",
        description="Core API",
        open_tasks_count=1,
        unresolved_incidents=0,
    )
    second = GraphComponent(
        external_id="comp-00000000-api",
        name="API Gateway",
        description="Core API (renamed)",
        open_tasks_count=2,
        unresolved_incidents=1,
    )

    assert first.id == second.id
    assert first.id == GraphComponent.id_for("comp-00000000-api")
