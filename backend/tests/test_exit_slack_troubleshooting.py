"""Slack troubleshooting filtering for exit handover section 3."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from app.models.operational import EmployeeIdentity
from app.services.exit_service import _compile_slack_troubleshooting
from app.services.slack_types import (
    SlackEmployeeSignals,
    SlackMessageRecord,
    SlackThreadEvidence,
    SlackThreadRecord,
)

from tests.conftest import add_employee


def _thread(
    *,
    channel_name: str = "general",
    parent_text: str = "standup notes",
    user_id: str = "U123",
    is_incident_channel: bool = False,
    resolved_at: datetime | None = None,
    resolved_by_employee_id: str | None = None,
) -> SlackThreadRecord:
    return SlackThreadRecord(
        channel_id="C1",
        channel_name=channel_name,
        thread_ts="1.0",
        parent_text=parent_text,
        messages=[
            SlackMessageRecord(ts="1.0", user_id=user_id, text=parent_text),
            SlackMessageRecord(ts="1.1", user_id=user_id, text="follow-up"),
            SlackMessageRecord(ts="1.2", user_id="U999", text="ack"),
        ],
        is_incident_channel=is_incident_channel,
        resolved_at=resolved_at,
        resolved_by_employee_id=resolved_by_employee_id,
        thread_url="https://example.slack.com/thread",
    )


def test_compile_slack_troubleshooting_ignores_casual_messages(db, tenant):
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-slack-filter",
        name="Bob Lee",
        email="bob@acme.com",
    )
    db.add(
        EmployeeIdentity(
            tenant_id=tenant.id,
            employee_id=employee.id,
            provider="slack",
            provider_username_or_id="U123",
        )
    )
    db.commit()

    casual = _thread(
        channel_name="random",
        parent_text="This deploy failed with a timeout error in CI",
    )
    incident = _thread(
        channel_name="incident-payments",
        parent_text="SEV2 outage on checkout API",
        is_incident_channel=True,
    )

    with (
        patch(
            "app.services.exit_service.hydrate_integration_telemetry",
            return_value=None,
        ),
        patch(
            "app.services.exit_service.get_slack_employee_signals",
            return_value=None,
        ),
        patch(
            "app.services.exit_service.get_cached_slack_threads",
            return_value=[casual, incident],
        ),
    ):
        lines = _compile_slack_troubleshooting(
            db,
            tenant.id,
            employee,
            graph_snippets=[],
            owned_names=["Payments API"],
        )

    joined = "\n".join(lines)
    assert "timeout error in CI" not in joined
    assert "incident-payments" in joined
    assert "SEV2 outage" in joined


def test_compile_slack_troubleshooting_uses_telemetry_evidence(db, tenant):
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-slack-evidence",
        name="Carol Wu",
        email="carol@acme.com",
    )

    signals = SlackEmployeeSignals(
        employee_id=employee.id,
        thread_evidence=[
            SlackThreadEvidence(
                thread_url="https://example.slack.com/oncall",
                title="Redis failover playbook gap",
                channel_name="#incident-platform",
                kind="on_call",
            )
        ],
    )

    with (
        patch(
            "app.services.exit_service.hydrate_integration_telemetry",
            return_value=None,
        ),
        patch(
            "app.services.exit_service.get_slack_employee_signals",
            return_value=signals,
        ),
        patch(
            "app.services.exit_service.get_cached_slack_threads",
            return_value=[],
        ),
    ):
        lines = _compile_slack_troubleshooting(
            db,
            tenant.id,
            employee,
            graph_snippets=[],
            owned_names=[],
        )

    joined = "\n".join(lines)
    assert "incident-platform" in joined
    assert "on call" in joined
    assert "Redis failover playbook gap" in joined


def test_compile_slack_troubleshooting_filters_unrelated_cognee_chunks(db, tenant):
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-slack-graph",
        name="Dana Fox",
        email="dana@acme.com",
    )

    snippets = [
        "Random slack message about lunch plans in #general.",
        "Dana Fox resolved SEV2 outage in #incident-checkout with rollback mitigation.",
    ]

    with (
        patch(
            "app.services.exit_service.hydrate_integration_telemetry",
            return_value=None,
        ),
        patch(
            "app.services.exit_service.get_slack_employee_signals",
            return_value=None,
        ),
        patch(
            "app.services.exit_service.get_cached_slack_threads",
            return_value=[],
        ),
    ):
        lines = _compile_slack_troubleshooting(
            db,
            tenant.id,
            employee,
            graph_snippets=snippets,
            owned_names=["Checkout"],
        )

    joined = "\n".join(lines)
    assert "lunch plans" not in joined
    assert "SEV2 outage" in joined
