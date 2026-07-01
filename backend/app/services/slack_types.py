"""Shared Slack telemetry types (ERA Step 07)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SlackMessageRecord:
    ts: str
    user_id: str
    text: str
    is_bot: bool = False
    reactions: list[str] = field(default_factory=list)


@dataclass
class SlackThreadRecord:
    channel_id: str
    channel_name: str
    thread_ts: str
    parent_text: str
    messages: list[SlackMessageRecord] = field(default_factory=list)
    component_id: str | None = None
    is_incident_channel: bool = False
    is_on_call_channel: bool = False
    mentioned_user_ids: list[str] = field(default_factory=list)
    resolved_by_employee_id: str | None = None
    resolved_at: datetime | None = None
    thread_url: str = ""


@dataclass
class SlackThreadEvidence:
    thread_url: str
    title: str
    channel_name: str
    kind: str  # undocumented | on_call | escalation | sole_responder


@dataclass
class SlackEmployeeSignals:
    employee_id: str
    undocumented_solved_incidents: int = 0
    on_call_incidents_30d: int = 0
    incident_escalation_threads: int = 0
    on_call_off_hours_messages: int = 0
    sole_responder_thread_count: int = 0
    thread_evidence: list[SlackThreadEvidence] = field(default_factory=list)


@dataclass
class SlackTelemetrySnapshot:
    threads: list[SlackThreadRecord] = field(default_factory=list)
    employee_signals: dict[str, SlackEmployeeSignals] = field(default_factory=dict)
    escalation_warnings: list[dict] = field(default_factory=list)
    sync_warnings: list[str] = field(default_factory=list)
