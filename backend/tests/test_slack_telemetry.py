"""Slack telemetry tests (ERA Step 07)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.models.operational import Component, Employee
from app.schemas.integrations import SlackConfigRequest
from app.services.integration_config_store import get_slack_config, save_slack_config
from app.services.integration_sync import analyze_slack_payload, GraphSlackThread
from app.services.integration_telemetry import (
    apply_slack_telemetry,
    get_slack_employee_signals,
    has_slack_sync,
    reset_telemetry_for_tests,
)
from app.services.notion_types import NotionDocRecord
from app.services.slack_client import (
    fetch_slack_incident_threads,
    is_resolved_incident_thread,
    load_fixture_channel_history,
)
from app.services.slack_evidence import build_slack_evidence_items
from app.services.slack_telemetry import compute_slack_telemetry
from app.services.era.signals_builder import build_signals_for_employee

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
    ):
        add_employee(db, tenant_id, employee_id=employee_id, name=employee_id, email=email)
    db.add(
        Component(
            id="comp-payments",
            tenant_id=tenant_id,
            name="Payment Gateway",
            description="",
            criticality="tier1_revenue",
        )
    )
    db.commit()


def _slack_mapping() -> dict[str, str]:
    return {
        "U_BEN": "emp-ben",
        "U_CARA": "emp-cara",
        "U_ALICE": "emp-alice",
    }


def _payments_notion_docs(*, documented: bool) -> list[NotionDocRecord]:
    edited = (
        datetime(2024, 6, 2, tzinfo=UTC)
        if documented
        else datetime(2024, 9, 1, tzinfo=UTC)
    )
    return [
        NotionDocRecord(
            page_id="notion-page-payments-runbook",
            title="Payment Gateway Runbook",
            page_url="https://www.notion.so/payments-runbook",
            last_edited_at=edited,
            component_id="comp-payments",
        )
    ]


def test_bot_only_thread_not_attributed():
    _, threads, _ = load_fixture_channel_history()
    bot_thread = next(
        thread for thread in threads if thread.parent_text == "Bot-only noise thread"
    )
    assert is_resolved_incident_thread(bot_thread, is_incident_channel=True) is None


def test_undocumented_incident_without_notion_update(db, tenant):
    _seed(db, tenant.id)
    _, threads, _ = load_fixture_channel_history()
    snapshot = compute_slack_telemetry(
        db,
        tenant.id,
        threads,
        slack_id_to_employee=_slack_mapping(),
        notion_docs=_payments_notion_docs(documented=False),
        now=datetime(2026, 7, 1, tzinfo=UTC),
    )
    ben = snapshot.employee_signals["emp-ben"]
    assert ben.undocumented_solved_incidents >= 1


def test_documented_incident_within_notion_window(db, tenant):
    _seed(db, tenant.id)
    _, threads, _ = load_fixture_channel_history()
    snapshot = compute_slack_telemetry(
        db,
        tenant.id,
        threads,
        slack_id_to_employee=_slack_mapping(),
        notion_docs=_payments_notion_docs(documented=True),
        now=datetime(2026, 7, 1, tzinfo=UTC),
    )
    ben = snapshot.employee_signals["emp-ben"]
    assert ben.undocumented_solved_incidents == 0


def test_escalation_shadow_signal(db, tenant):
    _seed(db, tenant.id)
    _, threads, _ = load_fixture_channel_history()
    snapshot = compute_slack_telemetry(
        db,
        tenant.id,
        threads,
        slack_id_to_employee=_slack_mapping(),
        now=datetime(2026, 7, 1, tzinfo=UTC),
    )
    ben = snapshot.employee_signals["emp-ben"]
    assert ben.incident_escalation_threads >= 8
    assert snapshot.escalation_warnings


def test_slack_evidence_uses_thread_urls_not_bodies(db, tenant):
    _seed(db, tenant.id)
    _, threads, _ = load_fixture_channel_history()
    snapshot = compute_slack_telemetry(
        db,
        tenant.id,
        threads,
        slack_id_to_employee=_slack_mapping(),
        notion_docs=_payments_notion_docs(documented=False),
        now=datetime(2026, 7, 1, tzinfo=UTC),
    )
    apply_slack_telemetry(snapshot)

    items = build_slack_evidence_items("emp-ben", "Ben Rivera", slack_connected=True)
    assert items
    for item in items:
        assert "sources" in item
        source = item["sources"][0]
        assert source["provider"] == "slack"
        if source.get("url"):
            assert "slack.com/archives/" in source["url"]
        combined = f"{item['title']} {item['description']}".lower()
        assert "mitigated" not in combined
        assert "root cause was" not in combined


def test_signals_use_slack_undocumented_with_notion(db, tenant):
    _seed(db, tenant.id)
    _, threads, _ = load_fixture_channel_history()
    snapshot = compute_slack_telemetry(
        db,
        tenant.id,
        threads,
        slack_id_to_employee=_slack_mapping(),
        notion_docs=_payments_notion_docs(documented=False),
        now=datetime(2026, 7, 1, tzinfo=UTC),
    )
    apply_slack_telemetry(snapshot)
    employee = db.query(Employee).filter(Employee.id == "emp-ben").one()
    employee.assignments = []
    signals = build_signals_for_employee(
        employee,
        all_employees=[employee],
        total_components=1,
        codebase_share_pct=0.0,
        jira_backlog_boost=0,
        slack_connected=True,
        notion_connected=True,
    )
    assert signals.undocumented_solved_incidents >= 1
    assert signals.incident_escalation_threads >= 8


def test_analyze_slack_payload_graph_nodes():
    from app.services.cognee_ingest import GraphComponent, GraphEmployee

    _, threads, _ = load_fixture_channel_history()
    threads[0].resolved_by_employee_id = "emp-ben"
    threads[0].component_id = "comp-payments"
    narrative, nodes, edge_count = analyze_slack_payload(
        {
            "emp-ben": GraphEmployee(
                external_id="emp-ben",
                name="Ben",
                role="Engineer",
                email="ben@acme.com",
                tenure_years=2.0,
            )
        },
        {
            "comp-payments": GraphComponent(
                external_id="comp-payments",
                name="Payment Gateway",
                description="",
                open_tasks_count=0,
                unresolved_incidents=0,
            )
        },
        threads[:1],
    )
    assert edge_count >= 1
    assert any(isinstance(node, GraphSlackThread) for node in nodes)
    assert "Slack incident thread" in narrative


def test_fetch_fixture_threads_without_token():
    threads, users, warnings, stats = fetch_slack_incident_threads(
        SlackConfigRequest(),
        use_fixture=True,
    )
    assert threads
    assert users["U_BEN"] == "ben@acme.com"
    assert not warnings
    assert stats["channels_synced"] >= 1


def test_slack_config_round_trip(db, tenant):
    save_slack_config(
        db,
        tenant.id,
        SlackConfigRequest(
            workspace_url="https://acme.slack.com",
            bot_token="xoxb-test",
            channel_ids="C_INCIDENTS",
            incident_channel_ids="C_INCIDENTS",
            on_call_channel_ids="C_ONCALL",
            validated=True,
        ),
    )
    config = get_slack_config(db, tenant.id)
    assert config is not None
    assert config.incident_channel_ids == "C_INCIDENTS"
    assert has_slack_sync() is False
