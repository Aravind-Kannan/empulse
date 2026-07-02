from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any, Callable

from pydantic import SkipValidation
from sqlalchemy.orm import Session

from cognee.infrastructure.engine import DataPoint
from cognee.infrastructure.engine.models.Edge import Edge

from app.models.operational import Component, Employee
from app.schemas.integrations import GitHubConfigRequest, JiraConfigRequest
from app.schemas.org import ACME_ORG_CHART
from app.services.cognee_ingest import GraphComponent, GraphEmployee
from app.services.github_code import (
    GitHubCodeFileSnapshot,
    collect_github_code_snapshots,
)
from app.services.github_client import (
    fetch_github_pull_request_activity,
    parse_repository_url,
)
from app.services.github_path_mapper import apply_path_mapping
from app.services.github_types import GitHubPullRequestActivity
from app.services.integration_config_store import record_integration_sync
from app.services.integration_telemetry import (
    HIGH_PRIORITIES,
    apply_github_telemetry,
    apply_jira_telemetry,
    apply_notion_telemetry,
    apply_slack_telemetry_with_cache,
    get_github_ownership,
    get_telemetry_snapshot,
    mark_sync_completed,
)
from app.services.identity_resolver import resolve_author_employee_id
from app.services.tenant_cognee import tenant_add_and_cognify, tenant_add_data_points
from app.tenancy import tenant_dataset_name

from app.services.jira_client import fetch_jira_issues
from app.services.jira_mapper import map_issue_to_component
from app.services.jira_types import JiraIssueActivity
from app.services.notion_client import (
    fetch_notion_document_inventory,
    load_fixture_document_inventory,
)
from app.services.notion_telemetry import (
    compute_notion_telemetry,
    inventory_dicts_to_records,
    living_runbook_template_narrative,
)
from app.services.notion_types import NotionDocRecord
from app.services.slack_client import fetch_slack_incident_threads, thread_title
from app.services.slack_telemetry import compute_slack_telemetry
from app.services.slack_types import SlackThreadRecord
from app.services.sync_ledger import (
    count_graph_edges,
    plan_sync_ingest,
    record_synced_items,
)


class GraphCodeFile(DataPoint):
    repository_url: str
    file_path: str
    ref: str
    content_preview: str = ""
    patch_preview: str = ""
    blame_summary: str = ""
    primary_authors: str = ""
    blob_sha: str = ""
    documentsComponent: SkipValidation[Any] = None
    blameAttributedTo: SkipValidation[Any] = None
    metadata: dict = {
        "index_fields": ["file_path", "repository_url", "ref", "primary_authors"],
        "identity_fields": ["repository_url", "file_path", "ref"],
    }


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
    metadata: dict = {
        "index_fields": ["pr_number", "file_path", "branch"],
        "identity_fields": ["repository_url", "pr_number", "commit_sha", "file_path"],
    }


class GraphJiraTicket(DataPoint):
    ticket_id: str
    issue_type: str
    priority: str
    status: str
    project_key: str
    assignedTo: SkipValidation[Any] = None
    blocksComponent: SkipValidation[Any] = None
    metadata: dict = {
        "index_fields": ["ticket_id", "issue_type", "status"],
        "identity_fields": ["ticket_id"],
    }


class GraphNotionPage(DataPoint):
    page_id: str
    title: str
    last_edited: str
    page_url: str = ""
    page_kind: str = "runbook"
    documentedBy: SkipValidation[Any] = None
    authoredBy: SkipValidation[Any] = None
    metadata: dict = {
        "index_fields": ["page_id", "title", "page_kind"],
        "identity_fields": ["page_id"],
    }


class GraphSlackThread(DataPoint):
    thread_id: str
    channel_name: str
    title: str
    thread_url: str = ""
    resolvedBy: SkipValidation[Any] = None
    discussesComponent: SkipValidation[Any] = None
    metadata: dict = {
        "index_fields": ["thread_id", "channel_name", "title"],
        "identity_fields": ["thread_id"],
    }


