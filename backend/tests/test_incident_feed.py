"""Incident feed prefers persisted sync telemetry over live APIs."""

from datetime import UTC, datetime

from app.services.incident_feed import fetch_live_incidents, invalidate_incident_feed_cache
from app.services.integration_telemetry import (
    apply_jira_telemetry,
    apply_slack_telemetry_with_cache,
    reset_telemetry_for_tests,
)
from app.services.jira_types import JiraIssueActivity
from app.services.slack_telemetry import compute_slack_telemetry
from app.services.slack_types import SlackThreadRecord
from tests.conftest import add_employee


def _open_jira_issue(key: str = "SCRUM-99") -> JiraIssueActivity:
    return JiraIssueActivity(
        issue_key=key,
        issue_type="Bug",
        priority="High",
        status="Open",
        status_category="indeterminate",
        project_key="SCRUM",
        summary="Checkout API 500s",
        updated_at=datetime.now(UTC),
    )


def test_fetch_incidents_uses_persisted_jira_snapshot(db, tenant):
    reset_telemetry_for_tests()
    invalidate_incident_feed_cache(tenant.id)

    apply_jira_telemetry(db, tenant.id, [_open_jira_issue()])
    db.commit()

    reset_telemetry_for_tests()
    invalidate_incident_feed_cache(tenant.id)

    incidents, warnings, sources = fetch_live_incidents(db, tenant.id)
    assert sources["jira"] is True
    assert not warnings
    assert len(incidents) == 1
    assert incidents[0].jira_id == "SCRUM-99"
    assert incidents[0].title == "Checkout API 500s"


def test_fetch_incidents_uses_persisted_slack_snapshot(db, tenant):
    reset_telemetry_for_tests()
    invalidate_incident_feed_cache(tenant.id)
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-slack-feed",
        name="Pager",
        email="pager@example.com",
    )
    db.commit()

    snapshot = compute_slack_telemetry(
        db,
        tenant.id,
        [
            SlackThreadRecord(
                channel_id="CINC",
                channel_name="incident",
                thread_ts="1783017502.455339",
                parent_text="SEV1 prod outage in checkout",
                is_incident_channel=True,
                resolved_by_employee_id=employee.id,
            )
        ],
        slack_id_to_employee={},
    )
    apply_slack_telemetry_with_cache(db, tenant.id, snapshot)
    db.commit()

    reset_telemetry_for_tests()
    invalidate_incident_feed_cache(tenant.id)

    incidents, _, sources = fetch_live_incidents(db, tenant.id)
    assert sources["slack"] is True
    assert len(incidents) == 1
    assert incidents[0].source == "slack"
    assert incidents[0].channel_name == "incident"
