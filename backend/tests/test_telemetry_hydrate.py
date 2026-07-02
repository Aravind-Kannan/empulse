"""Integration telemetry survives backend restarts via persisted cache."""

from app.services.integration_config_store import save_telemetry_cache
from app.services.integration_telemetry import (
    apply_slack_telemetry_with_cache,
    get_jira_backlog_boost,
    get_slack_employee_signals,
    has_jira_sync,
    has_slack_sync,
    hydrate_integration_telemetry,
    hydrate_jira_telemetry_from_db,
    hydrate_slack_telemetry_from_db,
    reset_telemetry_for_tests,
)
from app.services.slack_telemetry import compute_slack_telemetry
from app.services.slack_types import SlackThreadRecord
from tests.conftest import add_employee


def test_hydrate_jira_telemetry_from_db_cache(db, tenant):
    reset_telemetry_for_tests()
    save_telemetry_cache(
        db,
        tenant.id,
        "jira",
        {
            "backlog_by_employee": {"emp-jira": 1},
            "employee_signals": {
                "emp-jira": {
                    "employee_id": "emp-jira",
                    "open_tasks": 2,
                    "open_p1_p2": 1,
                    "jira_backlog_boost": 1,
                    "epic_owner_count": 0,
                    "sprint_points": 3.0,
                    "sample_issue_urls": [],
                }
            },
        },
    )

    assert not has_jira_sync()
    assert hydrate_jira_telemetry_from_db(db, tenant.id)
    assert has_jira_sync()
    assert get_jira_backlog_boost("emp-jira") == 1


def test_hydrate_slack_telemetry_from_db_cache(db, tenant):
    reset_telemetry_for_tests()
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-slack",
        name="Slack User",
        email="slack@example.com",
    )
    db.commit()

    snapshot = compute_slack_telemetry(
        db,
        tenant.id,
        [
            SlackThreadRecord(
                channel_id="C1",
                channel_name="incidents",
                thread_ts="1",
                parent_text="prod outage",
                is_incident_channel=True,
                resolved_by_employee_id=employee.id,
            )
        ],
        slack_id_to_employee={},
    )
    apply_slack_telemetry_with_cache(db, tenant.id, snapshot)
    assert has_slack_sync()

    reset_telemetry_for_tests()
    assert not has_slack_sync()

    assert hydrate_slack_telemetry_from_db(db, tenant.id)
    assert has_slack_sync()
    assert get_slack_employee_signals(employee.id) is not None


def test_hydrate_integration_telemetry_restores_all(db, tenant):
    reset_telemetry_for_tests()
    save_telemetry_cache(
        db,
        tenant.id,
        "jira",
        {
            "backlog_by_employee": {"emp-a": 1},
            "employee_signals": {
                "emp-a": {
                    "employee_id": "emp-a",
                    "open_tasks": 2,
                    "open_p1_p2": 1,
                    "jira_backlog_boost": 1,
                    "epic_owner_count": 0,
                    "sprint_points": 3.0,
                    "sample_issue_urls": [],
                }
            },
        },
    )
    hydrate_integration_telemetry(db, tenant.id)
    assert has_jira_sync()
