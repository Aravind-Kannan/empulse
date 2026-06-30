"""In-memory telemetry derived from integration syncs, feeding ERA/KRA engines."""

from __future__ import annotations

import uuid

from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.operational import Assignment
from app.services.integration_feeds import MOCK_GITHUB_ACTIVITY, MOCK_JIRA_ISSUES

_jira_backlog_by_employee: dict[str, int] = {}
_github_ownership: dict[str, dict[str, float]] = {}
_github_spof_components: set[str] = set()
_jira_synced = False
_github_synced = False

HIGH_PRIORITIES = {"High", "Critical"}


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


def apply_jira_telemetry(db: Session, tenant_id: uuid.UUID) -> dict[str, int]:
    """Map unassigned high-priority Jira bugs to each component's main engineer."""
    global _jira_synced

    backlog: dict[str, int] = defaultdict(int)

    for issue in MOCK_JIRA_ISSUES:
        if issue.get("assignee_employee_id"):
            continue
        if issue["priority"] not in HIGH_PRIORITIES:
            continue
        if issue["issue_type"] != "Bug":
            continue

        main_engineer = _main_engineer_for_component(db, issue["component_id"], tenant_id)
        if main_engineer:
            backlog[main_engineer] += 1

    _jira_backlog_by_employee.clear()
    _jira_backlog_by_employee.update(backlog)
    _jira_synced = True
    return dict(backlog)


def apply_github_telemetry(_db: Session, _tenant_id: uuid.UUID) -> dict[str, dict[str, float]]:
    """
    Derive 6-month directory ownership splits from GitHub activity.
    Components with a single contributor are flagged as SPOF.
    """
    global _github_synced

    loc_by_component: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for activity in MOCK_GITHUB_ACTIVITY:
        author_id = activity["author_employee_id"]
        for file_change in activity["files"]:
            component_id = file_change["component_id"]
            loc = file_change["loc_added"] + file_change["loc_removed"]
            loc_by_component[component_id][author_id] += loc

    ownership: dict[str, dict[str, float]] = {}
    spof_components: set[str] = set()

    for component_id, contributors in loc_by_component.items():
        total_loc = sum(contributors.values()) or 1
        ownership[component_id] = {
            employee_id: round((loc / total_loc) * 100, 1)
            for employee_id, loc in contributors.items()
        }
        if len(contributors) <= 1:
            spof_components.add(component_id)

    _github_ownership.clear()
    _github_ownership.update(ownership)
    _github_spof_components.clear()
    _github_spof_components.update(spof_components)
    _github_synced = True
    return ownership


def get_jira_backlog_boost(employee_id: str) -> int:
    return _jira_backlog_by_employee.get(employee_id, 0)


def has_jira_sync() -> bool:
    return _jira_synced


def has_github_sync() -> bool:
    return _github_synced


def get_github_ownership() -> dict[str, dict[str, float]]:
    return _github_ownership


def is_github_spof(component_id: str) -> bool:
    return component_id in _github_spof_components


def get_telemetry_snapshot() -> dict[str, object]:
    return {
        "jira_synced": _jira_synced,
        "github_synced": _github_synced,
        "jira_backlog_by_employee": dict(_jira_backlog_by_employee),
        "github_spof_components": sorted(_github_spof_components),
        "github_ownership": _github_ownership,
    }
