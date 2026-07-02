"""Notion telemetry tests (ERA Step 06)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.models.operational import Assignment, Component, Employee
from app.schemas.integrations import NotionConfigRequest
from app.services.integration_config_store import save_notion_config
from app.services.integration_sync import analyze_notion_payload, GraphNotionPage
from app.services.integration_telemetry import (
    apply_notion_telemetry,
    get_notion_component_sources,
    get_notion_employee_signals,
    has_notion_sync,
    reset_telemetry_for_tests,
)
from app.services.notion_client import load_fixture_document_inventory
from app.services.notion_evidence import build_notion_evidence_items
from app.services.notion_telemetry import (
    compute_notion_telemetry,
    inventory_dicts_to_records,
)
from app.services.kra_analytics import get_kra_graph

from tests.conftest import add_employee


@pytest.fixture(autouse=True)
def _reset():
    reset_telemetry_for_tests()
    yield
    reset_telemetry_for_tests()


def _seed(db, tenant_id: uuid.UUID):
    for employee_id, email in (
        ("emp-ben", "ben@acme.com"),
        ("emp-cara", "cara@acme.com"),
        ("emp-frank", "frank.osei@acme.com"),
    ):
        add_employee(db, tenant_id, employee_id=employee_id, name=employee_id, email=email)

    for component_id, name, criticality in (
        ("comp-payments", "Payment Gateway", "tier1_revenue"),
        ("comp-auth", "Auth Service", "tier2_core"),
        ("comp-notifications", "Notification Hub", "tier2_core"),
    ):
        db.add(
            Component(
                id=component_id,
                tenant_id=tenant_id,
                name=name,
                description="",
                criticality=criticality,
            )
        )

    db.add(
        Assignment(
            tenant_id=tenant_id,
            employee_id="emp-ben",
            component_id="comp-payments",
            codebase_share_pct=80.0,
        )
    )
    db.add(
        Assignment(
            tenant_id=tenant_id,
            employee_id="emp-cara",
            component_id="comp-auth",
            codebase_share_pct=70.0,
        )
    )
    db.add(
        Assignment(
            tenant_id=tenant_id,
            employee_id="emp-ben",
            component_id="comp-notifications",
            codebase_share_pct=20.0,
        )
    )
    db.commit()


def _fixture_snapshot(db, tenant_id: uuid.UUID, *, github_active: set[str] | None = None):
    pages, people_expertise = load_fixture_document_inventory()
    employees = db.query(Employee).filter(Employee.tenant_id == tenant_id).all()
    email_to_employee = {employee.email.lower(): employee.id for employee in employees}
    docs = inventory_dicts_to_records(pages, email_to_employee=email_to_employee)
    return compute_notion_telemetry(
        db,
        tenant_id,
        docs,
        people_expertise=people_expertise,
        components_with_github_activity=github_active or {"comp-payments", "comp-notifications"},
        now=datetime(2026, 7, 1, tzinfo=UTC),
    )


def test_doc_gap_and_stale_runbook_detection(db, tenant):
    _seed(db, tenant.id)
    snapshot = _fixture_snapshot(db, tenant.id)
    apply_notion_telemetry(db, tenant.id, snapshot)
    db.commit()

    ben_signals = get_notion_employee_signals("emp-ben")
    assert ben_signals is not None
    assert ben_signals.components_without_docs >= 1

    evidence = build_notion_evidence_items(
        "emp-ben",
        "Ben Rivera",
        notion_connected=True,
        component_names={"comp-payments": "Payment Gateway"},
    )
    titles = " ".join(item["title"] for item in evidence).lower()
    assert "lack notion" in titles or "stale runbook" in titles


def test_stale_runbook_uses_freshest_linked_page(db, tenant):
    _seed(db, tenant.id)
    pages, people_expertise = load_fixture_document_inventory()
    pages = [page for page in pages if page["page_id"] != "notion-page-payments-handover"]
    employees = db.query(Employee).filter(Employee.tenant_id == tenant.id).all()
    email_to_employee = {employee.email.lower(): employee.id for employee in employees}
    docs = inventory_dicts_to_records(pages, email_to_employee=email_to_employee)
    snapshot = compute_notion_telemetry(
        db,
        tenant.id,
        docs,
        people_expertise=people_expertise,
        components_with_github_activity={"comp-payments"},
        now=datetime(2026, 7, 1, tzinfo=UTC),
    )
    ben_signals = snapshot.employee_signals["emp-ben"]
    assert ben_signals.stale_runbook_count >= 1


def test_archived_pages_excluded(db, tenant):
    _seed(db, tenant.id)
    pages, people_expertise = load_fixture_document_inventory()
    pages.append(
        {
            "page_id": "archived-page",
            "title": "Archived Runbook",
            "page_url": "https://www.notion.so/archived",
            "last_edited_at": "2020-01-01T00:00:00Z",
            "component_id": "comp-notifications",
            "owner_emails": ["ben@acme.com"],
            "page_kind": "runbook",
            "is_archived": True,
        }
    )
    employees = db.query(Employee).filter(Employee.tenant_id == tenant.id).all()
    email_to_employee = {employee.email.lower(): employee.id for employee in employees}
    docs = inventory_dicts_to_records(pages, email_to_employee=email_to_employee)
    snapshot = compute_notion_telemetry(
        db,
        tenant.id,
        docs,
        people_expertise=people_expertise,
        components_with_github_activity={"comp-notifications"},
        now=datetime(2026, 7, 1, tzinfo=UTC),
    )
    assert all(not doc.is_archived for doc in snapshot.docs if doc.page_id != "archived-page")
    assert "comp-notifications" not in snapshot.component_sources


def test_kra_uses_real_notion_sources(db, tenant):
    _seed(db, tenant.id)
    snapshot = _fixture_snapshot(db, tenant.id)
    apply_notion_telemetry(db, tenant.id, snapshot)
    db.commit()

    assert has_notion_sync()
    assert "Notion: Payment Gateway Runbook" in get_notion_component_sources("comp-payments")

    graph = get_kra_graph(db, tenant)
    payments_node = next(node for node in graph.nodes if node.id == "comp-payments")
    assert "Notion: Payment Gateway Runbook" in payments_node.documentation_sources


def test_analyze_notion_payload_creates_documented_by_edges(db, tenant):
    _seed(db, tenant.id)
    snapshot = _fixture_snapshot(db, tenant.id)
    from app.services.cognee_ingest import GraphComponent, GraphEmployee

    employee_nodes = {
        "emp-ben": GraphEmployee(
            external_id="emp-ben",
            name="Ben",
            role="Engineer",
            email="ben@acme.com",
            tenure_years=3.0,
        )
    }
    component_nodes = {
        "comp-payments": GraphComponent(
            external_id="comp-payments",
            name="Payment Gateway",
            description="",
            open_tasks_count=0,
            unresolved_incidents=0,
        )
    }
    narrative, data_points, edge_count = analyze_notion_payload(
        employee_nodes,
        component_nodes,
        snapshot.docs,
    )
    assert edge_count >= 1
    assert any(isinstance(node, GraphNotionPage) for node in data_points)
    assert "Living runbook" in narrative


def test_notion_config_round_trip(db, tenant):
    save_notion_config(
        db,
        tenant.id,
        NotionConfigRequest(
            integration_token="secret_test_token",
            database_ids="db-123",
            validated=True,
        ),
    )
    from app.services.integration_config_store import get_notion_config

    config = get_notion_config(db, tenant.id)
    assert config is not None
    assert config.integration_token == "secret_test_token"
