from datetime import UTC, datetime

from app.schemas.investigation import IncidentSummary
from app.services.investigation import (
    _root_cause_from_linked_jira_issue,
    _workaround_from_linked_jira_issue,
)
from app.services.integration_telemetry import apply_jira_telemetry
from app.services.jira_types import JiraIssueActivity


def _incident(jira_id: str = "SCRUM-42") -> IncidentSummary:
    return IncidentSummary(
        id=f"jira:{jira_id}",
        title="Checkout API 500 errors",
        status="Investigating",
        system_scope="checkout",
        jira_id=jira_id,
        updated_at="2026-07-01T12:00:00Z",
        source="jira",
        priority="High",
        channel_name=None,
    )


def test_linked_jira_root_cause_uses_description(db, tenant):
    apply_jira_telemetry(
        db,
        tenant.id,
        [
            JiraIssueActivity(
                issue_key="SCRUM-42",
                issue_type="Bug",
                priority="High",
                status="In Progress",
                status_category="indeterminate",
                project_key="SCRUM",
                summary="Checkout API 500 errors",
                description_text=(
                    "Root cause: payment gateway timeout when Redis cache was cold "
                    "after deploy."
                ),
                updated_at=datetime.now(UTC),
            )
        ],
    )
    db.commit()

    root = _root_cause_from_linked_jira_issue(_incident(), db, tenant.id)
    assert root is not None
    assert "root cause" in root.lower() or "redis" in root.lower()


def test_linked_jira_workaround_uses_resolution(db, tenant):
    apply_jira_telemetry(
        db,
        tenant.id,
        [
            JiraIssueActivity(
                issue_key="SCRUM-42",
                issue_type="Bug",
                priority="High",
                status="Resolved",
                status_category="done",
                project_key="SCRUM",
                summary="Checkout API 500 errors",
                resolution="Rollback deploy and warm Redis cache via failover script.",
                recent_comments=[
                    "Mitigation: route traffic to secondary region until cache warms."
                ],
                updated_at=datetime.now(UTC),
            )
        ],
    )
    db.commit()

    workaround = _workaround_from_linked_jira_issue(_incident(), db, tenant.id)
    assert workaround is not None
    assert "rollback" in workaround.lower() or "mitigation" in workaround.lower()
