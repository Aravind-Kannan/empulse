"""In-memory telemetry derived from integration syncs, feeding ERA/KRA engines."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.operational import Assignment, Component, Employee, GitHubOwnershipSnapshot
from app.services.github_types import GitHubCommitActivity, GitHubPullRequestActivity
from app.services.identity_resolver import resolve_author_employee_id
from app.services.integration_config_store import (
    INTEGRATION_SOURCES,
    get_integration_last_synced,
    get_telemetry_cache,
    save_telemetry_cache,
)
from app.services.jira_types import JiraEmployeeSignals, JiraIssueActivity
from app.services.slack_types import (
    SlackEmployeeSignals,
    SlackMessageRecord,
    SlackThreadRecord,
)

_jira_backlog_by_employee: dict[str, int] = {}
_jira_employee_signals: dict[str, JiraEmployeeSignals] = {}
_jira_issues_cache: list[JiraIssueActivity] = []
_github_ownership: dict[str, dict[str, float]] = {}
_github_spof_components: set[str] = set()
_github_employee_context: dict[str, "GitHubEmployeeTelemetry"] = {}
_github_open_prs_by_login: dict[str, int] = {}
_component_bus_factor: dict[str, int] = {}
_employee_max_doa_pct: dict[str, float] = {}
_doa_available = False
_doa_decay_evidence: list[dict] = []
_github_activities: list[GitHubPullRequestActivity] = []
_review_network = None
_jira_synced = False
_github_synced = False
_notion_synced = False
_notion_component_sources: dict[str, list[str]] = {}
_notion_employee_signals: dict[str, object] = {}
_notion_expertise_warnings: list[dict] = []
_slack_synced = False
_slack_employee_signals: dict[str, object] = {}
_slack_escalation_warnings: list[dict] = []
_slack_threads_cache: list = []
_sync_timestamps: dict[str, str] = {}

HIGH_PRIORITIES = frozenset({"Highest", "High", "Critical"})
SPOF_OWNERSHIP_THRESHOLD = 85.0
# Engineers at or above this share count as meaningful backup context.
SPOF_BACKUP_CONTRIBUTOR_MIN = 20.0


def is_github_spof_component(
    contributors: dict[str, float],
    *,
    bus_factor: int | None = None,
) -> bool:
    """True when GitHub telemetry shows concentrated knowledge risk.

    Bus factor ≤ 1 alone is not enough: blame-weighted DOA can mark one engineer
    authoritative on most files while others maintain the same path with real
    context (common on small teams). Require either dominant ownership (>85%) or
    bus factor 1 with fewer than two meaningful contributors.
    """
    if not contributors:
        return False
    max_pct = max(contributors.values())
    if max_pct > SPOF_OWNERSHIP_THRESHOLD:
        return True
    if bus_factor is None or bus_factor > 1:
        return False
    meaningful_count = sum(
        1 for pct in contributors.values() if pct >= SPOF_BACKUP_CONTRIBUTOR_MIN
    )
    return meaningful_count < 2


def spof_components_from_telemetry(
    ownership: dict[str, dict[str, float]],
    bus_factors: dict[str, int] | None = None,
) -> set[str]:
    """Derive GitHub SPOF component ids from ownership splits and bus factors."""
    component_ids = set(ownership.keys())
    if bus_factors:
        component_ids |= set(bus_factors.keys())
    return {
        component_id
        for component_id in component_ids
        if is_github_spof_component(
            ownership.get(component_id, {}),
            bus_factor=(bus_factors or {}).get(component_id),
        )
    }


def is_team_open_p1_issue(issue: JiraIssueActivity) -> bool:
    """Open bug/incident-style issue counted in ERA Open P1 KPI."""
    if issue.is_done or issue.is_subtask:
        return False
    return issue.priority in HIGH_PRIORITIES


def _parse_cache_datetime(value: object) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _jira_issue_to_cache_row(issue: JiraIssueActivity) -> dict[str, object]:
    return {
        "issue_key": issue.issue_key,
        "issue_type": issue.issue_type,
        "priority": issue.priority,
        "status": issue.status,
        "status_category": issue.status_category,
        "project_key": issue.project_key,
        "summary": issue.summary,
        "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
        "assignee_provider_user_id": issue.assignee_provider_user_id,
        "assignee_email": issue.assignee_email,
        "component_id": issue.component_id,
        "jira_component_names": list(issue.jira_component_names),
        "labels": list(issue.labels),
        "story_points": issue.story_points,
        "is_subtask": issue.is_subtask,
        "issue_url": issue.issue_url,
    }


def _jira_issue_from_cache_row(row: dict[str, object]) -> JiraIssueActivity:
    return JiraIssueActivity(
        issue_key=str(row.get("issue_key", "")),
        issue_type=str(row.get("issue_type", "")),
        priority=str(row.get("priority", "")),
        status=str(row.get("status", "")),
        status_category=str(row.get("status_category", "")),
        project_key=str(row.get("project_key", "")),
        summary=str(row.get("summary", "")),
        updated_at=_parse_cache_datetime(row.get("updated_at")),
        assignee_provider_user_id=row.get("assignee_provider_user_id"),  # type: ignore[arg-type]
        assignee_email=row.get("assignee_email"),  # type: ignore[arg-type]
        component_id=row.get("component_id"),  # type: ignore[arg-type]
        jira_component_names=[
            str(name) for name in (row.get("jira_component_names") or [])
        ],
        labels=[str(label) for label in (row.get("labels") or [])],
        story_points=float(row.get("story_points") or 0.0),
        is_subtask=bool(row.get("is_subtask")),
        issue_url=row.get("issue_url"),  # type: ignore[arg-type]
    )


def _slack_message_to_cache_row(message: SlackMessageRecord) -> dict[str, object]:
    return {
        "ts": message.ts,
        "user_id": message.user_id,
        "text": message.text,
        "is_bot": message.is_bot,
        "reactions": list(message.reactions),
    }


def _slack_message_from_cache_row(row: dict[str, object]) -> SlackMessageRecord:
    return SlackMessageRecord(
        ts=str(row.get("ts", "")),
        user_id=str(row.get("user_id", "")),
        text=str(row.get("text", "")),
        is_bot=bool(row.get("is_bot")),
        reactions=[str(item) for item in (row.get("reactions") or [])],
    )


def _slack_thread_to_cache_row(thread: SlackThreadRecord) -> dict[str, object]:
    return {
        "channel_id": thread.channel_id,
        "channel_name": thread.channel_name,
        "thread_ts": thread.thread_ts,
        "parent_text": thread.parent_text,
        "messages": [_slack_message_to_cache_row(msg) for msg in thread.messages],
        "component_id": thread.component_id,
        "is_incident_channel": thread.is_incident_channel,
        "is_on_call_channel": thread.is_on_call_channel,
        "mentioned_user_ids": list(thread.mentioned_user_ids),
        "resolved_by_employee_id": thread.resolved_by_employee_id,
        "resolved_at": thread.resolved_at.isoformat() if thread.resolved_at else None,
        "thread_url": thread.thread_url,
    }


def _slack_thread_from_cache_row(row: dict[str, object]) -> SlackThreadRecord:
    messages_raw = row.get("messages")
    messages = [
        _slack_message_from_cache_row(item)
        for item in messages_raw
        if isinstance(item, dict)
    ] if isinstance(messages_raw, list) else []
    return SlackThreadRecord(
        channel_id=str(row.get("channel_id", "")),
        channel_name=str(row.get("channel_name", "")),
        thread_ts=str(row.get("thread_ts", "")),
        parent_text=str(row.get("parent_text", "")),
        messages=messages,
        component_id=row.get("component_id"),  # type: ignore[arg-type]
        is_incident_channel=bool(row.get("is_incident_channel")),
        is_on_call_channel=bool(row.get("is_on_call_channel")),
        mentioned_user_ids=[
            str(item) for item in (row.get("mentioned_user_ids") or [])
        ],
        resolved_by_employee_id=row.get("resolved_by_employee_id"),  # type: ignore[arg-type]
        resolved_at=_parse_cache_datetime(row.get("resolved_at")),
        thread_url=str(row.get("thread_url", "")),
    )


@dataclass
class GitHubEmployeeTelemetry:
    backup_review_score: float = 50.0
    open_prs: int = 0
    recent_pr_count: int = 0
    unique_reviewers: int = 0
    review_concentration_pct: float = 0.0
    sole_reviewer_count: int = 0
    reviews_given_count: int = 0
    isolation_score: float = 0.0
    no_backup_pr_urls: list[str] = field(default_factory=list)
    latest_pr_url: str | None = None
    top_pr_url_by_component: dict[str, str] = field(default_factory=dict)


def mark_sync_completed(source: str) -> None:
    """Record ISO timestamp when an integration sync finishes successfully."""
    normalized = source.lower().strip()
    _sync_timestamps[normalized] = datetime.now(UTC).isoformat()


def clear_integration_telemetry(source: str) -> None:
    """Drop in-memory telemetry for a disconnected integration source."""
    global _jira_synced, _github_synced, _notion_synced, _slack_synced, _doa_available, _review_network

    normalized = source.lower().strip()
    _sync_timestamps.pop(normalized, None)

    if normalized == "github":
        _github_synced = False
        _github_ownership.clear()
        _github_spof_components.clear()
        _github_employee_context.clear()
        _github_open_prs_by_login.clear()
        _component_bus_factor.clear()
        _employee_max_doa_pct.clear()
        _doa_available = False
        _doa_decay_evidence.clear()
        _github_activities.clear()
        _review_network = None
    elif normalized == "jira":
        _jira_synced = False
        _jira_backlog_by_employee.clear()
        _jira_employee_signals.clear()
        _jira_issues_cache.clear()
    elif normalized == "notion":
        _notion_synced = False
        _notion_component_sources.clear()
        _notion_employee_signals.clear()
        _notion_expertise_warnings.clear()
    elif normalized == "slack":
        _slack_synced = False
        _slack_employee_signals.clear()
        _slack_escalation_warnings.clear()
        _slack_threads_cache.clear()


def get_sync_freshness() -> dict[str, str | None]:
    return {
        "github": _sync_timestamps.get("github"),
        "jira": _sync_timestamps.get("jira"),
        "slack": _sync_timestamps.get("slack"),
        "notion": _sync_timestamps.get("notion"),
    }


def _main_engineer_for_component(
    db: Session,
    component_id: str,
    tenant_id: uuid.UUID,
) -> str | None:
    assignments = (
        db.query(Assignment)
        .filter(
            Assignment.component_id == component_id,
            Assignment.tenant_id == tenant_id,
        )
        .all()
    )
    if not assignments:
        return None
    return assignments[0].employee_id


def apply_jira_telemetry(
    db: Session,
    tenant_id: uuid.UUID,
    issues: list[JiraIssueActivity] | None = None,
    *,
    high_priorities: set[str] | None = None,
) -> dict[str, int]:
    """Aggregate Jira issues into employee signals and refresh component counts."""
    global _jira_synced, _jira_issues_cache

    if issues is None:
        if hydrate_jira_telemetry_from_db(db, tenant_id):
            return dict(_jira_backlog_by_employee)
        return {}

    priorities = high_priorities or HIGH_PRIORITIES
    valid_components = {
        row[0]
        for row in db.query(Component.id).filter(Component.tenant_id == tenant_id).all()
    }

    backlog: dict[str, int] = defaultdict(int)
    employee_open_tasks: dict[str, int] = defaultdict(int)
    employee_open_p1_p2: dict[str, int] = defaultdict(int)
    employee_epics: dict[str, int] = defaultdict(int)
    employee_sprint_points: dict[str, float] = defaultdict(float)
    employee_urls: dict[str, list[str]] = defaultdict(list)
    component_open_tasks: dict[str, int] = defaultdict(int)
    component_unresolved: dict[str, int] = defaultdict(int)

    for issue in issues:
        if issue.is_done:
            continue
        component_id = issue.component_id
        if component_id and component_id not in valid_components:
            component_id = None

        assignee_id: str | None = None
        if issue.assignee_provider_user_id:
            assignee_id = resolve_author_employee_id(
                db,
                tenant_id,
                "jira",
                issue.assignee_provider_user_id,
                email_hint=issue.assignee_email,
                quarantine_event_type="jira_issue",
                quarantine_payload={"issue_key": issue.issue_key},
            )

        if assignee_id and not issue.is_subtask:
            employee_open_tasks[assignee_id] += 1
            if is_team_open_p1_issue(issue):
                employee_open_p1_p2[assignee_id] += 1
            if issue.issue_type.lower() == "epic":
                employee_epics[assignee_id] += 1
            if issue.story_points > 0:
                employee_sprint_points[assignee_id] += issue.story_points
            if issue.issue_url:
                employee_urls[assignee_id].append(issue.issue_url)

        if component_id:
            if assignee_id and not issue.is_subtask:
                component_open_tasks[component_id] += 1
            if issue.is_bug_or_incident and is_team_open_p1_issue(issue):
                component_unresolved[component_id] += 1

        is_unassigned_boost_candidate = (
            not assignee_id
            and issue.is_bug_or_incident
            and issue.priority in priorities
            and component_id
        )
        if is_unassigned_boost_candidate:
            main_engineer = _main_engineer_for_component(db, component_id, tenant_id)
            if main_engineer:
                backlog[main_engineer] += 1
                if issue.issue_url:
                    employee_urls[main_engineer].append(issue.issue_url)

    for component_id in valid_components:
        row = (
            db.query(Component)
            .filter(Component.id == component_id, Component.tenant_id == tenant_id)
            .one_or_none()
        )
        if row:
            row.open_tasks_count = component_open_tasks.get(component_id, 0)
            row.unresolved_incidents = component_unresolved.get(component_id, 0)

    employee_ids = (
        set(employee_open_tasks)
        | set(backlog)
        | set(employee_epics)
    )
    signals: dict[str, JiraEmployeeSignals] = {}
    for employee_id in employee_ids:
        signals[employee_id] = JiraEmployeeSignals(
            employee_id=employee_id,
            open_tasks=employee_open_tasks.get(employee_id, 0),
            open_p1_p2=employee_open_p1_p2.get(employee_id, 0),
            jira_backlog_boost=backlog.get(employee_id, 0),
            epic_owner_count=employee_epics.get(employee_id, 0),
            sprint_points=employee_sprint_points.get(employee_id, 0.0),
            sample_issue_urls=employee_urls.get(employee_id, [])[:5],
        )

    _jira_backlog_by_employee.clear()
    _jira_backlog_by_employee.update(backlog)
    _jira_employee_signals.clear()
    _jira_employee_signals.update(signals)
    _jira_issues_cache = list(issues)
    _jira_synced = True
    db.flush()
    save_telemetry_cache(
        db,
        tenant_id,
        "jira",
        {
            "backlog_by_employee": dict(backlog),
            "employee_signals": {
                employee_id: {
                    "employee_id": row.employee_id,
                    "open_tasks": row.open_tasks,
                    "open_p1_p2": row.open_p1_p2,
                    "jira_backlog_boost": row.jira_backlog_boost,
                    "epic_owner_count": row.epic_owner_count,
                    "sprint_points": row.sprint_points,
                    "sample_issue_urls": list(row.sample_issue_urls),
                }
                for employee_id, row in signals.items()
            },
            "issues": [_jira_issue_to_cache_row(issue) for issue in issues],
        },
    )
    return dict(backlog)


def _compute_ownership_from_activities(
    db: Session,
    tenant_id: uuid.UUID,
    activities: list[GitHubPullRequestActivity],
    *,
    open_prs_by_login: dict[str, int] | None = None,
) -> tuple[dict[str, dict[str, float]], set[str], dict[str, GitHubEmployeeTelemetry]]:
    loc_by_component: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    employee_context: dict[str, GitHubEmployeeTelemetry] = defaultdict(GitHubEmployeeTelemetry)
    pr_urls_by_component_employee: dict[tuple[str, str], str] = {}
    reviewers_by_employee: dict[str, set[str]] = defaultdict(set)
    pr_count_by_employee: dict[str, int] = defaultdict(int)

    open_prs_by_login = open_prs_by_login or _github_open_prs_by_login

    for activity in activities:
        if activity.author_type == "Bot":
            continue

        author_id = resolve_author_employee_id(
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
        if not author_id:
            continue

        pr_count_by_employee[author_id] += 1
        ctx = employee_context[author_id]
        ctx.latest_pr_url = activity.pr_url
        ctx.open_prs = open_prs_by_login.get(activity.author_login.lower(), 0)

        for reviewer in activity.reviewer_logins:
            if reviewer.lower() != activity.author_login.lower():
                reviewers_by_employee[author_id].add(reviewer.lower())

        for file_change in activity.files:
            component_id = file_change.component_id
            if not component_id:
                continue
            loc = file_change.loc_added + file_change.loc_removed
            if loc <= 0:
                continue
            loc_by_component[component_id][author_id] += loc
            existing = pr_urls_by_component_employee.get((component_id, author_id))
            if not existing or loc > 0:
                pr_urls_by_component_employee[(component_id, author_id)] = activity.pr_url

    ownership: dict[str, dict[str, float]] = {}
    spof_components: set[str] = set()

    for component_id, contributors in loc_by_component.items():
        total_loc = sum(contributors.values()) or 1
        ownership[component_id] = {
            employee_id: round((loc / total_loc) * 100, 1)
            for employee_id, loc in contributors.items()
        }
        if contributors:
            if is_github_spof_component(ownership[component_id]):
                spof_components.add(component_id)

    for employee_id, ctx in employee_context.items():
        unique_reviewers = reviewers_by_employee.get(employee_id, set())
        ctx.unique_reviewers = len(unique_reviewers)
        ctx.recent_pr_count = pr_count_by_employee.get(employee_id, 0)
        for (component_id, emp_id), url in pr_urls_by_component_employee.items():
            if emp_id == employee_id:
                ctx.top_pr_url_by_component[component_id] = url

    return ownership, spof_components, dict(employee_context)


def _persist_ownership_snapshots(
    db: Session,
    tenant_id: uuid.UUID,
    ownership: dict[str, dict[str, float]],
) -> None:
    valid_components = {
        row[0]
        for row in db.query(Component.id)
        .filter(Component.tenant_id == tenant_id)
        .all()
    }
    valid_employees = {
        row[0]
        for row in db.query(Assignment.employee_id)
        .filter(Assignment.tenant_id == tenant_id)
        .all()
    }
    if not valid_employees:
        valid_employees = {
            row[0]
            for row in db.query(Employee.id)
            .filter(Employee.tenant_id == tenant_id)
            .all()
        }

    db.query(GitHubOwnershipSnapshot).filter(
        GitHubOwnershipSnapshot.tenant_id == tenant_id
    ).delete(synchronize_session=False)
    now = datetime.now(UTC)
    for component_id, contributors in ownership.items():
        if component_id not in valid_components:
            continue
        for employee_id, pct in contributors.items():
            if employee_id not in valid_employees:
                continue
            db.add(
                GitHubOwnershipSnapshot(
                    tenant_id=tenant_id,
                    component_id=component_id,
                    employee_id=employee_id,
                    ownership_pct=pct,
                    computed_at=now,
                )
            )
    db.flush()


def _load_ownership_from_db(db: Session, tenant_id: uuid.UUID) -> bool:
    rows = (
        db.query(GitHubOwnershipSnapshot)
        .filter(GitHubOwnershipSnapshot.tenant_id == tenant_id)
        .all()
    )
    if not rows:
        return False

    ownership: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        ownership[row.component_id][row.employee_id] = row.ownership_pct

    spof_components = spof_components_from_telemetry(ownership)

    _github_ownership.clear()
    _github_ownership.update(dict(ownership))
    _github_spof_components.clear()
    _github_spof_components.update(spof_components)
    return True


def _load_doa_from_db(db: Session, tenant_id: uuid.UUID) -> bool:
    from app.models.operational import DoaFileSnapshot
    from app.services.github_doa import compute_bus_factor, DOA_AUTHOR_THRESHOLD

    rows = (
        db.query(DoaFileSnapshot)
        .filter(DoaFileSnapshot.tenant_id == tenant_id)
        .all()
    )
    if not rows:
        return False

    global _doa_available, _component_bus_factor, _employee_max_doa_pct
    per_component_files: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    contributor_weight: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    employee_max: dict[str, float] = defaultdict(float)

    for row in rows:
        contributor_weight[row.component_id][row.employee_id] += row.doa_score
        employee_max[row.employee_id] = max(employee_max[row.employee_id], row.doa_score * 100.0)
        if row.is_author or row.doa_score >= DOA_AUTHOR_THRESHOLD:
            per_component_files[row.component_id][row.file_path].append(row.employee_id)

    ownership: dict[str, dict[str, float]] = {}
    bus_factor: dict[str, int] = {}

    for component_id, weights in contributor_weight.items():
        total = sum(weights.values()) or 1.0
        ownership[component_id] = {
            employee_id: round((weight / total) * 100, 1)
            for employee_id, weight in weights.items()
        }
        bus_factor[component_id] = compute_bus_factor(
            per_component_files.get(component_id, {})
        )

    spof_components = spof_components_from_telemetry(ownership, bus_factor)

    _github_ownership.clear()
    _github_ownership.update(ownership)
    _github_spof_components.clear()
    _github_spof_components.update(spof_components)
    _component_bus_factor.clear()
    _component_bus_factor.update(bus_factor)
    _employee_max_doa_pct.clear()
    _employee_max_doa_pct.update(dict(employee_max))
    _doa_available = True
    return True


def hydrate_github_telemetry_from_db(db: Session, tenant_id: uuid.UUID) -> bool:
    global _github_synced
    if _github_synced:
        return True
    if _load_ownership_from_db(db, tenant_id):
        _load_doa_from_db(db, tenant_id)
        _github_synced = True
        return True
    if _load_doa_from_db(db, tenant_id):
        _github_synced = True
        return True
    return False


def apply_github_telemetry(
    db: Session,
    tenant_id: uuid.UUID,
    activities: list[GitHubPullRequestActivity] | None = None,
    *,
    commit_activities: list[GitHubCommitActivity] | None = None,
    open_prs_by_login: dict[str, int] | None = None,
) -> dict[str, dict[str, float]]:
    """
    Derive directory ownership splits from GitHub activity and persist snapshots.
    Components with >85% single-contributor ownership are flagged as SPOF.
    """
    global _github_synced, _github_employee_context, _doa_available
    global _component_bus_factor, _employee_max_doa_pct, _doa_decay_evidence
    global _github_activities, _review_network

    if activities is None:
        if hydrate_github_telemetry_from_db(db, tenant_id):
            return _github_ownership
        return {}

    if open_prs_by_login:
        _github_open_prs_by_login.clear()
        _github_open_prs_by_login.update(open_prs_by_login)

    from app.services.github_doa import persist_doa_snapshots

    doa_result = persist_doa_snapshots(
        db, tenant_id, activities, commit_activities
    )
    _doa_available = bool(doa_result.snapshots)
    _component_bus_factor.clear()
    _component_bus_factor.update(doa_result.bus_factor_by_component)
    _employee_max_doa_pct.clear()
    _employee_max_doa_pct.update(doa_result.employee_max_doa_pct)
    _doa_decay_evidence = list(doa_result.decay_evidence)

    from app.services.github_file_risk import persist_file_risk_snapshots
    from app.services.integration_config_store import get_github_config

    github_config = get_github_config(db, tenant_id)
    repo_path = ""
    if github_config and github_config.repository_url:
        from app.services.github_client import parse_repository_url

        owner, repo = parse_repository_url(github_config.repository_url)
        repo_path = f"{owner}/{repo}"
    persist_file_risk_snapshots(
        db,
        tenant_id,
        activities,
        commit_activities,
        repo_path=repo_path,
    )

    ownership, spof_components, employee_context = _compute_ownership_from_activities(
        db,
        tenant_id,
        activities,
        open_prs_by_login=open_prs_by_login,
    )

    if doa_result.ownership:
        ownership = doa_result.ownership
        spof_components = spof_components_from_telemetry(
            ownership,
            doa_result.bus_factor_by_component,
        )

    _github_ownership.clear()
    _github_ownership.update(ownership)
    _github_spof_components.clear()
    _github_spof_components.update(spof_components)
    from app.services.github_reviews import build_review_network

    component_rows = (
        db.query(Component).filter(Component.tenant_id == tenant_id).all()
    )
    component_by_id = {row.id: row for row in component_rows}
    review_network = build_review_network(
        db,
        tenant_id,
        activities,
        since_days=90,
        component_by_id=component_by_id,
        bus_factor_by_component=_component_bus_factor,
    )
    _review_network = review_network
    _github_activities = list(activities)

    for employee_id, review_metrics in review_network.metrics_by_employee.items():
        ctx = employee_context.setdefault(employee_id, GitHubEmployeeTelemetry())
        ctx.backup_review_score = review_metrics.backup_review_score
        ctx.unique_reviewers = review_metrics.unique_reviewers_on_prs
        ctx.recent_pr_count = review_metrics.recent_pr_count
        ctx.review_concentration_pct = review_metrics.review_concentration_pct
        ctx.sole_reviewer_count = review_metrics.sole_reviewer_count
        ctx.reviews_given_count = review_metrics.reviews_given_count
        ctx.isolation_score = review_metrics.isolation_score
        ctx.no_backup_pr_urls = list(review_metrics.no_backup_pr_urls)

    _github_employee_context.clear()
    _github_employee_context.update(employee_context)

    _persist_ownership_snapshots(db, tenant_id, ownership)
    _github_synced = True
    return ownership


def apply_github_blame_telemetry(
    db: Session,
    tenant_id: uuid.UUID,
    snapshots: list,
) -> dict[str, dict[str, float]]:
    """
    Refresh KRA/ERA ownership from full-repo git blame.

    Repo sync stores rich blame in Cognee, but dashboards read PostgreSQL DOA
    snapshots — this bridges blame line ownership into those graphs.
    """
    global _github_synced, _doa_available
    global _component_bus_factor, _employee_max_doa_pct, _doa_decay_evidence
    global _github_ownership, _github_spof_components

    from app.services.github_doa import persist_doa_from_code_snapshots

    if not snapshots:
        return dict(_github_ownership)

    doa_result = persist_doa_from_code_snapshots(db, tenant_id, snapshots)
    _doa_available = bool(doa_result.snapshots)
    _component_bus_factor.clear()
    _component_bus_factor.update(doa_result.bus_factor_by_component)
    _employee_max_doa_pct.clear()
    _employee_max_doa_pct.update(doa_result.employee_max_doa_pct)
    _doa_decay_evidence = list(doa_result.decay_evidence)

    ownership = doa_result.ownership
    spof_components = spof_components_from_telemetry(
        ownership,
        doa_result.bus_factor_by_component,
    )

    _github_ownership.clear()
    _github_ownership.update(ownership)
    _github_spof_components.clear()
    _github_spof_components.update(spof_components)
    _persist_ownership_snapshots(db, tenant_id, ownership)
    _github_synced = True
    return ownership


def get_jira_backlog_boost(employee_id: str) -> int:
    return _jira_backlog_by_employee.get(employee_id, 0)


def get_jira_employee_signals(employee_id: str) -> JiraEmployeeSignals | None:
    return _jira_employee_signals.get(employee_id)


def get_jira_open_tasks(employee_id: str) -> int | None:
    signals = _jira_employee_signals.get(employee_id)
    return signals.open_tasks if signals else None


def get_jira_epic_owner_count(employee_id: str) -> int:
    signals = _jira_employee_signals.get(employee_id)
    return signals.epic_owner_count if signals else 0


def get_cached_jira_issues() -> list[JiraIssueActivity]:
    return list(_jira_issues_cache)


def count_team_open_p1_issues() -> int:
    """Count open high-priority Jira issues across the team."""
    if not _jira_synced:
        return 0
    return sum(1 for issue in _jira_issues_cache if is_team_open_p1_issue(issue))


def list_team_open_p1_issues(
    db: Session | None = None,
    tenant_id: uuid.UUID | None = None,
) -> list[JiraIssueActivity]:
    """List open high-priority issues from the Jira telemetry cache."""
    if not _jira_synced and db is not None and tenant_id is not None:
        hydrate_jira_telemetry_from_db(db, tenant_id)
    if not _jira_synced:
        return []
    issues = [issue for issue in _jira_issues_cache if is_team_open_p1_issue(issue)]
    issues.sort(
        key=lambda row: (
            {"Critical": 0, "Highest": 1, "High": 2}.get(row.priority, 9),
            -(
                (row.updated_at or datetime.min.replace(tzinfo=UTC)).timestamp()
            ),
        ),
    )
    return issues


def get_unassigned_p1_by_component(
    *,
    high_priorities: set[str] | None = None,
) -> dict[str, list[JiraIssueActivity]]:
    """Unassigned high-priority bugs/incidents grouped by mapped component."""
    if not _jira_synced:
        return {}
    priorities = high_priorities or HIGH_PRIORITIES
    grouped: dict[str, list[JiraIssueActivity]] = defaultdict(list)
    for issue in _jira_issues_cache:
        if issue.is_done:
            continue
        if issue.assignee_provider_user_id:
            continue
        if not issue.is_bug_or_incident:
            continue
        if issue.priority not in priorities:
            continue
        if not issue.component_id:
            continue
        grouped[issue.component_id].append(issue)
    return dict(grouped)


def has_jira_sync() -> bool:
    return _jira_synced


def has_github_sync() -> bool:
    return _github_synced


def get_github_ownership() -> dict[str, dict[str, float]]:
    return _github_ownership


def is_github_spof(component_id: str) -> bool:
    return component_id in _github_spof_components


def get_github_employee_context(employee_id: str) -> GitHubEmployeeTelemetry:
    return _github_employee_context.get(employee_id, GitHubEmployeeTelemetry())


def get_github_backup_review_score(employee_id: str) -> float:
    return get_github_employee_context(employee_id).backup_review_score


def get_github_open_prs(employee_id: str) -> int:
    return get_github_employee_context(employee_id).open_prs


def has_doa_ownership() -> bool:
    return _doa_available


def get_component_bus_factor(component_id: str) -> int | None:
    return _component_bus_factor.get(component_id)


def get_all_bus_factors() -> dict[str, int]:
    return dict(_component_bus_factor)


def get_employee_max_doa_pct(employee_id: str) -> float:
    return _employee_max_doa_pct.get(employee_id, 0.0)


def get_doa_decay_evidence() -> list[dict]:
    return list(_doa_decay_evidence)


def get_review_network():
    return _review_network


def get_github_activities() -> list[GitHubPullRequestActivity]:
    return list(_github_activities)


def get_team_risky_changes():
    if _review_network is None:
        return []
    return list(_review_network.risky_changes)


def has_review_network() -> bool:
    return _review_network is not None


def has_notion_sync() -> bool:
    return _notion_synced


def get_notion_component_sources(component_id: str) -> list[str]:
    return list(_notion_component_sources.get(component_id, []))


def get_notion_employee_signals(employee_id: str):
    return _notion_employee_signals.get(employee_id)


def get_notion_expertise_warnings() -> list[dict]:
    return list(_notion_expertise_warnings)


def _github_active_components() -> set[str]:
    return {component_id for component_id, rows in _github_ownership.items() if rows}


def apply_notion_telemetry(
    db: Session,
    tenant_id: uuid.UUID,
    snapshot,
) -> dict[str, object]:
    global _notion_synced, _notion_component_sources, _notion_employee_signals
    global _notion_expertise_warnings

    from app.services.notion_telemetry import persist_notion_snapshots

    persist_notion_snapshots(db, tenant_id, snapshot)
    _notion_component_sources.clear()
    _notion_component_sources.update(snapshot.component_sources)
    _notion_employee_signals.clear()
    _notion_employee_signals.update(snapshot.employee_signals)
    _notion_expertise_warnings.clear()
    _notion_expertise_warnings.extend(snapshot.expertise_sole_owner_warnings)
    _notion_synced = True
    return {
        "docs_indexed": len(snapshot.docs),
        "components_with_docs": len(snapshot.component_sources),
        "employees_tracked": len(snapshot.employee_signals),
    }


def hydrate_notion_telemetry_from_db(db: Session, tenant_id: uuid.UUID) -> bool:
    global _notion_synced, _notion_component_sources, _notion_employee_signals
    global _notion_expertise_warnings

    if _notion_synced:
        return True

    from app.models.operational import NotionDocSnapshot
    from app.services.notion_telemetry import compute_notion_telemetry, utc_dt
    from app.services.notion_types import NotionDocRecord

    rows = (
        db.query(NotionDocSnapshot)
        .filter(NotionDocSnapshot.tenant_id == tenant_id)
        .all()
    )
    if not rows:
        from app.services.integration_config_store import (
            get_integration_last_synced,
            get_notion_config,
        )

        if (
            get_notion_config(db, tenant_id) is not None
            and get_integration_last_synced(db, tenant_id, "notion")
        ):
            _notion_component_sources.clear()
            _notion_employee_signals.clear()
            _notion_expertise_warnings.clear()
            _notion_synced = True
            return True
        return False

    docs = [
        NotionDocRecord(
            page_id=row.page_id,
            title=row.title,
            page_url=row.page_url,
            last_edited_at=utc_dt(row.last_edited_at) or datetime.now(UTC),
            component_id=row.component_id,
            owner_employee_id=row.owner_employee_id,
            page_kind=row.page_kind,
            is_archived=row.is_archived,
            last_verified_at=utc_dt(row.last_verified_at),
            expertise_tags=list(row.expertise_tags or []),
        )
        for row in rows
    ]
    snapshot = compute_notion_telemetry(
        db,
        tenant_id,
        docs,
        components_with_github_activity=_github_active_components(),
    )
    _notion_component_sources.clear()
    _notion_component_sources.update(snapshot.component_sources)
    _notion_employee_signals.clear()
    _notion_employee_signals.update(snapshot.employee_signals)
    _notion_expertise_warnings.clear()
    _notion_expertise_warnings.extend(snapshot.expertise_sole_owner_warnings)
    _notion_synced = True
    return True


def _restore_jira_cache(cache: dict[str, object]) -> bool:
    global _jira_synced, _jira_backlog_by_employee, _jira_employee_signals, _jira_issues_cache

    restored = False

    issues_raw = cache.get("issues")
    if isinstance(issues_raw, list) and issues_raw:
        _jira_issues_cache.clear()
        _jira_issues_cache.extend(
            _jira_issue_from_cache_row(item)
            for item in issues_raw
            if isinstance(item, dict)
        )
        restored = True

    raw_signals = cache.get("employee_signals")
    if isinstance(raw_signals, dict) and raw_signals:
        backlog_raw = cache.get("backlog_by_employee")
        backlog = (
            {str(key): int(value) for key, value in backlog_raw.items()}
            if isinstance(backlog_raw, dict)
            else {}
        )
        signals: dict[str, JiraEmployeeSignals] = {}
        for employee_id, payload in raw_signals.items():
            if not isinstance(payload, dict):
                continue
            signals[str(employee_id)] = JiraEmployeeSignals(
                employee_id=str(payload.get("employee_id", employee_id)),
                open_tasks=int(payload.get("open_tasks", 0)),
                open_p1_p2=int(payload.get("open_p1_p2", 0)),
                jira_backlog_boost=int(payload.get("jira_backlog_boost", 0)),
                epic_owner_count=int(payload.get("epic_owner_count", 0)),
                sprint_points=float(payload.get("sprint_points", 0.0)),
                sample_issue_urls=list(payload.get("sample_issue_urls") or []),
            )

        _jira_backlog_by_employee.clear()
        _jira_backlog_by_employee.update(backlog)
        _jira_employee_signals.clear()
        _jira_employee_signals.update(signals)
        restored = True

    if restored:
        _jira_synced = True
    return restored


def hydrate_jira_telemetry_from_db(db: Session, tenant_id: uuid.UUID) -> bool:
    if _jira_synced:
        return True
    cache = get_telemetry_cache(db, tenant_id, "jira")
    if cache and _restore_jira_cache(cache):
        return True
    return False


def _restore_slack_cache(cache: dict[str, object]) -> bool:
    global _slack_synced, _slack_employee_signals, _slack_escalation_warnings, _slack_threads_cache

    restored = False

    threads_raw = cache.get("threads")
    if isinstance(threads_raw, list) and threads_raw:
        _slack_threads_cache.clear()
        _slack_threads_cache.extend(
            _slack_thread_from_cache_row(item)
            for item in threads_raw
            if isinstance(item, dict)
        )
        restored = True

    raw_signals = cache.get("employee_signals")
    if isinstance(raw_signals, dict) and raw_signals:
        signals: dict[str, SlackEmployeeSignals] = {}
        for employee_id, payload in raw_signals.items():
            if not isinstance(payload, dict):
                continue
            signals[str(employee_id)] = SlackEmployeeSignals(
                employee_id=str(payload.get("employee_id", employee_id)),
                undocumented_solved_incidents=int(
                    payload.get("undocumented_solved_incidents", 0)
                ),
                on_call_incidents_30d=int(
                    payload.get("on_call_incidents_30d", 0)
                ),
                incident_escalation_threads=int(
                    payload.get("incident_escalation_threads", 0)
                ),
                on_call_off_hours_messages=int(
                    payload.get("on_call_off_hours_messages", 0)
                ),
                sole_responder_thread_count=int(
                    payload.get("sole_responder_thread_count", 0)
                ),
            )

        _slack_employee_signals.clear()
        _slack_employee_signals.update(signals)
        restored = True

    warnings_raw = cache.get("escalation_warnings")
    if isinstance(warnings_raw, list):
        _slack_escalation_warnings.clear()
        _slack_escalation_warnings.extend(warnings_raw)
        restored = True

    if restored:
        _slack_synced = True
    return restored


def hydrate_slack_telemetry_from_db(db: Session, tenant_id: uuid.UUID) -> bool:
    if _slack_synced:
        return True
    cache = get_telemetry_cache(db, tenant_id, "slack")
    if cache and _restore_slack_cache(cache):
        return True
    return False


def hydrate_sync_freshness_from_db(db: Session, tenant_id: uuid.UUID) -> None:
    from sqlalchemy import func

    from app.models.operational import DoaFileSnapshot, NotionDocSnapshot

    for source in INTEGRATION_SOURCES:
        last_synced = get_integration_last_synced(db, tenant_id, source)
        if last_synced:
            _sync_timestamps[source] = last_synced

    if not _sync_timestamps.get("notion"):
        notion_ts = (
            db.query(func.max(NotionDocSnapshot.computed_at))
            .filter(NotionDocSnapshot.tenant_id == tenant_id)
            .scalar()
        )
        if notion_ts is not None:
            if notion_ts.tzinfo is None:
                notion_ts = notion_ts.replace(tzinfo=UTC)
            _sync_timestamps["notion"] = notion_ts.isoformat()

    if not _sync_timestamps.get("github"):
        github_ts = (
            db.query(func.max(GitHubOwnershipSnapshot.computed_at))
            .filter(GitHubOwnershipSnapshot.tenant_id == tenant_id)
            .scalar()
        )
        if github_ts is None:
            github_ts = (
                db.query(func.max(DoaFileSnapshot.computed_at))
                .filter(DoaFileSnapshot.tenant_id == tenant_id)
                .scalar()
            )
        if github_ts is not None:
            if github_ts.tzinfo is None:
                github_ts = github_ts.replace(tzinfo=UTC)
            _sync_timestamps["github"] = github_ts.isoformat()


def hydrate_integration_telemetry(db: Session, tenant_id: uuid.UUID) -> None:
    """Reload integration telemetry and sync timestamps after a backend restart."""
    hydrate_sync_freshness_from_db(db, tenant_id)
    hydrate_github_telemetry_from_db(db, tenant_id)
    hydrate_notion_telemetry_from_db(db, tenant_id)
    hydrate_jira_telemetry_from_db(db, tenant_id)
    hydrate_slack_telemetry_from_db(db, tenant_id)


def has_slack_sync() -> bool:
    return _slack_synced


def get_slack_employee_signals(employee_id: str):
    return _slack_employee_signals.get(employee_id)


def get_slack_escalation_warnings() -> list[dict]:
    return list(_slack_escalation_warnings)


def get_cached_slack_threads():
    return list(_slack_threads_cache)


def apply_slack_telemetry(snapshot) -> dict[str, object]:
    global _slack_synced, _slack_employee_signals, _slack_escalation_warnings
    global _slack_threads_cache

    _slack_employee_signals.clear()
    _slack_employee_signals.update(snapshot.employee_signals)
    _slack_escalation_warnings.clear()
    _slack_escalation_warnings.extend(snapshot.escalation_warnings)
    _slack_threads_cache.clear()
    _slack_threads_cache.extend(snapshot.threads)
    _slack_synced = True
    return {
        "threads_indexed": len(snapshot.threads),
        "employees_tracked": len(snapshot.employee_signals),
        "escalation_warnings": len(snapshot.escalation_warnings),
    }


def apply_slack_telemetry_with_cache(
    db: Session,
    tenant_id: uuid.UUID,
    snapshot,
) -> dict[str, object]:
    result = apply_slack_telemetry(snapshot)
    save_telemetry_cache(
        db,
        tenant_id,
        "slack",
        {
            "employee_signals": {
                employee_id: {
                    "employee_id": row.employee_id,
                    "undocumented_solved_incidents": row.undocumented_solved_incidents,
                    "on_call_incidents_30d": row.on_call_incidents_30d,
                    "incident_escalation_threads": row.incident_escalation_threads,
                    "on_call_off_hours_messages": row.on_call_off_hours_messages,
                    "sole_responder_thread_count": row.sole_responder_thread_count,
                }
                for employee_id, row in snapshot.employee_signals.items()
            },
            "escalation_warnings": list(snapshot.escalation_warnings),
            "threads": [
                _slack_thread_to_cache_row(thread) for thread in snapshot.threads
            ],
        },
    )
    return result


def get_telemetry_snapshot() -> dict[str, object]:
    return {
        "jira_synced": _jira_synced,
        "github_synced": _github_synced,
        "notion_synced": _notion_synced,
        "slack_synced": _slack_synced,
        "doa_available": _doa_available,
        "jira_backlog_by_employee": dict(_jira_backlog_by_employee),
        "jira_employee_signals": {
            employee_id: {
                "open_tasks": row.open_tasks,
                "open_p1_p2": row.open_p1_p2,
                "jira_backlog_boost": row.jira_backlog_boost,
                "epic_owner_count": row.epic_owner_count,
            }
            for employee_id, row in _jira_employee_signals.items()
        },
        "github_spof_components": sorted(_github_spof_components),
        "github_ownership": _github_ownership,
        "component_bus_factor": dict(_component_bus_factor),
    }


def reset_telemetry_for_tests() -> None:
    """Clear in-memory telemetry state (tests only)."""
    global _jira_synced, _github_synced, _notion_synced, _slack_synced, _doa_available, _review_network
    global _notion_component_sources, _notion_employee_signals, _notion_expertise_warnings
    global _slack_employee_signals, _slack_escalation_warnings, _slack_threads_cache
    _jira_backlog_by_employee.clear()
    _jira_employee_signals.clear()
    _jira_issues_cache.clear()
    _github_ownership.clear()
    _github_spof_components.clear()
    _github_employee_context.clear()
    _github_open_prs_by_login.clear()
    _github_activities.clear()
    _component_bus_factor.clear()
    _employee_max_doa_pct.clear()
    _doa_decay_evidence.clear()
    _sync_timestamps.clear()
    _review_network = None
    _jira_synced = False
    _github_synced = False
    _notion_synced = False
    _notion_component_sources.clear()
    _notion_employee_signals.clear()
    _notion_expertise_warnings.clear()
    _slack_synced = False
    _slack_employee_signals.clear()
    _slack_escalation_warnings.clear()
    _slack_threads_cache.clear()
    _doa_available = False