from app.services.integration_config_store import (
    get_github_config,
    get_jira_config,
    get_notion_config,
    get_slack_config,
)


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
    repository_urls = config.resolved_repository_urls()
    all_activities: list[GitHubPullRequestActivity] = []
    all_unmapped: list[str] = []
    combined_open_prs: dict[str, int] = {}
    seen_activity_keys: set[str] = set()

    for repository_url in repository_urls:
        repo_config = config.with_repository(repository_url)
        _, repo_name = parse_repository_url(repository_url)
        activities, open_prs_by_login = fetch_github_pull_request_activity(
            repo_config, use_fixture=use_fixture
        )
        mapped, unmapped = apply_path_mapping(
            activities,
            path_component_map=config.path_component_map,
            repo_name=repo_name,
            components_by_id=components_by_id,
            default_component_id=config.default_component_id,
        )
        for activity in mapped:
            if activity.dedupe_key in seen_activity_keys:
                continue
            seen_activity_keys.add(activity.dedupe_key)
            all_activities.append(activity)
        all_unmapped.extend(unmapped)
        for login, count in open_prs_by_login.items():
            combined_open_prs[login] = combined_open_prs.get(login, 0) + count

    return all_activities, all_unmapped, combined_open_prs


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
        f"GitHub repository sync: {', '.join(config.resolved_repository_urls())}",
        (
            "Target branches: all"
            if config.sync_all_branches
            else f"Target branches: {', '.join(config.resolved_branch_targets() or [])}"
        ),
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


def analyze_github_code_payload(
    snapshots: list[GitHubCodeFileSnapshot],
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
    db: Session,
    tenant_id: uuid.UUID,
) -> tuple[list[str], list[GraphCodeFile], int]:
    """Build Cognee nodes from file contents, diffs, and blame ranges."""
    narrative_lines: list[str] = []
    data_points: list[GraphCodeFile] = []
    edge_count = 0

    for snap in snapshots:
        component = (
            component_nodes.get(snap.component_id) if snap.component_id else None
        )
        node = GraphCodeFile(
            repository_url=snap.repository_url,
            file_path=snap.file_path,
            ref=snap.ref,
            content_preview=snap.content_preview,
            patch_preview=snap.patch_preview,
            blame_summary=snap.blame_summary(),
            primary_authors=", ".join(snap.primary_authors[:8]),
            blob_sha=snap.content_sha,
        )
        if component:
            node.documentsComponent = (
                Edge(relationship_type="documentsComponent"),
                component,
            )
            edge_count += 1

        top_author = snap.primary_authors[0] if snap.primary_authors else None
        if top_author:
            employee_id = resolve_author_employee_id(
                db,
                tenant_id,
                "github",
                f"gh-{top_author}",
                quarantine_event_type="github_blame",
                quarantine_payload={"file_path": snap.file_path, "ref": snap.ref},
            )
            author = employee_nodes.get(employee_id) if employee_id else None
            if author:
                node.blameAttributedTo = (
                    Edge(relationship_type="blameAttributedTo"),
                    author,
                )
                edge_count += 1

        data_points.append(node)
        blame_note = snap.blame_summary() or "no blame ranges"
        narrative_lines.append(
            f"Code file {snap.file_path} @ {snap.ref[:12]} "
            f"({len(snap.content_preview)} chars, blame: {blame_note})."
        )

    return narrative_lines, data_points, edge_count


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
        )

    return "\n".join(narrative_lines), data_points, edge_count


def analyze_notion_payload(
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
    docs: list[NotionDocRecord],
) -> tuple[str, list, int]:
    narrative_lines: list[str] = []
    data_points: list = []
    edge_count = 0
    template_pages = 0

    for doc in docs:
        if doc.is_archived or doc.is_inaccessible:
            continue

        component = (
            component_nodes.get(doc.component_id) if doc.component_id else None
        )
        author = (
            employee_nodes.get(doc.owner_employee_id) if doc.owner_employee_id else None
        )
        page_node = GraphNotionPage(
            page_id=doc.page_id,
            title=doc.title,
            last_edited=doc.last_edited_at.isoformat(),
            page_url=doc.page_url,
            page_kind=doc.page_kind,
        )
        if component:
            page_node.documentedBy = (
                Edge(relationship_type="documentedBy"),
                component,
            )
            edge_count += 1
        if author:
            page_node.authoredBy = (
                Edge(relationship_type="authoredBy"),
                author,
            )
            edge_count += 1

        data_points.append(page_node)
        component_name = component.name if component else "unlinked"
        author_name = author.name if author else "unknown"
        narrative_lines.append(
            f"Notion page '{doc.title}' ({doc.page_kind}) last edited "
            f"{doc.last_edited_at.date()} documents {component_name}, "
            f"authored by {author_name}."
        )
        if doc.is_ownership_template:
            template_pages += 1

    if template_pages:
        narrative_lines.append(living_runbook_template_narrative())

    return "\n".join(narrative_lines), data_points, edge_count


