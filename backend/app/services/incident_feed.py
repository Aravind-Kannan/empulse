"""Live incident cards from Jira issues and Slack incident threads."""

from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.operational import IncidentRecord
from app.schemas.investigation import IncidentStatus, IncidentSummary
from app.services.integration_config_store import get_jira_config, get_slack_config
from app.services.jira_client import fetch_jira_issues
from app.services.jira_types import JiraIssueActivity
from app.services.slack_client import fetch_slack_incident_threads, thread_title
from app.services.slack_types import SlackThreadRecord

logger = logging.getLogger(__name__)

_JIRA_ID_PATTERN = re.compile(r"[A-Z][A-Z0-9]+-\d+")
_RECENT_DAYS = 14
_INCIDENT_FEED_CACHE_TTL_SECONDS = 60.0
_incident_feed_cache: dict[
    uuid.UUID,
    tuple[float, list[IncidentSummary], list[str], dict[str, bool]],
] = {}


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slack_ts_to_datetime(ts: str) -> datetime:
    return datetime.fromtimestamp(float(ts), tz=UTC)


def _map_jira_status(status: str, status_category: str) -> IncidentStatus:
    if status_category.lower() == "done":
        return "Closed"
    lowered = status.lower()
    if "wait" in lowered or "block" in lowered:
        return "Waiting for Input"
    if "progress" in lowered or "investig" in lowered or "review" in lowered:
        return "Investigating"
    if "resolved" in lowered or "done" in lowered:
        return "Resolved"
    return "Open"


def _map_slack_status(thread: SlackThreadRecord) -> IncidentStatus:
    if thread.resolved_at:
        return "Resolved"
    text = thread.parent_text.lower()
    if "resolved" in text or "fixed" in text or "mitigated" in text:
        return "Resolved"
    if "investigat" in text or "looking into" in text or "on it" in text:
        return "Investigating"
    if "?" in thread.parent_text and "anyone" in text:
        return "Waiting for Input"
    return "Open"


def _jira_system_scope(issue: JiraIssueActivity) -> str:
    if issue.jira_component_names:
        return issue.jira_component_names[0]
    if issue.project_key:
        return issue.project_key
    return "Jira"


def _jira_to_summary(
    issue: JiraIssueActivity,
    *,
    status_override: IncidentStatus | None = None,
) -> IncidentSummary:
    title = (issue.summary or issue.issue_key).strip()
    updated = issue.updated_at or datetime.now(UTC)
    return IncidentSummary(
        id=f"jira:{issue.issue_key}",
        title=title,
        status=status_override or _map_jira_status(issue.status, issue.status_category),
        system_scope=_jira_system_scope(issue),
        jira_id=issue.issue_key,
        updated_at=_iso(updated),
        source="jira",
        priority=issue.priority,
        channel_name=None,
    )


def _slack_to_summary(
    thread: SlackThreadRecord,
    *,
    status_override: IncidentStatus | None = None,
) -> IncidentSummary:
    title = thread_title(thread.parent_text)
    jira_match = _JIRA_ID_PATTERN.search(thread.parent_text)
    updated = _slack_ts_to_datetime(thread.thread_ts)
    channel = thread.channel_name.lstrip("#") or thread.channel_id
    return IncidentSummary(
        id=f"slack:{thread.channel_id}:{thread.thread_ts}",
        title=title,
        status=status_override or _map_slack_status(thread),
        system_scope=channel,
        jira_id=jira_match.group(0) if jira_match else "",
        updated_at=_iso(updated),
        source="slack",
        priority=None,
        channel_name=channel,
    )


def _load_status_overrides(
    db: Session,
    tenant_id: uuid.UUID,
) -> dict[str, IncidentStatus]:
    rows = (
        db.query(IncidentRecord)
        .filter(IncidentRecord.tenant_id == tenant_id)
        .all()
    )
    return {row.id: row.status for row in rows}  # type: ignore[misc]


def _apply_overrides(
    incidents: list[IncidentSummary],
    overrides: dict[str, IncidentStatus],
) -> list[IncidentSummary]:
    if not overrides:
        return incidents
    merged: list[IncidentSummary] = []
    for item in incidents:
        override = overrides.get(item.id)
        if override:
            merged.append(item.model_copy(update={"status": override}))
        else:
            merged.append(item)
    return merged


def _incident_stub_from_id(incident_id: str) -> IncidentSummary | None:
    """Fallback when live Jira/Slack fetch is slow or temporarily unavailable."""
    if incident_id.startswith("jira:"):
        issue_key = incident_id.removeprefix("jira:").strip()
        if not issue_key:
            return None
        project = issue_key.rsplit("-", 1)[0] if "-" in issue_key else "Jira"
        return IncidentSummary(
            id=incident_id,
            title=issue_key,
            status="Open",
            system_scope=project,
            jira_id=issue_key,
            updated_at=_iso(datetime.now(UTC)),
            source="jira",
            priority=None,
            channel_name=None,
        )
    if incident_id.startswith("slack:"):
        parts = incident_id.split(":", 2)
        if len(parts) < 3:
            return None
        channel_id, thread_ts = parts[1], parts[2]
        return IncidentSummary(
            id=incident_id,
            title=f"Slack thread {thread_ts}",
            status="Open",
            system_scope=channel_id,
            jira_id="",
            updated_at=_iso(datetime.now(UTC)),
            source="slack",
            priority=None,
            channel_name=channel_id,
        )
    return None


