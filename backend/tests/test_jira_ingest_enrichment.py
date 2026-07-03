"""Jira rich ingest: description, comments, resolution, labels, reporter."""

from app.ontology.ingest import build_jira_work_items
from app.services.jira_text import adf_to_plain_text
from app.services.jira_types import JiraIssueActivity
from app.services.sync_ledger import plan_sync_ingest, _jira_version


def test_adf_to_plain_text_extracts_paragraphs():
    adf = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "Pool exhausted under load."}],
            }
        ],
    }
    assert "Pool exhausted" in adf_to_plain_text(adf)


def test_build_jira_work_items_includes_description_and_comments(db, tenant):
    from app.schemas.integrations import JiraConfigRequest
    from app.services.cognee_ingest import GraphComponent, GraphEmployee

    issue = JiraIssueActivity(
        issue_key="ENG-9",
        issue_type="Bug",
        priority="High",
        status="Resolved",
        status_category="done",
        project_key="ENG",
        summary="Checkout 500s",
        description_text="Connection pool exhausted during peak traffic.",
        resolution="Fixed",
        labels=["incident", "checkout"],
        linked_issue_keys=["ENG-8"],
        recent_comments=["Root cause: pool size too low.", "Deployed fix."],
        reporter_provider_user_id="rep-1",
        reporter_email="reporter@acme.com",
        assignee_provider_user_id="asg-1",
        assignee_email="assignee@acme.com",
        component_id="comp-pay",
    )
    components_by_id = {
        "comp-pay": type("C", (), {"id": "comp-pay", "name": "Payments"})(),
    }
    lines, nodes, edges = build_jira_work_items(
        JiraConfigRequest(site_url="https://acme.atlassian.net", api_token="x"),
        [issue],
        db=db,
        tenant_id=tenant.id,
        employee_nodes={},
        component_nodes={
            "comp-pay": GraphComponent(
                external_id="comp-pay",
                name="Payments",
                description="",
                open_tasks_count=0,
                unresolved_incidents=0,
            )
        },
        components_by_id=components_by_id,
    )
    assert len(nodes) == 1
    node = nodes[0]
    assert "Connection pool exhausted" in node.description_preview
    assert node.resolution == "Fixed"
    assert "incident" in node.labels
    assert "Root cause" in node.comment_preview
    assert edges >= 1
    blob = " ".join(lines)
    assert "Description:" in blob
    assert "Recent comments:" in blob
    assert "Resolution: Fixed" in blob
    assert "Linked issues: ENG-8" in blob


def test_jira_ledger_version_changes_when_description_changes():
    from app.ontology.datapoints import WorkItem

    base = WorkItem(
        source="jira",
        work_item_id="ENG-1",
        issue_type="Bug",
        priority="High",
        status="Open",
        project_key="ENG",
        summary="Title",
        description_preview="First",
    )
    updated = WorkItem(
        source="jira",
        work_item_id="ENG-1",
        issue_type="Bug",
        priority="High",
        status="Open",
        project_key="ENG",
        summary="Title",
        description_preview="Second",
    )
    assert _jira_version(base) != _jira_version(updated)


def test_plan_sync_ingest_detects_jira_content_update(db, tenant):
    from app.ontology.datapoints import WorkItem

    first = WorkItem(
        source="jira",
        work_item_id="ENG-1",
        issue_type="Bug",
        priority="High",
        status="Open",
        project_key="ENG",
        summary="Title",
        description_preview="v1",
    )
    plan = plan_sync_ingest(db, tenant.id, "jira", [first])
    assert plan.new_count == 1
    from app.services.sync_ledger import record_synced_items

    record_synced_items(db, tenant.id, "jira", plan.ledger_items)
    db.commit()

    second = WorkItem(
        source="jira",
        work_item_id="ENG-1",
        issue_type="Bug",
        priority="High",
        status="Open",
        project_key="ENG",
        summary="Title",
        description_preview="v2",
    )
    plan2 = plan_sync_ingest(db, tenant.id, "jira", [second])
    assert plan2.updated_count == 1
    assert plan2.skipped_count == 0
