"""High-level ontology ingest builders for integration sources."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.ontology.datapoints import (
    ChangeEvent,
    CodeArtifact,
    Discussion,
    Document,
    WorkItem,
)
from app.ontology.github import normalize_github_code_snapshot, normalize_github_pr_file_change
from app.ontology.jira import normalize_jira_issue
from app.ontology.mapper import (
    map_change_event,
    map_code_artifact,
    map_discussion,
    map_document,
    map_work_item,
)
from app.ontology.notion import normalize_notion_document
from app.ontology.slack import normalize_slack_thread
from app.schemas.integrations import GitHubConfigRequest, JiraConfigRequest
from app.services.cognee_ingest import GraphComponent, GraphEmployee
from app.services.github_types import GitHubPullRequestActivity
from app.services.jira_types import JiraIssueActivity
from app.services.notion_telemetry import living_runbook_template_narrative
from app.services.notion_types import NotionDocRecord
from app.services.slack_types import SlackThreadRecord


def _jira_work_item_narrative_line(canonical) -> str:
    parts = [
        (
            f"WorkItem {canonical.work_item_id} ({canonical.issue_type}, "
            f"{canonical.priority}, {canonical.status})"
        ),
        f"Summary: {canonical.summary}",
    ]
    if canonical.resolution:
        parts.append(f"Resolution: {canonical.resolution}")
    if canonical.labels:
        parts.append(f"Labels: {', '.join(canonical.labels)}")
    if canonical.description:
        parts.append(f"Description: {canonical.description[:600]}")
    if canonical.comment_excerpts:
        joined = " | ".join(canonical.comment_excerpts[:3])
        parts.append(f"Recent comments: {joined[:700]}")
    assignee_name = (
        canonical.assignee.display_name if canonical.assignee else "Unassigned"
    )
    reporter_name = (
        canonical.reporter.display_name if canonical.reporter else "Unknown"
    )
    component_name = (
        canonical.component.name if canonical.component else "unmapped"
    )
    parts.append(
        f"Assigned to {assignee_name}, reported by {reporter_name}, "
        f"blocks {component_name}."
    )
    if canonical.linked_work_item_ids:
        parts.append(
            "Linked issues: " + ", ".join(canonical.linked_work_item_ids[:8])
        )
    return " ".join(parts)


def build_github_code_artifacts(
    snapshots: list,
    *,
    db: Session,
    tenant_id: uuid.UUID,
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
    components_by_id: dict,
) -> tuple[list[str], list[CodeArtifact], int]:
    """Normalize GitHub file snapshots and map to ontology CodeArtifact nodes."""
    summary_lines: list[str] = []
    data_points: list[CodeArtifact] = []
    edge_count = 0

    for snap in snapshots:
        canonical = normalize_github_code_snapshot(
            snap,
            db=db,
            tenant_id=tenant_id,
            components_by_id=components_by_id,
        )
        node, edges = map_code_artifact(
            canonical,
            employee_nodes=employee_nodes,
            component_nodes=component_nodes,
        )
        data_points.append(node)
        edge_count += edges
        blame_note = canonical.blame_summary or "no blame ranges"
        summary_lines.append(
            f"CodeArtifact {canonical.file_path} @ {canonical.ref[:12]} "
            f"({len(canonical.content_preview)} chars, blame: {blame_note})."
        )

    return summary_lines, data_points, edge_count


def build_github_change_events(
    config: GitHubConfigRequest,
    activities: list[GitHubPullRequestActivity],
    *,
    db: Session,
    tenant_id: uuid.UUID,
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
    components_by_id: dict,
) -> tuple[list[str], list[ChangeEvent], int]:
    """Normalize GitHub PR activity and map to ontology ChangeEvent nodes."""
    summary_lines = [
        f"GitHub change ingest: {', '.join(config.resolved_repository_urls())}",
        (
            "Target branches: all"
            if config.sync_all_branches
            else f"Target branches: {', '.join(config.resolved_branch_targets() or [])}"
        ),
    ]
    data_points: list[ChangeEvent] = []
    edge_count = 0

    for activity in activities:
        for file_change in activity.files:
            canonical = normalize_github_pr_file_change(
                activity,
                file_change,
                config=config,
                db=db,
                tenant_id=tenant_id,
                components_by_id=components_by_id,
            )
            if canonical is None:
                continue
            node, edges = map_change_event(
                canonical,
                employee_nodes=employee_nodes,
                component_nodes=component_nodes,
            )
            data_points.append(node)
            edge_count += edges
            author_name = (
                canonical.author.display_name if canonical.author else "unknown"
            )
            component_name = (
                canonical.component.name if canonical.component else ""
            )
            summary_lines.append(
                f"ChangeEvent PR #{canonical.pr_number} ({canonical.pr_url}): "
                f"{author_name} changed {canonical.file_path} "
                f"(+{canonical.loc_added}/-{canonical.loc_removed} LOC) "
                f"modifying {component_name}."
            )

    return summary_lines, data_points, edge_count


def build_jira_work_items(
    config: JiraConfigRequest,
    issues: list[JiraIssueActivity],
    *,
    db: Session,
    tenant_id: uuid.UUID,
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
    components_by_id: dict,
) -> tuple[list[str], list[WorkItem], int]:
    project_filter = {
        key.strip().upper()
        for key in config.project_keys.split(",")
        if key.strip()
    }
    summary_lines = [
        f"Jira work item ingest: {config.site_url}",
        f"Project keys: {config.project_keys or 'all'}",
    ]
    data_points: list[WorkItem] = []
    edge_count = 0

    for issue in issues:
        canonical = normalize_jira_issue(
            issue,
            config=config,
            db=db,
            tenant_id=tenant_id,
            components_by_id=components_by_id,
            project_filter=project_filter,
        )
        if canonical is None:
            continue
        node, edges = map_work_item(
            canonical,
            employee_nodes=employee_nodes,
            component_nodes=component_nodes,
        )
        data_points.append(node)
        edge_count += edges
        summary_lines.append(_jira_work_item_narrative_line(canonical))

    return summary_lines, data_points, edge_count


def build_notion_documents(
    docs: list[NotionDocRecord],
    *,
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
    components_by_id: dict,
) -> tuple[list[str], list[Document], int]:
    employee_names = {
        employee_id: node.name for employee_id, node in employee_nodes.items()
    }
    summary_lines: list[str] = []
    data_points: list[Document] = []
    edge_count = 0
    template_pages = 0

    for doc in docs:
        canonical = normalize_notion_document(
            doc,
            components_by_id=components_by_id,
            employee_names=employee_names,
        )
        if canonical is None:
            continue
        node, edges = map_document(
            canonical,
            employee_nodes=employee_nodes,
            component_nodes=component_nodes,
        )
        data_points.append(node)
        edge_count += edges
        component_name = canonical.component.name if canonical.component else "unlinked"
        author_name = canonical.author.display_name if canonical.author else "unknown"
        summary_lines.append(
            f"Document '{canonical.title}' ({canonical.doc_kind}) documents "
            f"{component_name}, authored by {author_name}."
        )
        if doc.is_ownership_template:
            template_pages += 1

    if template_pages:
        summary_lines.append(living_runbook_template_narrative())

    return summary_lines, data_points, edge_count


def build_slack_discussions(
    threads: list[SlackThreadRecord],
    *,
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
    components_by_id: dict,
) -> tuple[list[str], list[Discussion], int]:
    employee_names = {
        employee_id: node.name for employee_id, node in employee_nodes.items()
    }
    summary_lines: list[str] = []
    data_points: list[Discussion] = []
    edge_count = 0

    for thread in threads:
        canonical = normalize_slack_thread(
            thread,
            components_by_id=components_by_id,
            employee_names=employee_names,
        )
        if canonical is None:
            continue
        node, edges = map_discussion(
            canonical,
            employee_nodes=employee_nodes,
            component_nodes=component_nodes,
        )
        data_points.append(node)
        edge_count += edges
        resolver_name = (
            canonical.resolver.display_name if canonical.resolver else "unknown"
        )
        summary_lines.append(
            f"Discussion '{canonical.title}' in #{canonical.channel_name}"
            + (
                f" resolved by {resolver_name}."
                if canonical.resolver
                else "."
            )
        )

    return summary_lines, data_points, edge_count