def invalidate_incident_feed_cache(tenant_id: uuid.UUID | None = None) -> None:
    if tenant_id is None:
        _incident_feed_cache.clear()
        return
    _incident_feed_cache.pop(tenant_id, None)


def _is_recent(updated_at: str) -> bool:
    try:
        parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    cutoff = datetime.now(UTC) - timedelta(days=_RECENT_DAYS)
    return parsed >= cutoff


def fetch_live_incidents(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    use_cache: bool = True,
) -> tuple[list[IncidentSummary], list[str], dict[str, bool]]:
    """
    Pull active incidents from connected Jira and Slack integrations.
    Returns (incidents, warnings, sources_connected).
    """
    if use_cache:
        cached = _incident_feed_cache.get(tenant_id)
        if cached and (time.time() - cached[0]) < _INCIDENT_FEED_CACHE_TTL_SECONDS:
            return cached[1], list(cached[2]), dict(cached[3])
    incidents: list[IncidentSummary] = []
    warnings: list[str] = []
    sources_connected = {"jira": False, "slack": False}
    overrides = _load_status_overrides(db, tenant_id)

    jira_config = get_jira_config(db, tenant_id)
    if jira_config:
        sources_connected["jira"] = True
        try:
            issues = fetch_jira_issues(jira_config)
            for issue in issues:
                if issue.is_done or not issue.is_bug_or_incident:
                    continue
                incidents.append(_jira_to_summary(issue))
        except Exception as exc:
            logger.warning("Jira incident fetch failed: %s", exc)
            warnings.append(f"Could not load Jira incidents: {exc}")

    slack_config = get_slack_config(db, tenant_id)
    if slack_config:
        sources_connected["slack"] = True
        try:
            threads, _, slack_warnings, _ = fetch_slack_incident_threads(slack_config)
            warnings.extend(slack_warnings)
            cutoff = datetime.now(UTC) - timedelta(days=_RECENT_DAYS)
            for thread in threads:
                if not (thread.is_incident_channel or thread.is_on_call_channel):
                    continue
                thread_dt = _slack_ts_to_datetime(thread.thread_ts)
                if thread_dt < cutoff:
                    continue
                incidents.append(_slack_to_summary(thread))
        except Exception as exc:
            logger.warning("Slack incident fetch failed: %s", exc)
            warnings.append(f"Could not load Slack incidents: {exc}")

    incidents = _apply_overrides(incidents, overrides)
    incidents = [item for item in incidents if _is_recent(item.updated_at)]
    incidents.sort(key=lambda item: item.updated_at, reverse=True)

    # De-duplicate Jira issues also mentioned in Slack threads
    seen_jira: set[str] = set()
    deduped: list[IncidentSummary] = []
    for item in incidents:
        if item.source == "jira":
            if item.jira_id in seen_jira:
                continue
            seen_jira.add(item.jira_id)
        deduped.append(item)

    _incident_feed_cache[tenant_id] = (time.time(), deduped, warnings, sources_connected)
    return deduped, warnings, sources_connected


def get_incident_by_id(
    db: Session,
    tenant_id: uuid.UUID,
    incident_id: str,
) -> IncidentSummary | None:
    incidents, _, _ = fetch_live_incidents(db, tenant_id)
    match = next((item for item in incidents if item.id == incident_id), None)
    if match:
        return match
    return _incident_stub_from_id(incident_id)


def build_faq_suggestions(
    incidents: list[IncidentSummary],
    *,
    active: IncidentSummary | None = None,
    limit: int = 6,
) -> list[str]:
    """Incident-specific FAQ prompts for the chat suggestion chips."""
    pool: list[IncidentSummary] = []
    if active:
        pool.append(active)
    pool.extend(item for item in incidents if not active or item.id != active.id)

    suggestions: list[str] = []
    seen: set[str] = set()

    def add(text: str) -> None:
        normalized = text.strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        suggestions.append(normalized)

    for item in pool[:4]:
        if item.source == "jira" and item.jira_id:
            add(f"What is the root cause of {item.jira_id}?")
            add(f"Who should own {item.jira_id} — {item.title}?")
            add(f"What is the workaround for {item.jira_id}?")
        elif item.source == "slack" and item.channel_name:
            add(f"What is happening in #{item.channel_name}?")
            add(f"Who was paged for the #{item.channel_name} thread?")
        add(f"Summarize impact for: {item.title}")

    if not suggestions:
        add("What open incidents need attention right now?")
        add("Which component is most at risk this week?")
        add("Who are the on-call experts for the latest outage?")

    return suggestions[:limit]
