"""Derive ERA codebase contribution from Cognee graph topology and multi-hop telemetry."""

from __future__ import annotations

from app.models.operational import Assignment, Component
from app.services.integration_feeds import MOCK_GITHUB_ACTIVITY, MOCK_JIRA_ISSUES
from app.services.integration_telemetry import get_github_ownership, get_jira_backlog_boost


def _github_commit_hops_for_components(component_ids: set[str]) -> int:
    count = 0
    for activity in MOCK_GITHUB_ACTIVITY:
        for file_change in activity["files"]:
            if file_change["component_id"] in component_ids:
                count += 1
    return count


def _unresolved_jira_hops_for_components(component_ids: set[str]) -> int:
    count = 0
    for issue in MOCK_JIRA_ISSUES:
        if issue["component_id"] not in component_ids:
            continue
        if issue.get("status") in ("Open", "In Progress", "Blocked"):
            count += 1
    return count


def calculate_graph_contribution_share(
    *,
    employee_id: str,
    assignments: list[Assignment],
    total_components: int,
    jira_backlog_boost: int | None = None,
) -> float:
    """
    Compute Codebase Contribution Share % from graph-linked component nodes
    and multi-hop integration density (GitHub commits, Jira tickets).
    """
    if total_components <= 0 or not assignments:
        return 0.0

    owned_ids = {assignment.component_id for assignment in assignments}
    owned_count = len(owned_ids)

    # Portfolio breadth: employee ownsComponent edges vs global component nodes
    breadth_pct = (owned_count / total_components) * 100

    # GitHub multi-hop density from contributedTo / modifies graph telemetry
    github_ownership = get_github_ownership()
    github_scores = [
        github_ownership.get(component_id, {}).get(employee_id, 0.0)
        for component_id in owned_ids
    ]
    github_density = sum(github_scores) / max(1, len(github_scores))

    # Operational node density (open tasks + incidents on linked components)
    open_tasks = sum(a.component.open_tasks_count for a in assignments)
    unresolved = sum(a.component.unresolved_incidents for a in assignments)
    ops_density = min(40.0, open_tasks * 1.5 + unresolved * 3.0)

    # Multi-hop link counts from integration graph feeds
    commit_hops = _github_commit_hops_for_components(owned_ids)
    jira_hops = _unresolved_jira_hops_for_components(owned_ids)
    hop_density = min(25.0, commit_hops * 2.0 + jira_hops * 2.5)

    jira_boost = jira_backlog_boost if jira_backlog_boost is not None else get_jira_backlog_boost(employee_id)
    jira_factor = min(15.0, jira_boost * 2.5)

    raw = (
        breadth_pct * 0.40
        + github_density * 0.30
        + ops_density * 0.12
        + hop_density * 0.10
        + jira_factor * 0.08
    )
    return min(100.0, round(raw, 1))


def calculate_contribution_for_employee(
    employee_id: str,
    assignments: list[Assignment],
    total_components: int,
) -> float:
    return calculate_graph_contribution_share(
        employee_id=employee_id,
        assignments=assignments,
        total_components=total_components,
    )


def total_component_count(components: list[Component]) -> int:
    return max(len(components), 1)
