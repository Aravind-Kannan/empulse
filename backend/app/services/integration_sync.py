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
from app.ontology.datapoints import ChangeEvent, CodeArtifact
from app.services.cognee_ingest import GraphComponent, GraphEmployee
from app.services.identity_resolver import resolve_author_employee_id
from app.services.github_code import (
    GitHubCodeFileSnapshot,
    collect_github_code_snapshots,
)
from app.services.github_client import (
    GitHubClient,
    fetch_github_pull_request_activity,
    parse_repository_url,
)
from app.services.github_path_mapper import apply_path_mapping
from app.services.github_touch import pr_merge_shas
from app.services.github_types import GitHubCommitActivity, GitHubPullRequestActivity
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
from app.services.tenant_cognee import tenant_add_data_points
from app.tenancy import tenant_dataset_name

from app.services.jira_client import fetch_jira_incident_issues, fetch_jira_issues
from app.services.jira_mapper import map_issue_to_component
from app.services.jira_types import JiraIssueActivity
from app.services.notion_client import (
    fetch_notion_document_inventory,
    load_fixture_document_inventory,
)
from app.services.notion_telemetry import (
    compute_notion_telemetry,
    inventory_dicts_to_records,
)
from app.services.notion_types import NotionDocRecord
from app.services.slack_client import fetch_slack_incident_threads
from app.services.slack_telemetry import compute_slack_telemetry
from app.services.slack_types import SlackThreadRecord
from app.services.sync_ledger import (
    count_graph_edges,
    plan_sync_ingest,
    record_synced_items,
)


class GraphCodeFile(DataPoint):
    """Deprecated — use app.ontology.datapoints.CodeArtifact."""

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
    """Deprecated — use app.ontology.datapoints.ChangeEvent."""

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


# Legacy graph types kept for backward-compatible disconnect cleanup only.
class GraphJiraTicket(DataPoint):
    ticket_id: str
    issue_type: str
    priority: str
    status: str
    project_key: str
    summary: str = ""
    assignedTo: SkipValidation[Any] = None
    blocksComponent: SkipValidation[Any] = None
    metadata: dict = {
        "index_fields": ["ticket_id", "issue_type", "status", "summary"],
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
        return {}, {}, {}

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
) -> tuple[
    list[GitHubPullRequestActivity],
    list[GitHubCommitActivity],
    list[str],
    dict[str, int],
]:
    repository_urls = config.resolved_repository_urls()
    all_activities: list[GitHubPullRequestActivity] = []
    all_commits: list[GitHubCommitActivity] = []
    all_unmapped: list[str] = []
    combined_open_prs: dict[str, int] = {}
    seen_activity_keys: set[str] = set()
    seen_commit_keys: set[str] = set()

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

        commits = GitHubClient(repo_config, use_fixture=use_fixture).fetch_branch_commit_activity(
            exclude_shas=pr_merge_shas(mapped),
        )
        mapped_commits, unmapped_commit_paths = apply_path_mapping(
            commits,
            path_component_map=config.path_component_map,
            repo_name=repo_name,
            components_by_id=components_by_id,
            default_component_id=config.default_component_id,
        )
        for commit in mapped_commits:
            if commit.dedupe_key in seen_commit_keys:
                continue
            seen_commit_keys.add(commit.dedupe_key)
            all_commits.append(commit)
        all_unmapped.extend(unmapped_commit_paths)

    return all_activities, all_commits, all_unmapped, combined_open_prs


def analyze_github_payload(
    config: GitHubConfigRequest,
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
    db: Session,
    tenant_id: uuid.UUID,
    activities: list[GitHubPullRequestActivity],
) -> tuple[str, list[ChangeEvent], int]:
    """Build ontology ChangeEvent nodes from live GitHub pull request activity."""
    from app.ontology.ingest import build_github_change_events

    components_by_id = {cid: component_nodes[cid] for cid in component_nodes}
    summary_lines, data_points, edge_count = build_github_change_events(
        config,
        activities,
        db=db,
        tenant_id=tenant_id,
        employee_nodes=employee_nodes,
        component_nodes=component_nodes,
        components_by_id=components_by_id,
    )
    return "\n".join(summary_lines), data_points, edge_count


def analyze_github_code_payload(
    snapshots: list[GitHubCodeFileSnapshot],
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
    db: Session,
    tenant_id: uuid.UUID,
    components_by_id: dict[str, Component] | None = None,
) -> tuple[list[str], list[CodeArtifact], int]:
    """Build ontology CodeArtifact nodes from file contents, diffs, and blame."""
    from app.ontology.ingest import build_github_code_artifacts

    if components_by_id is None:
        components_by_id = {}

    return build_github_code_artifacts(
        snapshots,
        db=db,
        tenant_id=tenant_id,
        employee_nodes=employee_nodes,
        component_nodes=component_nodes,
        components_by_id=components_by_id,
    )