def _notion_docs_for_crosscheck(db: Session, tenant_id: uuid.UUID) -> list[NotionDocRecord]:
    from app.models.operational import NotionDocSnapshot

    rows = (
        db.query(NotionDocSnapshot)
        .filter(NotionDocSnapshot.tenant_id == tenant_id)
        .all()
    )
    return [
        NotionDocRecord(
            page_id=row.page_id,
            title=row.title,
            page_url=row.page_url,
            last_edited_at=row.last_edited_at or datetime.now(UTC),
            component_id=row.component_id,
            owner_employee_id=row.owner_employee_id,
            page_kind=row.page_kind,
            is_archived=row.is_archived,
            last_verified_at=row.last_verified_at,
        )
        for row in rows
    ]


def _map_slack_users_to_employees(
    db: Session,
    tenant_id: uuid.UUID,
    slack_users: dict[str, str],
) -> dict[str, str]:
    employees = db.query(Employee).filter(Employee.tenant_id == tenant_id).all()
    email_to_employee = {employee.email.lower(): employee.id for employee in employees}
    mapping: dict[str, str] = {}
    for slack_id, email in slack_users.items():
        if not email:
            employee_id = resolve_author_employee_id(
                db,
                tenant_id,
                "slack",
                slack_id,
            )
        else:
            employee_id = email_to_employee.get(email.lower())
            if not employee_id:
                employee_id = resolve_author_employee_id(
                    db,
                    tenant_id,
                    "slack",
                    slack_id,
                    email_hint=email,
                )
        if employee_id:
            mapping[slack_id] = employee_id
    return mapping


def analyze_slack_payload(
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
    threads: list[SlackThreadRecord],
) -> tuple[str, list, int]:
    narrative_lines: list[str] = []
    data_points: list = []
    edge_count = 0

    for thread in threads:
        if not thread.resolved_by_employee_id and not thread.is_on_call_channel:
            continue
        title = thread_title(thread.parent_text)
        component = (
            component_nodes.get(thread.component_id) if thread.component_id else None
        )
        resolver = (
            employee_nodes.get(thread.resolved_by_employee_id)
            if thread.resolved_by_employee_id
            else None
        )
        thread_node = GraphSlackThread(
            thread_id=f"{thread.channel_id}:{thread.thread_ts}",
            channel_name=thread.channel_name,
            title=title,
            thread_url=thread.thread_url,
        )
        if resolver:
            thread_node.resolvedBy = (
                Edge(relationship_type="resolvedBy"),
                resolver,
            )
            edge_count += 1
        if component:
            thread_node.discussesComponent = (
                Edge(relationship_type="discussesComponent"),
                component,
            )
            edge_count += 1
        data_points.append(thread_node)
        resolver_name = resolver.name if resolver else "unknown"
        narrative_lines.append(
            f"Slack incident thread '{title}' in #{thread.channel_name} "
            f"resolved by {resolver_name}."
        )

    return "\n".join(narrative_lines), data_points, edge_count


