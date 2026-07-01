from __future__ import annotations

import uuid
from typing import Any

from pydantic import SkipValidation
from sqlalchemy.orm import Session

from cognee.infrastructure.engine import DataPoint
from cognee.infrastructure.engine.models.Edge import Edge

from app.models.operational import Component, Employee
from app.schemas.integrations import GitHubConfigRequest, JiraConfigRequest
from app.schemas.org import ACME_ORG_CHART
from app.services.cognee_ingest import GraphComponent, GraphEmployee
from app.services.github_client import (
    fetch_github_pull_request_activity,
    parse_repository_url,
)
from app.services.github_path_mapper import apply_path_mapping
from app.services.github_types import GitHubPullRequestActivity
from app.services.integration_telemetry import (
    HIGH_PRIORITIES,
    apply_github_telemetry,
    apply_jira_telemetry,
    get_telemetry_snapshot,
    mark_sync_completed,
)
from app.services.identity_resolver import resolve_author_employee_id
from app.services.tenant_cognee import tenant_add_and_cognify, tenant_add_data_points
from app.tenancy import tenant_dataset_name

from app.services.jira_client import fetch_jira_issues
from app.services.jira_mapper import map_issue_to_component
from app.services.jira_types import JiraIssueActivity


class GraphPullRequest(DataPoint):
    pr_number: int
    commit_sha: str
    branch: str
    repository_url: str
    loc_added: int
    loc_removed: int
    file_path: str
    pr_url: str = ""
    contributedTo: SkipValidation[Any] = None
    modifies: SkipValidation[Any] = None
    metadata: dict = {"index_fields": ["pr_number", "file_path", "branch"]}


class GraphJiraTicket(DataPoint):
    ticket_id: str
    issue_type: str
    priority: str
    status: str
    project_key: str
    assignedTo: SkipValidation[Any] = None
    blocksComponent: SkipValidation[Any] = None
    metadata: dict = {"index_fields": ["ticket_id", "issue_type", "status"]}


from app.services.integration_config_store import get_github_config, get_jira_config


def _load_org_context(
    db: Session,
    tenant_id: uuid.UUID,
) -> tuple[dict[str, GraphEmployee], dict[str, GraphComponent], dict[str, Component]]:
    employees = db.query(Employee).filter(Employee.tenant_id == tenant_id).all()
    components = db.query(Component).filter(Component.tenant_id == tenant_id).all()

    if not employees:
        employee_nodes = {
            employee.id: GraphEmployee(
                external_id=employee.id,
                name=employee.name,
                role=employee.role,
                email=employee.email,
                tenure_years=employee.tenure_years,
            )
            for employee in ACME_ORG_CHART.employees
        }
        component_nodes = {
            component.id: GraphComponent(
                external_id=component.id,
                name=component.name,
                description=component.description,
                open_tasks_count=component.open_tasks_count,
                unresolved_incidents=component.unresolved_incidents,
            )
            for component in ACME_ORG_CHART.components
        }
        components_by_id = {
            component.id: Component(
                id=component.id,
                tenant_id=tenant_id,
                name=component.name,
                description=component.description,
                open_tasks_count=component.open_tasks_count,
                unresolved_incidents=component.unresolved_incidents,
            )
            for component in ACME_ORG_CHART.components
        }
        return employee_nodes, component_nodes, components_by_id

    employee_nodes = {
        employee.id: GraphEmployee(
            external_id=employee.id,
            name=employee.name,
            role=employee.role,
            email=employee.email,
            tenure_years=employee.tenure_years,
        )
        for employee in employees
    }
    component_nodes = {
        component.id: GraphComponent(
            external_id=component.id,
            name=component.name,
            description=component.description,
            open_tasks_count=component.open_tasks_count,
            unresolved_incidents=component.unresolved_incidents,
        )
        for component in components
    }
    components_by_id = {component.id: component for component in components}
    return employee_nodes, component_nodes, components_by_id


def fetch_and_map_github_activity(
    config: GitHubConfigRequest,
    components_by_id: dict[str, Component],
    *,
    use_fixture: bool = False,
) -> tuple[list[GitHubPullRequestActivity], list[str], dict[str, int]]:
    _, repo_name = parse_repository_url(config.repository_url)
    activities, open_prs_by_login = fetch_github_pull_request_activity(
        config, use_fixture=use_fixture
    )
    mapped, unmapped = apply_path_mapping(
        activities,
        path_component_map=config.path_component_map,
        repo_name=repo_name,
        components_by_id=components_by_id,
        default_component_id=config.default_component_id,
    )
    return mapped, unmapped, open_prs_by_login


