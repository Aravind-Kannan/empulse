"""Slack telemetry aggregation for ERA O/D/S/B dimensions (Step 07)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.operational import Employee
from app.services.slack_client import (
    ESCALATION_CONCENTRATION_PCT,
    ESCALATION_THREAD_THRESHOLD,
    count_on_call_incident,
    is_after_hours,
    is_resolved_incident_thread,
    thread_title,
)
from app.services.slack_types import (
    SlackEmployeeSignals,
    SlackTelemetrySnapshot,
    SlackThreadEvidence,
    SlackThreadRecord,
)

NOTION_DOC_WINDOW_DAYS = 7
ON_CALL_LOOKBACK_DAYS = 30


def _notion_edit_times_by_component(
    notion_docs,
) -> dict[str, datetime]:
    by_component: dict[str, datetime] = {}
    for doc in notion_docs or []:
        if not doc.component_id or doc.is_archived:
            continue
        current = by_component.get(doc.component_id)
        edited = doc.last_edited_at
        if current is None or edited > current:
            by_component[doc.component_id] = edited
    return by_component


def _is_undocumented_resolution(
    thread: SlackThreadRecord,
    *,
    resolver_employee_id: str,
    notion_edits: dict[str, datetime],
) -> bool:
    if not thread.resolved_at:
        return False
    if not thread.component_id:
        return True
    last_edit = notion_edits.get(thread.component_id)
    if last_edit is None:
        return True
    window_start = thread.resolved_at
    window_end = thread.resolved_at + timedelta(days=NOTION_DOC_WINDOW_DAYS)
    return not (window_start <= last_edit <= window_end)


def compute_slack_telemetry(
    db: Session,
    tenant_id: uuid.UUID,
    threads: list[SlackThreadRecord],
    *,
    slack_id_to_employee: dict[str, str],
    notion_docs=None,
    now: datetime | None = None,
) -> SlackTelemetrySnapshot:
    now = now or datetime.now(UTC)
    on_call_cutoff = now - timedelta(days=ON_CALL_LOOKBACK_DAYS)
    notion_edits = _notion_edit_times_by_component(notion_docs)

    employees = (
        db.query(Employee).filter(Employee.tenant_id == tenant_id).all()
    )
    employee_ids = {employee.id for employee in employees}
    employee_signals: dict[str, SlackEmployeeSignals] = {
        employee.id: SlackEmployeeSignals(employee_id=employee.id)
        for employee in employees
    }

    component_incident_threads: dict[str, list[SlackThreadRecord]] = defaultdict(list)
    mention_counts_by_component: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    escalation_warnings: list[dict] = []

    for thread in threads:
        if thread.is_incident_channel and thread.component_id:
            component_incident_threads[thread.component_id].append(thread)
            for slack_id in thread.mentioned_user_ids:
                employee_id = slack_id_to_employee.get(slack_id)
                if employee_id:
                    mention_counts_by_component[thread.component_id][employee_id] += 1

        resolver_slack_id = is_resolved_incident_thread(
            thread,
            is_incident_channel=thread.is_incident_channel,
        )
        if resolver_slack_id:
            resolver_employee_id = slack_id_to_employee.get(resolver_slack_id)
            if resolver_employee_id and resolver_employee_id in employee_ids:
                thread.resolved_by_employee_id = resolver_employee_id
                signal = employee_signals[resolver_employee_id]
                if _is_undocumented_resolution(
                    thread,
                    resolver_employee_id=resolver_employee_id,
                    notion_edits=notion_edits,
                ):
                    signal.undocumented_solved_incidents += 1
                    signal.thread_evidence.append(
                        SlackThreadEvidence(
                            thread_url=thread.thread_url,
                            title=thread_title(thread.parent_text),
                            channel_name=thread.channel_name,
                            kind="undocumented",
                        )
                    )

                human_users = {
                    message.user_id
                    for message in thread.messages
                    if not message.is_bot and message.user_id
                }
                if len(human_users) == 1 and resolver_slack_id in human_users:
                    signal.sole_responder_thread_count += 1
                    signal.thread_evidence.append(
                        SlackThreadEvidence(
                            thread_url=thread.thread_url,
                            title=thread_title(thread.parent_text),
                            channel_name=thread.channel_name,
                            kind="sole_responder",
                        )
                    )

        for slack_id, employee_id in slack_id_to_employee.items():
            if employee_id not in employee_ids:
                continue
            if count_on_call_incident(thread, slack_id):
                anchor = thread.resolved_at
                if anchor is None and thread.messages:
                    anchor = datetime.fromtimestamp(float(thread.messages[0].ts), tz=UTC)
                if anchor and anchor >= on_call_cutoff:
                    signal = employee_signals[employee_id]
                    signal.on_call_incidents_30d += 1
                    signal.thread_evidence.append(
                        SlackThreadEvidence(
                            thread_url=thread.thread_url,
                            title=thread_title(thread.parent_text),
                            channel_name=thread.channel_name,
                            kind="on_call",
                        )
                    )

            off_hours = 0
            for message in thread.messages:
                if message.is_bot or message.user_id != slack_id or not message.ts:
                    continue
                ts = datetime.fromtimestamp(float(message.ts), tz=UTC)
                if thread.is_on_call_channel and is_after_hours(ts):
                    off_hours += 1
            if off_hours:
                employee_signals[employee_id].on_call_off_hours_messages += off_hours

    for component_id, threads_for_component in component_incident_threads.items():
        if not threads_for_component:
            continue
        total = len(threads_for_component)
        for employee_id, mention_count in mention_counts_by_component[component_id].items():
            concentration = (mention_count / total) * 100 if total else 0.0
            if (
                mention_count >= ESCALATION_THREAD_THRESHOLD
                and concentration >= ESCALATION_CONCENTRATION_PCT
            ):
                signal = employee_signals.setdefault(
                    employee_id,
                    SlackEmployeeSignals(employee_id=employee_id),
                )
                signal.incident_escalation_threads = max(
                    signal.incident_escalation_threads,
                    mention_count,
                )
                escalation_warnings.append(
                    {
                        "employee_id": employee_id,
                        "component_id": component_id,
                        "mention_count": mention_count,
                        "concentration_pct": round(concentration, 1),
                        "thread_total": total,
                    }
                )
                signal.thread_evidence.append(
                    SlackThreadEvidence(
                        thread_url=threads_for_component[-1].thread_url,
                        title=(
                            f"Escalation shadow on {total} incident threads "
                            f"({round(concentration, 0):.0f}% mentions)"
                        ),
                        channel_name=threads_for_component[-1].channel_name,
                        kind="escalation",
                    )
                )

    return SlackTelemetrySnapshot(
        threads=threads,
        employee_signals=employee_signals,
        escalation_warnings=escalation_warnings,
    )