async def process_external_app_sync(
    source: str,
    db: Session,
    tenant_id: uuid.UUID,
    *,
    use_github_fixture: bool = False,
    use_jira_fixture: bool = False,
    use_notion_fixture: bool = False,
    use_slack_fixture: bool = False,
    progress: Callable[[str, str], None] | None = None,
) -> dict[str, int | str]:
    """
    Transform raw app feed data, load into Cognee via add/cognify,
    and attach structured graph edges for multi-hop traversal.
    """
    def report(phase: str, message: str) -> None:
        if progress is not None:
            progress(phase, message)

    normalized = source.lower().strip()
    employee_nodes, component_nodes, components_by_id = _load_org_context(db, tenant_id)
    github_activities: list[GitHubPullRequestActivity] = []
    open_prs_by_login: dict[str, int] = {}
    jira_issues: list[JiraIssueActivity] = []
    notion_snapshot = None
    slack_snapshot = None
    slack_sync_stats: dict[str, int] | None = None
    config = None

    if normalized == "github":
        config = get_github_config(db, tenant_id)
        if not config:
            raise ValueError("GitHub integration is not configured.")
        report("fetching", "Fetching pull requests and file changes from GitHub…")
        github_activities, unmapped_paths, open_prs_by_login = await asyncio.to_thread(
            fetch_and_map_github_activity,
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
        report("fetching", "Fetching file contents, diffs, and blame metadata…")
        code_snapshots = await asyncio.to_thread(
            collect_github_code_snapshots,
            config,
            github_activities,
            use_fixture=use_github_fixture,
        )
        code_lines, code_points, code_edges = analyze_github_code_payload(
            code_snapshots,
            employee_nodes,
            component_nodes,
            db,
            tenant_id,
        )
        data_points.extend(code_points)
        edge_count += code_edges
        if code_lines:
            narrative = narrative + "\n" + "\n".join(code_lines)
        report("building_graph", "Building Cognee graph nodes from GitHub activity…")
        custom_prompt = (
            "Extract GitHub engineering activity including pull requests, commits, "
            "file diff pathways, LOC changes, source file contents, git blame line "
            "ownership, and map contributors to components via contributedTo, "
            "modifies, documentsComponent, and blameAttributedTo relationships."
        )
    elif normalized == "jira":
        config = get_jira_config(db, tenant_id)
        if not config:
            raise ValueError("Jira integration is not configured.")
        report("fetching", "Fetching Jira issues and assignees…")
        jira_issues = await asyncio.to_thread(
            fetch_and_map_jira_issues,
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
        report("building_graph", "Building Cognee graph nodes from Jira issues…")
        custom_prompt = (
            "Extract Jira issue metadata including ticket IDs, issue types, priorities, "
            "status indicators, and link assignees and blocked components via "
            "assignedTo and blocksComponent relationships."
        )
    elif normalized == "notion":
        config = get_notion_config(db, tenant_id)
        if not config:
            raise ValueError("Notion integration is not configured.")
        report("fetching", "Fetching Notion pages and workspace members…")
        component_names = {
            component_id: component.name
            for component_id, component in components_by_id.items()
        }
        if use_notion_fixture:
            pages, people_expertise = load_fixture_document_inventory()
        else:
            pages, people_expertise = await asyncio.to_thread(
                fetch_notion_document_inventory,
                config.integration_token,
                config.database_ids or None,
                component_names=component_names,
            )
        employees = db.query(Employee).filter(Employee.tenant_id == tenant_id).all()
        email_to_employee = {employee.email.lower(): employee.id for employee in employees}
        docs = inventory_dicts_to_records(
            pages,
            email_to_employee=email_to_employee,
        )
        narrative, data_points, edge_count = analyze_notion_payload(
            employee_nodes,
            component_nodes,
            docs,
        )
        report("building_graph", "Building Cognee graph nodes from Notion docs…")
        custom_prompt = (
            "Extract Notion documentation pages including runbooks, architecture docs, "
            "and ownership transfer templates. Link pages to components via documentedBy "
            "and authors via authoredBy relationships."
        )
        github_active = {
            component_id
            for component_id, owners in get_github_ownership().items()
            if owners
        }
        notion_snapshot = compute_notion_telemetry(
            db,
            tenant_id,
            docs,
            people_expertise=people_expertise,
            components_with_github_activity=github_active,
        )
    elif normalized == "slack":
        config = get_slack_config(db, tenant_id)
        if not config:
            raise ValueError("Slack integration is not configured.")
        report("fetching", "Fetching Slack incident threads…")
        component_names = {
            component_id: component.name
            for component_id, component in components_by_id.items()
        }
        threads, slack_users, sync_warnings, slack_sync_stats = await asyncio.to_thread(
            fetch_slack_incident_threads,
            config,
            component_names=component_names,
            use_fixture=use_slack_fixture,
        )
        slack_id_to_employee = _map_slack_users_to_employees(db, tenant_id, slack_users)
        notion_docs = _notion_docs_for_crosscheck(db, tenant_id)
        slack_snapshot = compute_slack_telemetry(
            db,
            tenant_id,
            threads,
            slack_id_to_employee=slack_id_to_employee,
            notion_docs=notion_docs or None,
        )
        if sync_warnings:
            slack_snapshot.sync_warnings.extend(sync_warnings)
        narrative, data_points, edge_count = analyze_slack_payload(
            employee_nodes,
            component_nodes,
            threads,
        )
        report("building_graph", "Building Cognee graph nodes from Slack threads…")
        if slack_snapshot.sync_warnings:
            narrative = (
                f"Warnings: {'; '.join(slack_snapshot.sync_warnings)}\n{narrative}"
            )
        custom_prompt = (
            "Extract Slack incident thread metadata including channel names, "
            "thread titles, and link resolvers to components via resolvedBy "
            "and discussesComponent relationships. Do not store message bodies."
        )
    else:
        raise ValueError(f"Unsupported integration source '{source}'.")

    ingest_plan = plan_sync_ingest(db, tenant_id, normalized, data_points)
    data_points = ingest_plan.to_ingest
    edge_count = count_graph_edges(data_points)

    report("building_graph", ingest_plan.progress_message())

    if data_points:
        report("building_graph", f"Indexing {len(data_points)} graph nodes into Cognee…")
        await tenant_add_data_points(tenant_id, data_points)
        record_synced_items(db, tenant_id, normalized, ingest_plan.ledger_items)

    dataset = tenant_dataset_name(tenant_id)
    if ingest_plan.should_cognify:
        report("cognifying", ingest_plan.cognify_message())
        await tenant_add_and_cognify(
            narrative,
            tenant_id,
            custom_prompt=custom_prompt,
        )
    else:
        report("cognifying", ingest_plan.cognify_message())

    report("finalizing", "Applying telemetry and finishing sync…")
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
    elif normalized == "notion" and notion_snapshot is not None:
        telemetry["notion_docs"] = apply_notion_telemetry(
            db,
            tenant_id,
            notion_snapshot,
        )
    elif normalized == "slack" and slack_snapshot is not None:
        telemetry["slack_incidents"] = apply_slack_telemetry_with_cache(
            db,
            tenant_id,
            slack_snapshot,
        )

    db.commit()

    mark_sync_completed(normalized)
    record_integration_sync(db, tenant_id, normalized)

    ledger_note = ingest_plan.result_note()
    narrative_preview = narrative[:280]
    if ledger_note:
        narrative_preview = f"{ledger_note} {narrative_preview}"[:280]

    result: dict[str, int | str] = {
        "source": normalized,
        "cognee_dataset": dataset,
        "documents_ingested": len(data_points) if data_points else 0,
        "graph_nodes_created": len(data_points),
        "graph_edges_created": edge_count,
        "narrative_preview": narrative_preview,
        "items_fetched": ingest_plan.fetched_count,
        "items_new": ingest_plan.new_count,
        "items_updated": ingest_plan.updated_count,
        "items_skipped": ingest_plan.skipped_count,
        "skipped_preview": ingest_plan.skipped_preview,
        "already_synced_note": ledger_note,
        "telemetry": telemetry or get_telemetry_snapshot(),
    }
    if normalized == "slack" and slack_sync_stats is not None:
        result["channels_discovered"] = slack_sync_stats.get("channels_discovered", 0)
        result["channels_synced"] = slack_sync_stats.get("channels_synced", 0)
        result["messages_ingested"] = slack_sync_stats.get("messages_ingested", 0)
    return result


async def process_global_sync(
    db: Session,
    tenant_id: uuid.UUID,
    sources: list[str],
) -> list[dict[str, int | str]]:
    results: list[dict[str, int | str]] = []
    for source in sources:
        results.append(await process_external_app_sync(source, db, tenant_id))
    return results