def analyze_github_payload(
    config: GitHubConfigRequest,
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
    db: Session,
    tenant_id: uuid.UUID,
    activities: list[GitHubPullRequestActivity],
) -> tuple[str, list[GraphPullRequest], int]:
    """Build Cognee graph nodes from live GitHub pull request activity."""
    narrative_lines = [
        f"GitHub repository sync: {config.repository_url}",
        f"Target branch: {config.branch_target}",
        "Engineering activity feed with pull requests, commits, and file diffs.",
    ]
    data_points: list[GraphPullRequest] = []
    edge_count = 0

    for activity in activities:
        author_employee_id = resolve_author_employee_id(
            db,
            tenant_id,
            "github",
            activity.author_provider_user_id,
            demo_fallback_employee_id=None,
            quarantine_event_type="github_pr",
            quarantine_payload={
                "pr_number": activity.pr_number,
                "commit_sha": activity.commit_sha,
                "pr_url": activity.pr_url,
            },
        )
        author = employee_nodes.get(author_employee_id) if author_employee_id else None
        for file_change in activity.files:
            if not file_change.component_id:
                continue
            component = component_nodes.get(file_change.component_id)
            pr_node = GraphPullRequest(
                pr_number=activity.pr_number,
                commit_sha=activity.commit_sha,
                branch=activity.branch or config.branch_target,
                repository_url=config.repository_url,
                loc_added=file_change.loc_added,
                loc_removed=file_change.loc_removed,
                file_path=file_change.path,
                pr_url=activity.pr_url,
            )
            if author:
                pr_node.contributedTo = (
                    Edge(
                        relationship_type="contributedTo",
                        properties={
                            "loc_added": file_change.loc_added,
                            "loc_removed": file_change.loc_removed,
                            "pr_url": activity.pr_url,
                        },
                    ),
                    author,
                )
                edge_count += 1
            if component:
                pr_node.modifies = (
                    Edge(
                        relationship_type="modifies",
                        properties={
                            "file_path": file_change.path,
                            "pr_url": activity.pr_url,
                        },
                    ),
                    component,
                )
                edge_count += 1

            data_points.append(pr_node)
            author_name = author.name if author else activity.author_login
            component_name = component.name if component else file_change.component_id
            narrative_lines.append(
                f"PR #{activity.pr_number} ({activity.pr_url}) commit {activity.commit_sha}: "
                f"{author_name} changed {file_change.path} "
                f"(+{file_change.loc_added}/-{file_change.loc_removed} LOC) "
                f"modifying {component_name}."
            )

    return "\n".join(narrative_lines), data_points, edge_count


def fetch_and_map_jira_issues(
    config: JiraConfigRequest,
    components_by_id: dict[str, Component],
    *,
    use_fixture: bool = False,
) -> list[JiraIssueActivity]:
    issues = fetch_jira_issues(config, use_fixture=use_fixture)
    valid_ids = set(components_by_id)
    mapped: list[JiraIssueActivity] = []
    for issue in issues:
        component_id = map_issue_to_component(
            issue, config, valid_component_ids=valid_ids
        )
        if component_id:
            issue.component_id = component_id
        mapped.append(issue)
    return mapped


def analyze_jira_payload(
    config: JiraConfigRequest,
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
    db: Session,
    tenant_id: uuid.UUID,
    issues: list[JiraIssueActivity],
) -> tuple[str, list[GraphJiraTicket], int]:
    """Build Cognee graph nodes from Jira issue activity."""
    project_filter = {
        key.strip().upper()
        for key in config.project_keys.split(",")
        if key.strip()
    }
    source_issues = issues if issues is not None else MOCK_JIRA_ISSUES
    narrative_lines = [
        f"Jira site sync: {config.site_url}",
        f"Project keys: {config.project_keys or 'all'}",
        "Issue tracker feed with bugs, tasks, epics, priorities, and assignees.",
    ]
    data_points: list[GraphJiraTicket] = []
    edge_count = 0

    for issue in issues:
        if project_filter and issue.project_key not in project_filter:
            continue
        if issue.is_done:
            continue

        assignee_employee_id: str | None = None
        if issue.assignee_provider_user_id:
            assignee_employee_id = resolve_author_employee_id(
                db,
                tenant_id,
                "jira",
                issue.assignee_provider_user_id,
                email_hint=issue.assignee_email,
                quarantine_event_type="jira_issue",
                quarantine_payload={"issue_key": issue.issue_key},
            )
        assignee = (
            employee_nodes.get(assignee_employee_id) if assignee_employee_id else None
        )
        component = (
            component_nodes.get(issue.component_id) if issue.component_id else None
        )
        ticket_node = GraphJiraTicket(
            ticket_id=issue.issue_key,
            issue_type=issue.issue_type,
            priority=issue.priority,
            status=issue.status,
            project_key=issue.project_key,
        )
        if assignee:
            ticket_node.assignedTo = (
                Edge(relationship_type="assignedTo"),
                assignee,
            )
            edge_count += 1
        if component:
            ticket_node.blocksComponent = (
                Edge(
                    relationship_type="blocksComponent",
                    properties={"priority": issue.priority, "status": issue.status},
                ),
                component,
            )
            edge_count += 1

        data_points.append(ticket_node)
        assignee_name = assignee.name if assignee else "Unassigned"
        component_name = component.name if component else (issue.component_id or "unmapped")
        narrative_lines.append(
            f"{issue.issue_key} ({issue.issue_type}, {issue.priority}, "
            f"{issue.status}) assigned to {assignee_name}, "
            f"blocking component {component_name}."
            + (f" {description}" if description else "")
        )

    return "\n".join(narrative_lines), data_points, edge_count


