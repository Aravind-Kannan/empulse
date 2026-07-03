"""Slack API client and incident thread parsing (ERA Step 07)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import requests

from app.schemas.integrations import SlackConfigRequest
from app.services.slack_types import SlackMessageRecord, SlackThreadRecord

logger = logging.getLogger(__name__)

RESOLUTION_PATTERNS = ("resolved", "fixed", "root cause", "mitigated")
INCIDENT_KEYWORDS = ("#incident", "sev1", "sev2", "sev3", "outage", "incident")
_JIRA_KEY_RE = re.compile(r"[A-Z][A-Z0-9]+-\d+")
_INCIDENT_SIGNAL_RE = re.compile(
    r"(#incident\b|\bsev[123]\b|\boutage\b|\bincident\b)",
    re.IGNORECASE,
)
MENTION_RE = re.compile(r"<@([A-Z0-9]+)>")
OFF_HOURS_START = 22
OFF_HOURS_END = 7
LOOKBACK_DAYS = 90
FEED_LOOKBACK_DAYS = 14
FEED_HISTORY_LIMIT = 200
SYNC_HISTORY_LIMIT = 10_000
MAX_THREAD_REPLY_FETCHES_PER_CHANNEL = 35
ON_CALL_WINDOW_HOURS = 4
MIN_THREAD_MESSAGES = 3
MIN_THREAD_USERS = 2
ESCALATION_THREAD_THRESHOLD = 8
ESCALATION_CONCENTRATION_PCT = 70.0
SLACK_API_MIN_INTERVAL_SEC = 1.3
SLACK_MAX_RETRIES = 8
_last_slack_request_at = 0.0

SlackFetchPurpose = Literal["sync", "feed"]
_SLACK_FETCH_CACHE_TTL_SECONDS = {"sync": 900.0, "feed": 300.0}
_slack_fetch_cache: dict[str, tuple[float, tuple[Any, ...]]] = {}
_slack_fetch_locks: dict[str, threading.Lock] = {}
_slack_fetch_lock_guard = threading.Lock()


def _pace_slack_request() -> None:
    """Stay under Tier-2 conversations.* limits (~50 req/min)."""
    global _last_slack_request_at
    now = time.monotonic()
    elapsed = now - _last_slack_request_at
    if elapsed < SLACK_API_MIN_INTERVAL_SEC:
        time.sleep(SLACK_API_MIN_INTERVAL_SEC - elapsed)
    _last_slack_request_at = time.monotonic()


def _slack_fetch_cache_key(config: SlackConfigRequest, purpose: SlackFetchPurpose) -> str:
    fingerprint = "|".join(
        [
            purpose,
            config.bot_token.strip(),
            config.channel_ids.strip(),
            config.incident_channel_ids.strip(),
            config.on_call_channel_ids.strip(),
        ]
    )
    return hashlib.sha256(fingerprint.encode()).hexdigest()


def _get_slack_fetch_lock(cache_key: str) -> threading.Lock:
    with _slack_fetch_lock_guard:
        lock = _slack_fetch_locks.get(cache_key)
        if lock is None:
            lock = threading.Lock()
            _slack_fetch_locks[cache_key] = lock
        return lock


def invalidate_slack_threads_cache(cache_key: str | None = None) -> None:
    """Drop in-process Slack thread fetch cache (e.g. after integration sync)."""
    if cache_key is None:
        _slack_fetch_cache.clear()
        return
    _slack_fetch_cache.pop(cache_key, None)


def _incident_feed_channel_ids(
    target_channels: set[str],
    id_to_name: dict[str, str],
) -> set[str]:
    return {
        channel_id
        for channel_id in target_channels
        if is_incident_feed_channel(id_to_name.get(channel_id, channel_id))
    }


def _retry_after_seconds(response: requests.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(float(retry_after), 1.0)
        except ValueError:
            pass
    return min(60.0, 2.0 ** attempt)


def _format_slack_api_error(error: str, *, method: str) -> str:
    if error in ("missing_scope", "invalid_auth", "token_revoked"):
        return _format_slack_conversations_error(error)
    if error == "rate_limited":
        return (
            f"Slack {method} rate limited. Retry the sync in a minute or narrow "
            "channel_ids to fewer incident channels."
        )
    return f"Slack {method} failed: {error}"


def _slack_api_get(
    url: str,
    *,
    token: str,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
    context: str = "Slack API",
) -> dict[str, Any]:
    """GET Slack Web API with pacing and 429/rate_limited retries."""
    for attempt in range(SLACK_MAX_RETRIES):
        _pace_slack_request()
        try:
            response = requests.get(
                url,
                headers=slack_headers(token),
                params=params,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise ValueError(f"Could not reach {context}: {exc}") from exc

        if response.status_code == 429:
            wait = _retry_after_seconds(response, attempt)
            logger.warning(
                "%s HTTP 429; backing off %.1fs (attempt %s/%s)",
                context,
                wait,
                attempt + 1,
                SLACK_MAX_RETRIES,
            )
            time.sleep(wait)
            continue

        response.raise_for_status()
        payload = response.json()
        if payload.get("ok"):
            return payload

        error = str(payload.get("error", "unknown_error"))
        if error == "rate_limited" and attempt + 1 < SLACK_MAX_RETRIES:
            wait = _retry_after_seconds(response, attempt)
            logger.warning(
                "%s rate_limited; backing off %.1fs (attempt %s/%s)",
                context,
                wait,
                attempt + 1,
                SLACK_MAX_RETRIES,
            )
            time.sleep(wait)
            continue

        raise ValueError(_format_slack_api_error(error, method=context))

    raise ValueError(
        f"{context} rate limited after {SLACK_MAX_RETRIES} retries. "
        "Wait a minute and retry, or restrict Slack channel_ids."
    )


def parse_csv_ids(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def resolve_channel_sets(config: SlackConfigRequest) -> tuple[set[str], set[str], set[str]]:
    configured = set(parse_csv_ids(config.channel_ids))
    incident = set(parse_csv_ids(config.incident_channel_ids)) or configured
    on_call = set(parse_csv_ids(config.on_call_channel_ids)) or configured
    return configured, incident, on_call


def slack_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token.strip()}"}


CHANNEL_READ_SCOPES = (
    "channels:read",
    "groups:read",
    "channels:history",
    "groups:history",
)


def _format_slack_conversations_error(error: str) -> str:
    if error == "missing_scope":
        scopes = ", ".join(CHANNEL_READ_SCOPES)
        return (
            f"Slack bot token is missing required channel scopes. Add {scopes} "
            "under OAuth & Permissions, reinstall the app to your workspace, and "
            "copy a fresh xoxb- token."
        )
    if error == "invalid_auth":
        return (
            "Slack rejected this token (invalid_auth). Reinstall the app to your "
            "workspace and copy a fresh Bot User OAuth Token (xoxb-…)."
        )
    if error == "token_revoked":
        return (
            "Slack token was revoked. Reinstall the app and copy a fresh xoxb- token."
        )
    return f"Slack conversations.list failed: {error}"


def _normalize_channel(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(raw.get("id", "")),
        "name": str(raw.get("name") or raw.get("id") or ""),
        "is_private": bool(raw.get("is_private")),
        "is_member": bool(raw.get("is_member")),
        "num_members": raw.get("num_members"),
    }


def list_accessible_channels(token: str) -> list[dict[str, Any]]:
    """Paginate conversations.list and return normalized channel objects."""
    cleaned = token.strip()
    if not cleaned:
        raise ValueError("Slack bot token is required.")

    channels: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        params: dict[str, str] = {
            "types": "public_channel,private_channel",
            "exclude_archived": "true",
            "limit": "200",
        }
        if cursor:
            params["cursor"] = cursor
        payload = _slack_api_get(
            "https://slack.com/api/conversations.list",
            token=cleaned,
            params=params,
            context="conversations.list",
        )

        for raw in payload.get("channels") or []:
            if isinstance(raw, dict) and raw.get("id"):
                channels.append(_normalize_channel(raw))

        cursor = (payload.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
    return channels


def discover_channel_ids(token: str) -> list[str]:
    """Return channel IDs the bot has joined and can read."""
    return [
        channel["id"]
        for channel in list_accessible_channels(token)
        if channel.get("is_member") and channel.get("id")
    ]


def fetch_channel_history(
    token: str,
    channel_id: str,
    *,
    limit: int = 200,
    oldest: float | None = None,
) -> list[dict[str, Any]]:
    """Fetch up to `limit` messages from conversations.history."""
    if limit <= 0:
        return []

    messages: list[dict[str, Any]] = []
    cursor: str | None = None
    remaining = limit
    while remaining > 0:
        page_limit = min(remaining, 200)
        params: dict[str, Any] = {
            "channel": channel_id,
            "limit": page_limit,
        }
        if oldest is not None:
            params["oldest"] = str(oldest)
        if cursor:
            params["cursor"] = cursor
        payload = _slack_api_get(
            "https://slack.com/api/conversations.history",
            token=token,
            params=params,
            context=f"conversations.history ({channel_id})",
        )

        batch = payload.get("messages") or []
        messages.extend(batch)
        remaining -= len(batch)
        cursor = (payload.get("response_metadata") or {}).get("next_cursor")
        if not cursor or not batch:
            break
    return messages[:limit]


def resolve_sync_channels(
    token: str,
    config: SlackConfigRequest,
) -> tuple[set[str], set[str], set[str], dict[str, str], int]:
    """
    Resolve channel sets for sync, always re-discovering member channels.

    Returns (configured, incident, on_call, channel_id_to_name, channels_discovered).
    """
    allowlist = set(parse_csv_ids(config.channel_ids))
    discovered = list_accessible_channels(token)
    member_channels = [
        channel for channel in discovered if channel.get("is_member")
    ]
    id_to_name = {
        channel["id"]: channel["name"]
        for channel in member_channels
        if channel.get("id")
    }
    discovered_ids = set(id_to_name)
    channels_discovered = len(discovered_ids)

    if allowlist:
        configured = allowlist & discovered_ids or allowlist
    else:
        configured = discovered_ids

    incident = set(parse_csv_ids(config.incident_channel_ids)) or configured
    on_call = set(parse_csv_ids(config.on_call_channel_ids)) or configured
    return configured, incident, on_call, id_to_name, channels_discovered


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


def _is_thread_parent_message(message: dict[str, Any]) -> bool:
    """True when message has thread replies worth fetching via conversations.replies."""
    if _message_is_bot(message):
        return False
    if (message.get("reply_count") or 0) > 0:
        return True
    ts = message.get("ts")
    thread_ts = message.get("thread_ts")
    return ts is not None and thread_ts == ts


def _is_thread_reply_in_history(message: dict[str, Any]) -> bool:
    thread_ts = message.get("thread_ts")
    ts = message.get("ts")
    return thread_ts is not None and ts is not None and thread_ts != ts


def _is_standalone_channel_message(message: dict[str, Any]) -> bool:
    """Top-level channel message that is not a thread parent (single-message discussion)."""
    if _message_is_bot(message):
        return False
    if _is_thread_reply_in_history(message):
        return False
    if _is_thread_parent_message(message):
        return False
    return bool(message.get("ts"))


def _collect_mentions_and_users(
    messages: list[SlackMessageRecord],
    user_emails: dict[str, str],
) -> list[str]:
    mentions: list[str] = []
    for message in messages:
        mentions.extend(_extract_mentions(message.text))
        if message.user_id and message.user_id not in user_emails:
            user_emails[message.user_id] = ""
    return sorted(set(mentions))


def _finalize_thread_record(
    record: SlackThreadRecord,
    *,
    is_incident_channel: bool,
) -> SlackThreadRecord:
    resolver = is_resolved_incident_thread(
        record,
        is_incident_channel=is_incident_channel,
    )
    if resolver:
        last_human = next(
            (
                message
                for message in reversed(_human_messages(record.messages))
                if message.user_id
            ),
            None,
        )
        record.resolved_at = (
            _parse_ts(last_human.ts) if last_human and last_human.ts else None
        )
    return record


def _build_thread_record(
    *,
    channel_id: str,
    channel_name: str,
    thread_ts: str,
    parent_text: str,
    messages: list[SlackMessageRecord],
    workspace_url: str,
    component_names: dict[str, str],
    is_incident_channel: bool,
    is_on_call_channel: bool,
    user_emails: dict[str, str],
) -> SlackThreadRecord:
    record = SlackThreadRecord(
        channel_id=channel_id,
        channel_name=channel_name,
        thread_ts=thread_ts,
        parent_text=parent_text,
        messages=messages,
        component_id=_infer_component_id(channel_name, component_names),
        is_incident_channel=is_incident_channel,
        is_on_call_channel=is_on_call_channel,
        mentioned_user_ids=_collect_mentions_and_users(messages, user_emails),
        thread_url=build_thread_url(workspace_url, channel_id, thread_ts),
    )
    return _finalize_thread_record(record, is_incident_channel=is_incident_channel)


def _extract_mentions(text: str) -> list[str]:
    return MENTION_RE.findall(text or "")


def _normalize_channel_name(channel_name: str) -> str:
    return (channel_name or "").lstrip("#").strip().lower()


def is_incident_feed_channel(channel_name: str) -> bool:
    """
    Channels that may surface incident cards: name is exactly ``incident`` or
    starts with ``incident-`` (e.g. ``incident-payments``).
    """
    name = _normalize_channel_name(channel_name)
    return name == "incident" or name.startswith("incident-")


def _text_has_incident_keywords(text: str) -> bool:
    return bool(_INCIDENT_SIGNAL_RE.search(text or ""))


def _human_messages(messages: list[SlackMessageRecord]) -> list[SlackMessageRecord]:
    return [message for message in messages if not message.is_bot]


def thread_has_incident_signal(thread: SlackThreadRecord) -> bool:
    """Incident-like content: Jira key or incident keywords in parent / early replies."""
    if _JIRA_KEY_RE.search(thread.parent_text or ""):
        return True
    if _text_has_incident_keywords(thread.parent_text):
        return True
    human = _human_messages(thread.messages)
    if human:
        combined = " ".join(message.text for message in human[:3])
        if _text_has_incident_keywords(combined):
            return True
    return False


def qualifies_for_incident_feed(thread: SlackThreadRecord) -> bool:
    """
    Whether a Slack thread should appear on the investigation incident board.

    Channel must be ``#incident`` or ``incident-*``, and thread text must include
    a Jira key or incident keywords — not every message in the channel.
    """
    if not is_incident_feed_channel(thread.channel_name):
        return False
    if not _human_messages(thread.messages) and not (thread.parent_text or "").strip():
        return False
    return thread_has_incident_signal(thread)


def _contains_incident_signal(text: str, *, is_incident_channel: bool) -> bool:
    if is_incident_channel:
        return True
    return _text_has_incident_keywords(text)


def _is_resolution_message(message: SlackMessageRecord) -> bool:
    lowered = message.text.lower()
    if any(pattern in lowered for pattern in RESOLUTION_PATTERNS):
        return True
    return "white_check_mark" in message.reactions or "heavy_check_mark" in message.reactions


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
    return fetch_channel_history(
        token,
        channel_id,
        limit=10_000,
        oldest=oldest,
    )


def _fetch_thread_replies(
    token: str,
    channel_id: str,
    thread_ts: str,
) -> list[dict[str, Any]]:
    payload = _slack_api_get(
        "https://slack.com/api/conversations.replies",
        token=token,
        params={"channel": channel_id, "ts": thread_ts, "limit": 200},
        context=f"conversations.replies ({channel_id})",
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
    purpose: SlackFetchPurpose = "sync",
) -> tuple[list[SlackThreadRecord], dict[str, str], list[str], dict[str, int]]:
    """
    Return (threads, slack_user_id_to_email, warnings, sync_stats).

    ``purpose='feed'`` — lightweight path for incident cards (few channels,
    no thread-reply fan-out). ``purpose='sync'`` — full integration ingest.
    """
    if use_fixture or not config.bot_token.strip():
        return _fetch_slack_incident_threads_uncached(
            config,
            component_names=component_names,
            use_fixture=use_fixture,
            now=now,
            purpose=purpose,
        )

    cache_key = _slack_fetch_cache_key(config, purpose)
    ttl = _SLACK_FETCH_CACHE_TTL_SECONDS[purpose]
    cached = _slack_fetch_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < ttl:
        return cached[1]  # type: ignore[return-value]

    lock = _get_slack_fetch_lock(cache_key)
    with lock:
        cached = _slack_fetch_cache.get(cache_key)
        if cached and (time.time() - cached[0]) < ttl:
            return cached[1]  # type: ignore[return-value]

        result = _fetch_slack_incident_threads_uncached(
            config,
            component_names=component_names,
            use_fixture=use_fixture,
            now=now,
            purpose=purpose,
        )
        _slack_fetch_cache[cache_key] = (time.time(), result)
        return result


def _fetch_slack_incident_threads_uncached(
    config: SlackConfigRequest,
    *,
    component_names: dict[str, str] | None = None,
    use_fixture: bool = False,
    now: datetime | None = None,
    purpose: SlackFetchPurpose = "sync",
) -> tuple[list[SlackThreadRecord], dict[str, str], list[str], dict[str, int]]:
    """
    Return (threads, slack_user_id_to_email, warnings, sync_stats).

    sync_stats keys: channels_discovered, channels_synced, messages_ingested.
    """
    component_names = component_names or {}
    empty_stats = {
        "channels_discovered": 0,
        "channels_synced": 0,
        "messages_ingested": 0,
    }
    if use_fixture or not config.bot_token.strip():
        workspace_url, threads, users = load_fixture_channel_history()
        if not config.workspace_url.strip():
            config = config.model_copy(update={"workspace_url": workspace_url})
        fixture_stats = {
            "channels_discovered": len({thread.channel_id for thread in threads}),
            "channels_synced": len({thread.channel_id for thread in threads}),
            "messages_ingested": sum(len(thread.messages) for thread in threads),
        }
        return threads, users, [], fixture_stats

    now = now or datetime.now(UTC)
    if purpose == "feed":
        lookback_days = FEED_LOOKBACK_DAYS
        history_limit = FEED_HISTORY_LIMIT
    else:
        lookback_days = LOOKBACK_DAYS
        history_limit = SYNC_HISTORY_LIMIT
    oldest = now.timestamp() - (lookback_days * 86400)
    try:
        configured, incident_channels, on_call_channels, id_to_name, channels_discovered = (
            resolve_sync_channels(config.bot_token, config)
        )
    except ValueError as exc:
        return [], {}, [str(exc)], empty_stats

    target_channels = configured
    if purpose == "feed":
        target_channels = _incident_feed_channel_ids(configured, id_to_name)
        if not target_channels:
            return (
                [],
                {},
                [
                    "No Slack channels named #incident or incident-* found for the "
                    "incident board. Rename your incident channel or run a full "
                    "Slack sync from Settings."
                ],
                {**empty_stats, "channels_discovered": channels_discovered},
            )
    elif not target_channels:
        return (
            [],
            {},
            [
                "No Slack channels available for sync. Invite the bot to channels "
                "you want imported, or add channel IDs under Advanced settings."
            ],
            {**empty_stats, "channels_discovered": channels_discovered},
        )

    warnings: list[str] = []
    threads: list[SlackThreadRecord] = []
    user_emails: dict[str, str] = {}
    messages_ingested = 0
    channels_synced = 0

    for channel_id in sorted(target_channels):
        channel_name = id_to_name.get(channel_id, channel_id)
        is_incident_channel = channel_id in incident_channels
        is_on_call_channel = channel_id in on_call_channels
        try:
            history = fetch_channel_history(
                config.bot_token,
                channel_id,
                limit=history_limit,
                oldest=oldest,
            )
        except ValueError as exc:
            warnings.append(str(exc))
            continue

        channels_synced += 1
        messages_ingested += len(history)

        reply_fetches = 0
        for parent in [message for message in history if _is_thread_parent_message(message)]:
            thread_ts = str(parent.get("ts", ""))
            if not thread_ts:
                continue
            parent_text = str(parent.get("text") or "")
            reply_count = int(parent.get("reply_count") or 0)
            if reply_count > 0 and purpose == "sync":
                if reply_fetches < MAX_THREAD_REPLY_FETCHES_PER_CHANNEL:
                    try:
                        replies = _fetch_thread_replies(
                            config.bot_token,
                            channel_id,
                            thread_ts,
                        )
                        reply_fetches += 1
                    except ValueError as exc:
                        warnings.append(str(exc))
                        replies = [parent]
                    messages_ingested += max(0, len(replies) - 1)
                else:
                    replies = [parent]
            else:
                replies = [parent]

            messages = [_message_from_dict(row) for row in replies]
            threads.append(
                _build_thread_record(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    thread_ts=thread_ts,
                    parent_text=parent_text,
                    messages=messages,
                    workspace_url=config.workspace_url,
                    component_names=component_names,
                    is_incident_channel=is_incident_channel,
                    is_on_call_channel=is_on_call_channel,
                    user_emails=user_emails,
                )
            )

        for message in history:
            if not _is_standalone_channel_message(message):
                continue
            ts = str(message.get("ts", ""))
            if not ts:
                continue
            text = str(message.get("text") or "")
            if not text.strip():
                continue
            slack_message = _message_from_dict(message)
            threads.append(
                _build_thread_record(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    thread_ts=ts,
                    parent_text=text,
                    messages=[slack_message],
                    workspace_url=config.workspace_url,
                    component_names=component_names,
                    is_incident_channel=is_incident_channel,
                    is_on_call_channel=is_on_call_channel,
                    user_emails=user_emails,
                )
            )

    sync_stats = {
        "channels_discovered": channels_discovered,
        "channels_synced": channels_synced,
        "messages_ingested": messages_ingested,
    }
    return threads, user_emails, warnings, sync_stats


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
