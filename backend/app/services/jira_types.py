"""Shared Jira telemetry types (ERA Step 05)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JiraIssueActivity:
    issue_key: str
    issue_type: str
    priority: str
    status: str
    status_category: str
    project_key: str
    assignee_provider_user_id: str | None = None
    assignee_email: str | None = None
    component_id: str | None = None
    jira_component_names: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    story_points: float = 0.0
    is_subtask: bool = False
    issue_url: str | None = None

    @property
    def is_done(self) -> bool:
        return self.status_category.lower() == "done"

    @property
    def is_high_priority(self) -> bool:
        return self.priority in {"Highest", "High", "Critical"}

    @property
    def is_bug_or_incident(self) -> bool:
        normalized = self.issue_type.lower()
        return normalized in {"bug", "incident"}


@dataclass
class JiraEmployeeSignals:
    employee_id: str
    open_tasks: int = 0
    open_p1_p2: int = 0
    jira_backlog_boost: int = 0
    epic_owner_count: int = 0
    sprint_points: float = 0.0
    sample_issue_urls: list[str] = field(default_factory=list)