def fetch_and_map_jira_issues(
    config: JiraConfigRequest,
    components_by_id: dict[str, Component],
    *,
    use_fixture: bool = False,
) -> list[JiraIssueActivity]:
    issues = fetch_jira_incident_issues(config, use_fixture=use_fixture)
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
) -> tuple[str, list, int]:
    """Build ontology WorkItem nodes from Jira issue activity."""
    from app.ontology.ingest import build_jira_work_items

    summary_lines, data_points, edge_count = build_jira_work_items(
        config,
        issues,
        db=db,
        tenant_id=tenant_id,
        employee_nodes=employee_nodes,
        component_nodes=component_nodes,
        components_by_id={cid: component_nodes[cid] for cid in component_nodes},
    )
    return "\n".join(summary_lines), data_points, edge_count


def analyze_notion_payload(
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
    docs: list[NotionDocRecord],
    *,
    components_by_id: dict[str, Component] | None = None,
) -> tuple[str, list, int]:
    """Build ontology Document nodes from Notion pages."""
    from app.ontology.ingest import build_notion_documents

    if components_by_id is None:
        components_by_id = {}

    summary_lines, data_points, edge_count = build_notion_documents(
        docs,
        employee_nodes=employee_nodes,
        component_nodes=component_nodes,
        components_by_id=components_by_id,
    )
    return "\n".join(summary_lines), data_points, edge_count


def analyze_slack_payload(
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
    threads: list[SlackThreadRecord],
    *,
    components_by_id: dict[str, Component] | None = None,
) -> tuple[str, list, int]:
    """Build ontology Discussion nodes from Slack incident threads."""
    from app.ontology.ingest import build_slack_discussions

    if components_by_id is None:
        components_by_id = {}

    summary_lines, data_points, edge_count = build_slack_discussions(
        threads,
        employee_nodes=employee_nodes,
        component_nodes=component_nodes,
        components_by_id=components_by_id,
    )
    return "\n".join(summary_lines), data_points, edge_count


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


