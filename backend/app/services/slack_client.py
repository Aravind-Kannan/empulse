"""Slack API client and incident thread parsing (ERA Step 07)."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from app.schemas.integrations import SlackConfigRequest
from app.services.slack_types import SlackMessageRecord, SlackThreadRecord

logger = logging.getLogger(__name__)

RESOLUTION_PATTERNS = ("resolved", "fixed", "root cause", "mitigated")
INCIDENT_KEYWORDS = ("#incident", "sev1", "sev2", "sev3", "outage", "incident")
MENTION_RE = re.compile(r"<@([A-Z0-9]+)>")
OFF_HOURS_START = 22
OFF_HOURS_END = 7
LOOKBACK_DAYS = 90
ON_CALL_WINDOW_HOURS = 4
MIN_THREAD_MESSAGES = 3
MIN_THREAD_USERS = 2
ESCALATION_THREAD_THRESHOLD = 8
ESCALATION_CONCENTRATION_PCT = 70.0


def parse_csv_ids(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def resolve_channel_sets(config: SlackConfigRequest) -> tuple[set[str], set[str], set[str]]:
    configured = set(parse_csv_ids(config.channel_ids))
    incident = set(parse_csv_ids(config.incident_channel_ids)) or configured
    on_call = set(parse_csv_ids(config.on_call_channel_ids)) or configured
    return configured, incident, on_call


def slack_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token.strip()}"}


def build_thread_url(workspace_url: str, channel_id: str, thread_ts: str) -> str:
    host = urlparse(workspace_url.strip()).netloc or "slack.com"
    ts_compact = thread_ts.replace(".", "")
    return f"https://{host}/archives/{channel_id}/p{ts_compact}?thread_ts={thread_ts}"


def thread_title(parent_text: str, *, max_len: int = 80) -> str:
    cleaned = " ".join(parent_text.split())
    if len(cleaned) <= max_len:
        return cleaned or "Incident thread"
    return f"{cleaned[: max_len - 1]}…"


def _parse_ts(ts: str) -> datetime:
    return datetime.fromtimestamp(float(ts), tz=UTC)


def _message_is_bot(message: dict[str, Any]) -> bool:
    if message.get("bot_id") or message.get("subtype") == "bot_message":
        return True
    return bool(message.get("is_bot"))


def _extract_mentions(text: str) -> list[str]:
    return MENTION_RE.findall(text or "")


def _contains_incident_signal(text: str, *, is_incident_channel: bool) -> bool:
    if is_incident_channel:
        return True
    lowered = (text or "").lower()
    return any(keyword in lowered for keyword in INCIDENT_KEYWORDS)


def _is_resolution_message(message: SlackMessageRecord) -> bool:
    lowered = message.text.lower()
    if any(pattern in lowered for pattern in RESOLUTION_PATTERNS):
        return True
    return "white_check_mark" in message.reactions or "heavy_check_mark" in message.reactions


def _human_messages(messages: list[SlackMessageRecord]) -> list[SlackMessageRecord]:
    return [message for message in messages if not message.is_bot]


def is_resolved_incident_thread(
    thread: SlackThreadRecord,
    *,
    is_incident_channel: bool,
) -> str | None:
    human = _human_messages(thread.messages)
    if len(human) < MIN_THREAD_MESSAGES:
        return None
    unique_users = {message.user_id for message in human}
    if len(unique_users) < MIN_THREAD_USERS:
        return None

    parent_text = thread.parent_text or (human[0].text if human else "")
    if not _contains_incident_signal(parent_text, is_incident_channel=is_incident_channel):
        combined = " ".join(message.text for message in human[:3])
        if not _contains_incident_signal(combined, is_incident_channel=is_incident_channel):
            return None

    for message in reversed(human):
        if _is_resolution_message(message):
            return message.user_id
    return None


def _message_from_dict(raw: dict[str, Any]) -> SlackMessageRecord:
    reactions: list[str] = []
    for item in raw.get("reactions") or []:
        if isinstance(item, str):
            reactions.append(item)
        elif isinstance(item, dict) and item.get("name"):
            reactions.append(str(item["name"]))
    return SlackMessageRecord(
        ts=str(raw.get("ts", "")),
        user_id=str(raw.get("user") or raw.get("user_id") or ""),
        text=str(raw.get("text") or ""),
        is_bot=_message_is_bot(raw),
        reactions=reactions,
    )


def _thread_from_fixture(
    channel: dict[str, Any],
    thread: dict[str, Any],
    *,
    workspace_url: str,
    is_incident_channel: bool,
    is_on_call_channel: bool,
) -> SlackThreadRecord:
    messages = [_message_from_dict(row) for row in thread.get("messages") or []]
    mentions = list(thread.get("mentions") or [])
    if not mentions:
        for message in messages:
            mentions.extend(_extract_mentions(message.text))
    channel_id = str(channel["id"])
    thread_ts = str(thread["thread_ts"])
    record = SlackThreadRecord(
        channel_id=channel_id,
        channel_name=str(channel.get("name") or channel_id),
        thread_ts=thread_ts,
        parent_text=str(thread.get("parent_text") or ""),
        messages=messages,
        component_id=channel.get("component_id"),
        is_incident_channel=is_incident_channel,
        is_on_call_channel=is_on_call_channel,
        mentioned_user_ids=sorted(set(mentions)),
        thread_url=build_thread_url(workspace_url, channel_id, thread_ts),
    )
    resolver_slack_id = is_resolved_incident_thread(
        record,
        is_incident_channel=is_incident_channel,
    )
    if resolver_slack_id:
        last_human = next(
            (message for message in reversed(_human_messages(messages)) if message.user_id),
            None,
        )
        record.resolved_at = (
            _parse_ts(last_human.ts) if last_human and last_human.ts else None
        )
    return record


def load_fixture_channel_history() -> tuple[str, list[SlackThreadRecord], dict[str, str]]:
    fixture_path = (
        Path(__file__).resolve().parent.parent.parent
        / "tests"
        / "fixtures"
        / "slack_channel_history.json"
    )
    payload = json.loads(fixture_path.read_text())
    workspace_url = str(payload.get("workspace_url") or "https://example.slack.com")
    users = {
        str(user_id): str((profile or {}).get("email", "")).lower()
        for user_id, profile in (payload.get("users") or {}).items()
    }
    threads: list[SlackThreadRecord] = []
    for channel in payload.get("channels") or []:
        is_incident = bool(channel.get("is_incident"))
        is_on_call = bool(channel.get("is_on_call"))
        for thread in channel.get("threads") or []:
            threads.append(
                _thread_from_fixture(
                    channel,
                    thread,
                    workspace_url=workspace_url,
                    is_incident_channel=is_incident,
                    is_on_call_channel=is_on_call,
                )
            )
    return workspace_url, threads, users


def _fetch_conversation_history(
    token: str,
    channel_id: str,
    *,
    oldest: float | None = None,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"channel": channel_id, "limit": 200}
        if oldest is not None:
            params["oldest"] = str(oldest)
        if cursor:
            params["cursor"] = cursor
        response = requests.get(
            "https://slack.com/api/conversations.history",
            headers=slack_headers(token),
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise ValueError(
                f"Slack conversations.history failed for {channel_id}: "
                f"{payload.get('error', 'unknown_error')}"
            )
        messages.extend(payload.get("messages") or [])
        cursor = (payload.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
    return messages


def _fetch_thread_replies(
    token: str,
    channel_id: str,
    thread_ts: str,
) -> list[dict[str, Any]]:
    response = requests.get(
        "https://slack.com/api/conversations.replies",
        headers=slack_headers(token),
        params={"channel": channel_id, "ts": thread_ts, "limit": 200},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise ValueError(
            f"Slack conversations.replies failed for {channel_id}/{thread_ts}: "
            f"{payload.get('error', 'unknown_error')}"
        )
    return payload.get("messages") or []


def _infer_component_id(
    channel_name: str,
    component_names: dict[str, str],
) -> str | None:
    lowered = channel_name.lower()
    for component_id, name in component_names.items():
        slug = name.lower().replace(" ", "-")
        if slug in lowered or name.lower() in lowered:
            return component_id
    return None


def fetch_slack_incident_threads(
    config: SlackConfigRequest,
    *,
    component_names: dict[str, str] | None = None,
    use_fixture: bool = False,
    now: datetime | None = None,
) -> tuple[list[SlackThreadRecord], dict[str, str], list[str]]:
    """
    Return (threads, slack_user_id_to_email, warnings).
    """
    component_names = component_names or {}
    if use_fixture or not config.bot_token.strip():
        workspace_url, threads, users = load_fixture_channel_history()
        if not config.workspace_url.strip():
            config = config.model_copy(update={"workspace_url": workspace_url})
        return threads, users, []

    now = now or datetime.now(UTC)
    oldest = now.timestamp() - (LOOKBACK_DAYS * 86400)
    _, incident_channels, on_call_channels = resolve_channel_sets(config)
    target_channels = incident_channels | on_call_channels
    if not target_channels:
        return [], {}, ["No Slack channels configured for incident or on-call sync."]

    warnings: list[str] = []
    threads: list[SlackThreadRecord] = []
    user_emails: dict[str, str] = {}

    for channel_id in sorted(target_channels):
        try:
            history = _fetch_conversation_history(
                config.bot_token,
                channel_id,
                oldest=oldest,
            )
        except ValueError as exc:
            warnings.append(str(exc))
            continue

        parent_messages = [
            message
            for message in history
            if message.get("thread_ts") in (None, message.get("ts"))
            and not _message_is_bot(message)
        ]
        for parent in parent_messages:
            thread_ts = str(parent.get("ts", ""))
            if not thread_ts:
                continue
            try:
                replies = _fetch_thread_replies(config.bot_token, channel_id, thread_ts)
            except ValueError as exc:
                warnings.append(str(exc))
                replies = [parent]

            messages = [_message_from_dict(row) for row in replies]
            mentions: list[str] = []
            for message in messages:
                mentions.extend(_extract_mentions(message.text))
                if message.user_id and message.user_id not in user_emails:
                    user_emails[message.user_id] = ""

            channel_name = channel_id
            record = SlackThreadRecord(
                channel_id=channel_id,
                channel_name=channel_name,
                thread_ts=thread_ts,
                parent_text=str(parent.get("text") or ""),
                messages=messages,
                component_id=_infer_component_id(channel_name, component_names),
                is_incident_channel=channel_id in incident_channels,
                is_on_call_channel=channel_id in on_call_channels,
                mentioned_user_ids=sorted(set(mentions)),
                thread_url=build_thread_url(config.workspace_url, channel_id, thread_ts),
            )
            resolver = is_resolved_incident_thread(
                record,
                is_incident_channel=record.is_incident_channel,
            )
            if resolver:
                last_human = next(
                    (
                        message
                        for message in reversed(_human_messages(messages))
                        if message.user_id
                    ),
                    None,
                )
                record.resolved_at = (
                    _parse_ts(last_human.ts) if last_human and last_human.ts else None
                )
            threads.append(record)

    return threads, user_emails, warnings


def is_after_hours(ts: datetime) -> bool:
    hour = ts.astimezone(UTC).hour
    return hour >= OFF_HOURS_START or hour < OFF_HOURS_END


def count_on_call_incident(
    thread: SlackThreadRecord,
    employee_slack_id: str,
) -> bool:
    if not thread.is_on_call_channel:
        return False
    employee_messages = [
        message
        for message in _human_messages(thread.messages)
        if message.user_id == employee_slack_id
    ]
    if len(employee_messages) < 2:
        return False
    timestamps = sorted(_parse_ts(message.ts) for message in employee_messages if message.ts)
    if len(timestamps) < 2:
        return False
    window = ON_CALL_WINDOW_HOURS * 3600
    return (timestamps[-1] - timestamps[0]).total_seconds() <= window