async def process_external_app_sync(
    source: str,
    db: Session,
    tenant_id: uuid.UUID,
    *,
    use_github_fixture: bool = False,
    use_jira_fixture: bool = False,
) -> dict[str, int | str]:
    """
    Transform raw app feed data, load into Cognee via add/cognify,
    and attach structured graph edges for multi-hop traversal.
    """
    normalized = source.lower().strip()
    employee_nodes, component_nodes, components_by_id = _load_org_context(db, tenant_id)
    github_activities: list[GitHubPullRequestActivity] = []
    open_prs_by_login: dict[str, int] = {}

    if normalized == "github":
        config = get_github_config(db, tenant_id)
        if not config:
            raise ValueError("GitHub integration is not configured.")
        github_activities, unmapped_paths, open_prs_by_login = fetch_and_map_github_activity(
            config,
            components_by_id,
            use_fixture=use_github_fixture,
        )
        if unmapped_paths:
            narrative_prefix = (
                f"Warning: {len(unmapped_paths)} file paths could not be mapped to components."
            )
        else:
            narrative_prefix = ""
        narrative, data_points, edge_count = analyze_github_payload(
            config,
            employee_nodes,
            component_nodes,
            db,
            tenant_id,
            github_activities,
        )
        if narrative_prefix:
            narrative = f"{narrative_prefix}\n{narrative}"
        custom_prompt = (
            "Extract GitHub engineering activity including pull requests, commits, "
            "file diff pathways, LOC changes, and map contributors to components "
            "via contributedTo and modifies relationships."
        )
    elif normalized == "jira":
        config = get_jira_config(db, tenant_id)
        if not config:
            raise ValueError("Jira integration is not configured.")
        jira_issues = fetch_and_map_jira_issues(
            config,
            components_by_id,
            use_fixture=use_jira_fixture,
        )
        narrative, data_points, edge_count = analyze_jira_payload(
            config,
            employee_nodes,
            component_nodes,
            db,
            tenant_id,
            jira_issues,
        )
        custom_prompt = (
            "Extract Jira issue metadata including ticket IDs, issue types, priorities, "
            "status indicators, and link assignees and blocked components via "
            "assignedTo and blocksComponent relationships."
        )
    else:
        raise ValueError(f"Unsupported integration source '{source}'.")

    if data_points:
        await tenant_add_data_points(tenant_id, data_points)

    dataset = tenant_dataset_name(tenant_id)
    await tenant_add_and_cognify(
        narrative,
        tenant_id,
        custom_prompt=custom_prompt,
    )

    telemetry: dict[str, object] = {}
    if normalized == "github":
        telemetry["github_ownership"] = apply_github_telemetry(
            db,
            tenant_id,
            github_activities,
            open_prs_by_login=open_prs_by_login or None,
        )
    elif normalized == "jira":
        high_priorities = set(config.high_priorities) if config else HIGH_PRIORITIES
        telemetry["jira_backlog"] = apply_jira_telemetry(
            db,
            tenant_id,
            jira_issues,
            high_priorities=high_priorities,
        )

    db.commit()

    mark_sync_completed(normalized)

    return {
        "source": normalized,
        "cognee_dataset": dataset,
        "documents_ingested": 1,
        "graph_nodes_created": len(data_points),
        "graph_edges_created": edge_count,
        "narrative_preview": narrative[:280],
        "telemetry": telemetry or get_telemetry_snapshot(),
    }


async def process_global_sync(
    db: Session,
    tenant_id: uuid.UUID,
    sources: list[str],
) -> list[dict[str, int | str]]:
    results: list[dict[str, int | str]] = []
    for source in sources:
        results.append(await process_external_app_sync(source, db, tenant_id))
    return results
