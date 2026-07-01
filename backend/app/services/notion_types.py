"""Shared Notion telemetry types (ERA Step 06)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NotionDocRecord:
    page_id: str
    title: str
    page_url: str
    last_edited_at: datetime
    component_id: str | None = None
    owner_employee_id: str | None = None
    owner_email: str | None = None
    page_kind: str = "runbook"
    is_archived: bool = False
    is_inaccessible: bool = False
    is_ownership_template: bool = False
    last_verified_at: datetime | None = None
    expertise_tags: list[str] = field(default_factory=list)


@dataclass
class NotionEmployeeDocSignals:
    employee_id: str
    pages_owned: int = 0
    components_without_docs: int = 0
    stale_runbook_count: int = 0
    undocumented_solved_incidents: int = 0
    sole_critical_runbook_count: int = 0
    expertise_tags: list[str] = field(default_factory=list)


@dataclass
class NotionTelemetrySnapshot:
    docs: list[NotionDocRecord] = field(default_factory=list)
    component_sources: dict[str, list[str]] = field(default_factory=dict)
    employee_signals: dict[str, NotionEmployeeDocSignals] = field(default_factory=dict)
    expertise_sole_owner_warnings: list[dict] = field(default_factory=list)
