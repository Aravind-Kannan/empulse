"""Slack → canonical ontology normalizers."""

from __future__ import annotations

from app.ontology.canonical import (
    CanonicalComponentRef,
    CanonicalDiscussion,
    CanonicalPersonRef,
)
from app.ontology.jira_keys import extract_jira_issue_keys
from app.services.slack_client import thread_title
from app.services.slack_types import SlackThreadRecord


def normalize_slack_thread(
    thread: SlackThreadRecord,
    *,
    components_by_id: dict,
    employee_names: dict[str, str] | None = None,
) -> CanonicalDiscussion | None:
    human_messages = [
        message
        for message in thread.messages
        if not message.is_bot and message.text.strip()
    ]
    if not human_messages:
        return None

    component_ref = None
    if thread.component_id and thread.component_id in components_by_id:
        comp = components_by_id[thread.component_id]
        component_ref = CanonicalComponentRef(
            component_id=thread.component_id,
            name=getattr(comp, "name", ""),
        )

    resolver = None
    if thread.resolved_by_employee_id:
        resolver = CanonicalPersonRef(
            employee_id=thread.resolved_by_employee_id,
            provider="slack",
            provider_user_id=thread.resolved_by_employee_id,
            display_name=(employee_names or {}).get(thread.resolved_by_employee_id, ""),
        )

    title = thread_title(thread.parent_text)
    return CanonicalDiscussion(
        source="slack",
        thread_id=f"{thread.channel_id}:{thread.thread_ts}",
        channel_name=thread.channel_name,
        title=title,
        thread_url=thread.thread_url,
        resolver=resolver,
        component=component_ref,
        referenced_work_item_ids=extract_jira_issue_keys(title, thread.parent_text),
    )
