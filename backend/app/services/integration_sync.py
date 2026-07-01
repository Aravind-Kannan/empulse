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
from app.services.integration_telemetry import (
    apply_github_telemetry,
    apply_jira_telemetry,
    get_telemetry_snapshot,
)
from app.services.tenant_cognee import tenant_add_and_cognify, tenant_add_data_points
from app.tenancy import tenant_dataset_name

from app.services.integration_feeds import MOCK_GITHUB_ACTIVITY, MOCK_JIRA_ISSUES


class GraphPullRequest(DataPoint):
    pr_number: int
    commit_sha: str
    branch: str
    repository_url: str
    loc_added: int
    loc_removed: int
    file_path: str
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


_integration_configs: dict[str, GitHubConfigRequest | JiraConfigRequest] = {}


def save_github_config(config: GitHubConfigRequest) -> None:
    _integration_configs["github"] = config


def save_jira_config(config: JiraConfigRequest) -> None:
    _integration_configs["jira"] = config


def get_github_config() -> GitHubConfigRequest | None:
    config = _integration_configs.get("github")
    return config if isinstance(config, GitHubConfigRequest) else None


def get_jira_config(
    db: Session | None = None,
    tenant_id: uuid.UUID | None = None,
) -> JiraConfigRequest | None:
    if db is not None and tenant_id is not None:
        from app.services.jira_service import get_jira_config_for_tenant

        db_config = get_jira_config_for_tenant(db, tenant_id)
        if db_config:
            return db_config
    config = _integration_configs.get("jira")
    return config if isinstance(config, JiraConfigRequest) else None


def _load_org_context(
    db: Session,
    tenant_id: uuid.UUID,
) -> tuple[dict[str, GraphEmployee], dict[str, GraphComponent]]:
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
        return employee_nodes, component_nodes

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
    return employee_nodes, component_nodes


def analyze_github_payload(
    config: GitHubConfigRequest,
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
) -> tuple[str, list[GraphPullRequest], int]:
    """Mock document analyzer for GitHub commits, PRs, diffs, and LOC."""
    narrative_lines = [
        f"GitHub repository sync: {config.repository_url}",
        f"Target branch: {config.branch_target}",
        "Engineering activity feed with pull requests, commits, and file diffs.",
    ]
    data_points: list[GraphPullRequest] = []
    edge_count = 0

    for activity in MOCK_GITHUB_ACTIVITY:
        author = employee_nodes.get(activity["author_employee_id"])
        for file_change in activity["files"]:
            component = component_nodes.get(file_change["component_id"])
            pr_node = GraphPullRequest(
                pr_number=activity["pr_number"],
                commit_sha=activity["commit_sha"],
                branch=activity.get("branch", config.branch_target),
                repository_url=config.repository_url,
                loc_added=file_change["loc_added"],
                loc_removed=file_change["loc_removed"],
                file_path=file_change["path"],
            )
            if author:
                pr_node.contributedTo = (
                    Edge(
                        relationship_type="contributedTo",
                        properties={
                            "loc_added": file_change["loc_added"],
                            "loc_removed": file_change["loc_removed"],
                        },
                    ),
                    author,
                )
                edge_count += 1
            if component:
                pr_node.modifies = (
                    Edge(
                        relationship_type="modifies",
                        properties={"file_path": file_change["path"]},
                    ),
                    component,
                )
                edge_count += 1

            data_points.append(pr_node)
            author_name = author.name if author else "Unknown engineer"
            component_name = component.name if component else file_change["component_id"]
            narrative_lines.append(
                f"PR #{activity['pr_number']} commit {activity['commit_sha']}: "
                f"{author_name} changed {file_change['path']} "
                f"(+{file_change['loc_added']}/-{file_change['loc_removed']} LOC) "
                f"modifying {component_name}."
            )

    return "\n".join(narrative_lines), data_points, edge_count


def analyze_jira_payload(
    config: JiraConfigRequest,
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
    *,
    issues: list[dict] | None = None,
) -> tuple[str, list[GraphJiraTicket], int]:
    """Mock document analyzer for Jira tickets, priorities, and assignments."""
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

    for issue in source_issues:
        if project_filter and issue["project_key"] not in project_filter:
            continue

        assignee = (
            employee_nodes.get(issue["assignee_employee_id"])
            if issue.get("assignee_employee_id")
            else None
        )
        component = component_nodes.get(issue["component_id"])
        ticket_node = GraphJiraTicket(
            ticket_id=issue["ticket_id"],
            issue_type=issue["issue_type"],
            priority=issue["priority"],
            status=issue["status"],
            project_key=issue["project_key"],
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
                    properties={"priority": issue["priority"], "status": issue["status"]},
                ),
                component,
            )
            edge_count += 1

        data_points.append(ticket_node)
        assignee_name = assignee.name if assignee else "Unassigned"
        component_name = component.name if component else issue["component_id"]
        description = issue.get("description", "")
        narrative_lines.append(
            f"{issue['ticket_id']} ({issue['issue_type']}, {issue['priority']}, "
            f"{issue['status']}) assigned to {assignee_name}, "
            f"blocking component {component_name}."
            + (f" {description}" if description else "")
        )

    return "\n".join(narrative_lines), data_points, edge_count


async def process_external_app_sync(
    source: str,
    db: Session,
    tenant_id: uuid.UUID,
) -> dict[str, int | str]:
    """
    Transform raw app feed data, load into Cognee via add/cognify,
    and attach structured graph edges for multi-hop traversal.
    """
    normalized = source.lower().strip()
    employee_nodes, component_nodes = _load_org_context(db, tenant_id)

    if normalized == "github":
        config = get_github_config()
        if not config:
            raise ValueError("GitHub integration is not configured.")
        narrative, data_points, edge_count = analyze_github_payload(
            config, employee_nodes, component_nodes
        )
        custom_prompt = (
            "Extract GitHub engineering activity including pull requests, commits, "
            "file diff pathways, LOC changes, and map contributors to components "
            "via contributedTo and modifies relationships."
        )
    elif normalized == "jira":
        config = get_jira_config(db, tenant_id)
        if not config:
            raise ValueError("Jira integration is not configured.")
        from app.services.jira_service import sync_jira_to_cognee

        result = await sync_jira_to_cognee(tenant_id, db)
        return {
            **result,
            "telemetry": get_telemetry_snapshot(),
        }
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
        telemetry["github_ownership"] = apply_github_telemetry(db, tenant_id)

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