async def process_external_app_sync(
    source: str,
    db: Session,
    tenant_id: uuid.UUID,
    *,
    use_github_fixture: bool = False,
    use_jira_fixture: bool = False,
    use_notion_fixture: bool = False,
    use_slack_fixture: bool = False,
    progress: Callable[[str, str, dict | None], None] | None = None,
) -> dict[str, int | str]:
    """
    Transform raw app feed data, load into Cognee via add/cognify,
    and attach structured graph edges for multi-hop traversal.
    """
    def report(
        phase: str,
        message: str,
        stats: dict[str, int | str] | None = None,
    ) -> None:
        if progress is not None:
            progress(phase, message, stats)

    normalized = source.lower().strip()
    config = None

    if normalized == "github":
        config = get_github_config(db, tenant_id)
        if not config:
            raise ValueError("GitHub integration is not configured.")
        report("fetching", "Discovering components from GitHub repositories…")
        from app.services.component_provisioning import provision_github_components

        await asyncio.to_thread(
            provision_github_components,
            db,
            tenant_id,
            config,
            use_fixture=use_github_fixture,
        )
        config = get_github_config(db, tenant_id)
    elif normalized == "jira":
        config = get_jira_config(db, tenant_id)
        if not config:
            raise ValueError("Jira integration is not configured.")
        report("fetching", "Discovering components from Jira projects…")
        from app.services.component_provisioning import provision_jira_components

        await asyncio.to_thread(
            provision_jira_components,
            db,
            tenant_id,
            config,
            use_fixture=use_jira_fixture,
        )
        config = get_jira_config(db, tenant_id)

    employee_nodes, component_nodes, components_by_id = _load_org_context(db, tenant_id)
    github_activities: list[GitHubPullRequestActivity] = []
    github_commits: list[GitHubCommitActivity] = []
    open_prs_by_login: dict[str, int] = {}
    jira_issues: list[JiraIssueActivity] = []
    notion_snapshot = None
    slack_snapshot = None
    slack_sync_stats: dict[str, int] | None = None
    cognify_extra_stats: dict[str, int | str] = {}

    if normalized == "github":
        if not config:
            raise ValueError("GitHub integration is not configured.")
        from app.services.github_identity import prepare_github_identity_context

        report("fetching", "Loading GitHub contributors for identity mapping…")
        await asyncio.to_thread(prepare_github_identity_context, db, tenant_id, config)
        report("fetching", "Fetching pull requests, commits, and file changes from GitHub…")
        github_activities, github_commits, unmapped_paths, open_prs_by_login = await asyncio.to_thread(
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
            components_by_id=components_by_id,
        )
        data_points.extend(code_points)
        edge_count += code_edges
        if code_lines:
            narrative = narrative + "\n" + "\n".join(code_lines)
        cognify_extra_stats["prs_fetched"] = len(github_activities)
        cognify_extra_stats["commits_fetched"] = len(github_commits)
        cognify_extra_stats["code_files_fetched"] = len(code_snapshots)
        report("building_graph", "Building ontology graph nodes from GitHub activity…")
    elif normalized == "jira":
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
        cognify_extra_stats["issues_fetched"] = len(jira_issues)
        report("building_graph", "Building ontology graph nodes from Jira issues…")
    elif normalized == "notion":
        config = get_notion_config(db, tenant_id)
        if not config:
            raise ValueError("Notion integration is not configured.")
        report("fetching", "Fetching Notion pages and workspace members…")
        component_names = {
            component_id: component.name
            for component_id, component in components_by_id.items()
        }
        github_config = get_github_config(db, tenant_id)
        path_component_map = dict(github_config.path_component_map or {}) if github_config else {}
        repo_doc_pages: list[dict] = []
        from app.services.notion_repo_pack import (
            fetch_github_notion_doc_pack,
            fetch_local_notion_doc_pack,
        )

        if github_config and github_config.personal_access_token:
            repo_urls = [
                url.strip()
                for url in (github_config.repository_urls or [])
                if url.strip()
            ]
            if not repo_urls and github_config.repository_url:
                repo_urls = [github_config.repository_url.strip()]
            branch = (github_config.branch_target or "main").strip() or "main"
            for repo_url in repo_urls:
                repo_doc_pages.extend(
                    fetch_github_notion_doc_pack(
                        github_config.personal_access_token,
                        repo_url,
                        component_names=component_names,
                        path_component_map=path_component_map,
                        branch=branch,
                    )
                )
        if not repo_doc_pages:
            repo_doc_pages = fetch_local_notion_doc_pack(
                component_names=component_names,
                path_component_map=path_component_map,
            )
        if use_notion_fixture:
            pages, people_expertise = load_fixture_document_inventory()
        else:
            pages, people_expertise = await asyncio.to_thread(
                fetch_notion_document_inventory,
                config.integration_token,
                config.database_ids or None,
                component_names=component_names,
                path_component_map=path_component_map,
                repo_doc_pages=repo_doc_pages,
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
            components_by_id=components_by_id,
        )
        cognify_extra_stats["pages_fetched"] = len(docs)
        report("building_graph", "Building ontology graph nodes from Notion docs…")
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
        report("fetching", "Fetching Slack messages from joined channels…")
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
            components_by_id=components_by_id,
        )
        cognify_extra_stats["threads_fetched"] = len(threads)
        if slack_sync_stats:
            for key in ("channels_discovered", "channels_synced", "messages_ingested"):
                if key in slack_sync_stats:
                    cognify_extra_stats[key] = slack_sync_stats[key]
        report("building_graph", "Building ontology graph nodes from Slack threads…")
        if slack_snapshot.sync_warnings:
            narrative = (
                f"Warnings: {'; '.join(slack_snapshot.sync_warnings)}\n{narrative}"
            )
    else:
        raise ValueError(f"Unsupported integration source '{source}'.")

    from app.ontology.crosslinks import apply_ontology_cross_links
    from app.ontology.enrichment import run_post_structured_cognify_enrichment

    ingest_plan = plan_sync_ingest(db, tenant_id, normalized, data_points)
    data_points = ingest_plan.to_ingest
    edge_count = count_graph_edges(data_points)
    edge_count += apply_ontology_cross_links(data_points)

    report("building_graph", ingest_plan.progress_message())

    if data_points:
        report("building_graph", f"Indexing {len(data_points)} graph nodes into Cognee…")
        await tenant_add_data_points(
            tenant_id,
            data_points,
            employee_nodes=employee_nodes,
            component_nodes=component_nodes,
        )
        record_synced_items(db, tenant_id, normalized, ingest_plan.ledger_items)

    dataset = tenant_dataset_name(tenant_id)
    await run_post_structured_cognify_enrichment(
        normalized,
        tenant_id,
        narrative,
        ingest_plan,
        report=report,
        extra_stats=cognify_extra_stats or None,
    )

    report("finalizing", "Applying telemetry and finishing sync…")
    telemetry: dict[str, object] = {}
    if normalized == "github":
        telemetry["github_ownership"] = apply_github_telemetry(
            db,
            tenant_id,
            github_activities,
            commit_activities=github_commits,
            open_prs_by_login=open_prs_by_login or None,
        )
        from app.services.component_management import sync_assignments_from_github_ownership

        telemetry["assignments_created"] = sync_assignments_from_github_ownership(
            db, tenant_id
        )
    elif normalized == "jira":
        high_priorities = set(config.high_priorities) if config else HIGH_PRIORITIES
        telemetry["jira_backlog"] = apply_jira_telemetry(
            db,
            tenant_id,
            jira_issues,
            high_priorities=high_priorities,
        )
        from app.services.jira_service import get_jira_integration

        integration = get_jira_integration(db, tenant_id)
        if integration:
            integration.status = "connected"
            integration.last_synced_at = datetime.now(UTC).replace(tzinfo=None)
            integration.issues_synced_count = len(jira_issues)
            integration.updated_at = datetime.now(UTC).replace(tzinfo=None)
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

    if normalized in {"jira", "slack"}:
        if normalized == "slack":
            from app.services.slack_client import invalidate_slack_threads_cache
            from app.services.provider_members import invalidate_provider_members_cache

            invalidate_slack_threads_cache()
            invalidate_provider_members_cache(tenant_id, "slack")
        from app.services.incident_feed import invalidate_incident_feed_cache

        invalidate_incident_feed_cache(tenant_id)

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
