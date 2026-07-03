from app.schemas.investigation import IncidentSummary
from app.services.incident_feed import _apply_overrides, _map_jira_status
from app.services.jira_types import JiraIssueActivity


def test_map_jira_status_closed_without_done_category() -> None:
    assert _map_jira_status("Closed", "indeterminate") == "Closed"


def test_map_jira_status_cancelled() -> None:
    assert _map_jira_status("Cancelled", "indeterminate") == "Closed"


def test_jira_issue_is_done_when_status_closed() -> None:
    issue = JiraIssueActivity(
        issue_key="ENG-1",
        issue_type="Bug",
        priority="High",
        status="Closed",
        status_category="indeterminate",
        project_key="ENG",
    )
    assert issue.is_done is True


def test_terminal_jira_status_not_overridden_by_stale_open() -> None:
    incident = IncidentSummary(
        id="jira:ENG-99",
        title="Checkout bug",
        status="Closed",
        system_scope="ENG",
        jira_id="ENG-99",
        updated_at="2026-07-01T10:00:00Z",
        source="jira",
    )
    merged = _apply_overrides([incident], {"jira:ENG-99": "Open"})
    assert merged[0].status == "Closed"
