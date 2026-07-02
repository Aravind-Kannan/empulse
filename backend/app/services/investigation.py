from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models.operational import (
    Assignment,
    Component,
    Employee,
    IncidentRecord,
    NotionDocSnapshot,
)
from app.models.tenant import Tenant
from app.schemas.investigation import (
    IncidentListResponse,
    IncidentStatus,
    IncidentSummary,
    InvestigationChatRequest,
    InvestigationDiagnostics,
    InvestigationReference,
    SmeRecommendation,
)
from app.services.identity_resolver import resolve_author_employee_id
from app.services.incident_feed import (
    build_faq_suggestions,
    fetch_live_incidents,
    get_incident_by_id,
)
from app.services.integration_telemetry import (
    get_cached_jira_issues,
    get_cached_slack_threads,
)
from app.services.tenant_cognee import (
    tenant_cognee_context,
    tenant_write_memory_record,
)
from app.tenancy import tenant_dataset_name

_BRIEFING_CACHE_TTL_SECONDS = 1800.0
_briefing_cache: dict[tuple[str, str], tuple[float, InvestigationDiagnostics]] = {}

_BRIEFING_QUERY = (
    "incident root cause workaround impact owners escalation postmortem runbook"
)

INCIDENT_STATUSES: list[IncidentStatus] = [
    "Open",
    "Investigating",
    "Waiting for Input",
    "Resolved",
    "Closed",
]

_JIRA_PATTERN = re.compile(r"[A-Z][A-Z0-9]+-\d+")
_WORKAROUND_HINTS = (
    "workaround",
    "mitigation",
    "failover",
    "rollback",
    "scale",
    "drain",
    "bypass",
    "degrad",
)
_SOLUTION_HINTS = _WORKAROUND_HINTS + (
    "solution",
    "fix",
    "resolve",
    "remediation",
    "mitigate",
    "patch",
    "hotfix",
    "runbook",
    "playbook",
    "recovery",
    "restored",
    "mitigated",
)
_NO_WORKAROUND_MESSAGE = (
    "No workaround or solution found for this incident. "
    "No matching fix was identified in linked Jira tickets, Slack threads, or "
    "runbooks. Sync integrations and use Refresh, or ask in chat."
)
_ROOT_CAUSE_HINTS = (
    "root cause",
    "caused by",
    "due to",
    "failure",
    "outage",
    "timeout",
    "exhaust",
    "stampede",
    "latency",
    "error",
    "postmortem",
)

_INTERNAL_RECORD_MARKERS = (
    "record_type",
    "resolution_note",
    "incident_status_update",
    "updated_text",
    "cognee_dataset",
    "graph_nodes_created",
    "graph_edges_created",
)

_QUERY_ECHO_PHRASES = (
    "incident root cause workaround",
    "impact owners escalation",
    "postmortem runbook",
)


@dataclass
class _GraphSearchHit:
    text: str
    similarity: float
    slack_thread_id: str | None = None
    notion_page_id: str | None = None
    jira_key: str | None = None
    component_name: str | None = None
    employee_name: str | None = None


@dataclass
class _GraphHop:
    """Internal representation of graph traversal hop for confidence scoring."""

    from_node: str
    edge: str
    to: str


@dataclass
class _GraphContext:
    search_hits: list[_GraphSearchHit] = field(default_factory=list)
    search_texts: list[str] = field(default_factory=list)
    components: list[Component] = field(default_factory=list)
    employees: list[Employee] = field(default_factory=list)
    assignments: list[Assignment] = field(default_factory=list)
    incident: IncidentSummary | None = None
    matched_components: list[Component] = field(default_factory=list)
    matched_employees: list[tuple[Employee, float]] = field(default_factory=list)
    graph_hops: list[_GraphHop] = field(default_factory=list)
    slack_threads: list[InvestigationReference] = field(default_factory=list)
    jira_tickets: list[InvestigationReference] = field(default_factory=list)
    notion_pages: list[InvestigationReference] = field(default_factory=list)
    postmortems: list[InvestigationReference] = field(default_factory=list)


def list_incidents(
    db: Session,
    tenant: Tenant,
    status: IncidentStatus | None = None,
) -> IncidentListResponse:
    incidents, warnings, sources_connected = fetch_live_incidents(db, tenant.id)
    if status:
        incidents = [item for item in incidents if item.status == status]
    suggestions = build_faq_suggestions(incidents)
    return IncidentListResponse(
        incidents=incidents,
        suggestions=suggestions,
        sources_connected=sources_connected,
        warnings=warnings,
    )


def update_incident_status(
    db: Session,
    tenant: Tenant,
    incident_id: str,
    status: IncidentStatus,
) -> IncidentSummary:
    live = get_incident_by_id(db, tenant.id, incident_id)
    if not live:
        raise ValueError(f"Incident '{incident_id}' not found.")

    record = (
        db.query(IncidentRecord)
        .filter(
            IncidentRecord.id == incident_id,
            IncidentRecord.tenant_id == tenant.id,
        )
        .one_or_none()
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    if record:
        record.status = status
        record.updated_at = now
        record.title = live.title
        record.system_scope = live.system_scope
        record.jira_id = live.jira_id or None
    else:
        record = IncidentRecord(
            id=incident_id,
            tenant_id=tenant.id,
            title=live.title,
            status=status,
            system_scope=live.system_scope,
            jira_id=live.jira_id or None,
            updated_at=now,
        )
        db.add(record)
    db.commit()
    db.refresh(record)
    return live.model_copy(update={"status": status, "updated_at": _iso_now(record.updated_at)})


def _iso_now(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


async def write_incident_memory_to_cognee(
    tenant_id: uuid.UUID,
    incident_id: str,
    status: IncidentStatus,
    *,
    resolution_note: str | None = None,
    title: str | None = None,
    system_scope: str | None = None,
    jira_id: str | None = None,
) -> None:
    """Write incident status transitions back into the tenant Cognee dataset."""
    note = (resolution_note or "").strip()
    updated_text = (
        f"Incident {incident_id} status changed to {status}."
        + (f" Resolution note: {note}" if note else "")
    )
    record = {
        "id": incident_id,
        "title": title,
        "system_scope": system_scope,
        "jira_id": jira_id,
        "status": status,
        "updated_text": updated_text,
        "resolution_note": note or None,
        "record_type": "incident_status_update",
    }
    await tenant_write_memory_record(tenant_id, record)


def _parse_jira_id(message: str) -> str | None:
    match = _JIRA_PATTERN.search(message)
    return match.group(0) if match else None


def _unwrap_search_result(item: Any) -> Any:
    if item is None:
        return None
    if hasattr(item, "search_result"):
        return getattr(item, "search_result")
    if isinstance(item, dict) and "search_result" in item:
        return item["search_result"]
    return item


def _extract_search_text(item: Any) -> str:
    raw = _unwrap_search_result(item)
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        record_type = str(raw.get("record_type") or "").strip()
        if record_type == "incident_status_update":
            updated = raw.get("updated_text")
            return str(updated).strip() if updated else ""

        for key in (
            "text",
            "content",
            "page_content",
            "snippet",
            "answer",
            "result",
            "updated_text",
            "title",
        ):
            value = raw.get(key)
            if value and not isinstance(value, (dict, list)):
                text = str(value).strip()
                if text and not _is_internal_memory_text(text):
                    return text

        if record_type or any(marker in raw for marker in _INTERNAL_RECORD_MARKERS):
            return ""

        serialized = json.dumps(raw)
        if _is_internal_memory_text(serialized):
            return ""
        return serialized[:600]
    for attr in ("text", "content", "page_content", "snippet"):
        if hasattr(raw, attr):
            value = getattr(raw, attr)
            if value:
                text = str(value).strip()
                if not _is_internal_memory_text(text):
                    return text
    text = str(raw)[:600]
    return "" if _is_internal_memory_text(text) else text


def _looks_like_json_fragment(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if stripped[0] in {'"', "{", "[", "}", "]"}:
        return True
    if re.search(r'"\w+"\s*:', stripped):
        return True
    if stripped.count(":") >= 2 and stripped.count('"') >= 2:
        return True
    return False


def _is_internal_memory_text(text: str) -> bool:
    lowered = text.lower()
    if any(marker in lowered for marker in _INTERNAL_RECORD_MARKERS):
        return True
    if _looks_like_json_fragment(text):
        return True
    if re.search(r"status changed to\s+(open|investigating|resolved|closed)", lowered):
        return True
    return False


def _is_query_echo_text(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in _QUERY_ECHO_PHRASES)


def _is_metadata_only_reference(text: str) -> bool:
    lowered = text.lower()
    if "documents unlinked" in lowered or "authored by unknown" in lowered:
        return True
    if "notion page" in lowered and "last edited" in lowered:
        return True
    return False


def _is_displayable_evidence_text(
    text: str,
    incident: IncidentSummary | None = None,
) -> bool:
    stripped = text.strip()
    if len(stripped) < 25:
        return False
    if _is_internal_memory_text(stripped):
        return False
    if _is_query_echo_text(stripped):
        return False
    if _is_metadata_only_reference(stripped):
        return False
    if _is_bare_ticket_summary(stripped, incident):
        return False
    return True


def _text_has_hints(text: str, hints: tuple[str, ...]) -> bool:
    lowered = text.lower()
    for hint in hints:
        if " " in hint:
            if hint in lowered:
                return True
        elif re.search(rf"\b{re.escape(hint)}", lowered):
            return True
    return False


def _pick_first_displayable(
    incident: IncidentSummary | None,
    *candidates: str | None,
) -> str | None:
    for candidate in candidates:
        if not candidate:
            continue
        stripped = candidate.strip()
        if _is_displayable_evidence_text(stripped, incident):
            return stripped[:400]
    return None


def _similarity_from_item(item: Any, rank: int) -> float:
    raw = _unwrap_search_result(item)
    if isinstance(raw, dict):
        for key in ("score", "similarity", "relevance", "vector_score"):
            value = raw.get(key)
            if value is not None:
                score = float(value)
                if 0.0 <= score <= 1.0:
                    return round(score * 100.0, 1)
                return min(100.0, round(score, 1))
        distance = raw.get("distance")
        if distance is not None:
            return max(0.0, min(100.0, round((1.0 - float(distance)) * 100.0, 1)))
    return max(18.0, round(90.0 - rank * 6.5, 1))


def _parse_graph_search_hits(raw_results: list[Any]) -> list[_GraphSearchHit]:
    hits: list[_GraphSearchHit] = []
    for rank, item in enumerate(raw_results):
        text = _extract_search_text(item)
        if not text:
            continue
        raw = _unwrap_search_result(item)
        slack_thread_id: str | None = None
        notion_page_id: str | None = None
        jira_key = _parse_jira_id(text)
        component_name: str | None = None
        employee_name: str | None = None

        if isinstance(raw, dict):
            slack_thread_id = (
                raw.get("thread_id")
                or raw.get("slack_thread_id")
                or None
            )
            notion_page_id = raw.get("page_id") or raw.get("notion_page_id")
            jira_key = jira_key or raw.get("ticket_id") or raw.get("jira_key")
            component_name = raw.get("component_name") or raw.get("component")
            employee_name = raw.get("employee_name") or raw.get("assignee")

        thread_match = re.search(
            r"thread_id['\"]?\s*[:=]\s*['\"]?([A-Z0-9]+:[0-9.]+)",
            text,
            re.I,
        )
        if thread_match:
            slack_thread_id = slack_thread_id or thread_match.group(1)

        page_match = re.search(
            r"page_id['\"]?\s*[:=]\s*['\"]?([a-f0-9-]{8,})",
            text,
            re.I,
        )
        if page_match:
            notion_page_id = notion_page_id or page_match.group(1)

        component_match = re.search(
            r"(?:blocking component|documents|discusses component|component)\s+([A-Za-z0-9 _-]+)",
            text,
            re.I,
        )
        if component_match:
            component_name = component_name or component_match.group(1).strip()

        employee_match = re.search(
            r"(?:assigned to|resolved by|authored by)\s+([A-Za-z][A-Za-z .'-]+)",
            text,
            re.I,
        )
        if employee_match:
            employee_name = employee_name or employee_match.group(1).strip()

        hits.append(
            _GraphSearchHit(
                text=text,
                similarity=_similarity_from_item(item, rank),
                slack_thread_id=slack_thread_id,
                notion_page_id=notion_page_id,
                jira_key=jira_key,
                component_name=component_name,
                employee_name=employee_name,
            )
        )
    return hits


def _incident_search_terms(incident: IncidentSummary | None) -> set[str]:
    if not incident:
        return set()
    terms = {
        incident.id.lower(),
        incident.title.lower(),
        incident.system_scope.lower(),
    }
    if incident.jira_id:
        terms.add(incident.jira_id.lower())
    if incident.channel_name:
        terms.add(incident.channel_name.lstrip("#").lower())
    return {term for term in terms if term}


def _text_matches_incident(text: str, incident: IncidentSummary | None) -> bool:
    if not incident:
        return False
    lowered = text.lower()
    return any(term in lowered for term in _incident_search_terms(incident))


def _rank_search_hits_for_incident(
    hits: list[_GraphSearchHit],
    incident: IncidentSummary | None,
) -> list[_GraphSearchHit]:
    if not incident or not hits:
        return hits

    def score(hit: _GraphSearchHit) -> float:
        blob = hit.text.lower()
        bonus = sum(
            18.0 for term in _incident_search_terms(incident) if term in blob
        )
        if hit.jira_key and incident.jira_id and hit.jira_key == incident.jira_id:
            bonus += 25.0
        return hit.similarity + bonus

    return sorted(hits, key=score, reverse=True)


def _prioritize_search_texts(
    search_texts: list[str],
    incident: IncidentSummary | None,
) -> list[str]:
    if not incident:
        return search_texts
    matched = [text for text in search_texts if _text_matches_incident(text, incident)]
    if not matched:
        return search_texts
    remainder = [text for text in search_texts if text not in matched]
    return matched + remainder


def _make_graph_hop(from_node: str, edge: str, to: str) -> _GraphHop:
    return _GraphHop(from_node=from_node, edge=edge, to=to)


def _extract_slack_channel_label(
    text: str,
    incident: IncidentSummary | None,
) -> str:
    channel_match = re.search(r"#([\w-]+)", text)
    if channel_match:
        return f"Slack #{channel_match.group(1)} Thread"
    if incident and incident.channel_name:
        return f"Slack #{incident.channel_name.lstrip('#')} Thread"
    return "Slack Incident Thread"


def _best_matching_sentence(
    text: str,
    hints: tuple[str, ...],
    *,
    incident: IncidentSummary | None = None,
) -> str | None:
    for sentence in text.split("."):
        stripped = sentence.strip()
        if len(stripped) < 20:
            continue
        if not _text_has_hints(stripped, hints):
            continue
        if not _is_displayable_evidence_text(stripped, incident):
            continue
        return stripped[:400]
    return None


def _is_slack_hit(hit: _GraphSearchHit) -> bool:
    lowered = hit.text.lower()
    return bool(
        hit.slack_thread_id
        or "slack" in lowered
        or "incident thread" in lowered
        or "#" in hit.text
    )


def _is_jira_hit(hit: _GraphSearchHit) -> bool:
    lowered = hit.text.lower()
    return bool(hit.jira_key or "jira" in lowered or _JIRA_PATTERN.search(hit.text))


def _is_bare_ticket_summary(text: str, incident: IncidentSummary | None) -> bool:
    """Reject Jira title-only lines that are not causal analysis."""
    if not incident:
        return False
    stripped = text.strip()
    if len(stripped) < 12:
        return True
    lowered = stripped.lower()
    causal_markers = _ROOT_CAUSE_HINTS + (
        "block",
        "fail",
        "error",
        "timeout",
        "because",
        "due to",
        "caused",
        "outage",
        "degrad",
        "incident thread",
        "resolved by",
        "assigned to",
    )
    if any(marker in lowered for marker in causal_markers):
        return False
    if incident.jira_id and incident.jira_id.lower() in lowered:
        return True
    if incident.title and incident.title.lower() in lowered and len(stripped) < 120:
        return True
    return False


def _analyze_root_cause_from_graph(
    hits: list[_GraphSearchHit],
    incident: IncidentSummary | None,
    components: list[Component],
) -> str | None:
    """Synthesize probable root cause from ranked Cognee graph evidence."""
    if not hits:
        return None

    scored: list[tuple[float, _GraphSearchHit]] = []
    for hit in hits:
        if _is_bare_ticket_summary(hit.text, incident):
            continue
        if not _is_displayable_evidence_text(hit.text, incident):
            continue
        score = hit.similarity
        lowered = hit.text.lower()
        if _text_has_hints(lowered, _ROOT_CAUSE_HINTS):
            score += 28.0
        if _is_slack_hit(hit):
            score += 18.0
        if _is_jira_hit(hit) and any(
            token in lowered for token in ("block", "fail", "bug", "incident")
        ):
            score += 16.0
        if incident and _text_matches_incident(hit.text, incident):
            score += 12.0
        if any(component.name.lower() in lowered for component in components):
            score += 10.0
        scored.append((score, hit))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)
    evidence: list[str] = []
    for _, hit in scored[:4]:
        sentence = _best_matching_sentence(
            hit.text, _ROOT_CAUSE_HINTS, incident=incident
        )
        if not sentence:
            first = hit.text.split(".")[0].strip()
            if _is_displayable_evidence_text(first, incident):
                sentence = first
        if not sentence or len(sentence) < 25:
            continue
        if sentence not in evidence:
            evidence.append(sentence)

    if not evidence:
        return None
    if len(evidence) == 1:
        return evidence[0][:400]

    scope = incident.system_scope if incident else "the affected component"
    return (
        f"Analysis for {scope}: {evidence[0]}. "
        f"Supporting detail: {evidence[1]}"
    )[:400]


async def _fetch_cognee_root_cause_narrative(
    incident: IncidentSummary | None,
    tenant_id: uuid.UUID,
    *,
    timeout_seconds: float = 12.0,
) -> str | None:
    """Ask Cognee graph completion for an analyzed root-cause narrative."""
    if not incident:
        return None

    import cognee
    from cognee.modules.search.types.SearchType import SearchType

    dataset = tenant_dataset_name(tenant_id)
    query = (
        f"Analyze the probable root cause of the incident: {incident.title}. "
        f"System scope: {incident.system_scope}. "
        + (f"Jira ticket: {incident.jira_id}. " if incident.jira_id else "")
        + "Use Slack incident threads, Jira blocking relationships, and component "
        "ownership from the knowledge graph. Explain what failed and why."
    )

    async def _run() -> list[Any]:
        async with tenant_cognee_context(tenant_id):
            try:
                results = await cognee.search(
                    query,
                    query_type=SearchType.GRAPH_COMPLETION,
                    datasets=[dataset],
                    top_k=5,
                )
            except TypeError:
                results = await cognee.search(
                    query,
                    datasets=[dataset],
                    top_k=5,
                )
            return results if isinstance(results, list) else list(results or [])

    try:
        results = await asyncio.wait_for(_run(), timeout=timeout_seconds)
    except (asyncio.TimeoutError, Exception):
        return None

    for item in results[:3]:
        text = _extract_search_text(item).strip()
        if _is_displayable_evidence_text(text, incident):
            return text[:400]
    return None


def _extract_slack_jira_diagnostics(
    hits: list[_GraphSearchHit],
    incident: IncidentSummary | None,
) -> tuple[str | None, str | None]:
    root_cause: str | None = None
    workaround: str | None = None

    for hit in hits:
        if not (_is_slack_hit(hit) or _is_jira_hit(hit)):
            continue
        if not root_cause:
            sentence = _best_matching_sentence(
                hit.text, _ROOT_CAUSE_HINTS, incident=incident
            )
            if sentence:
                root_cause = sentence
            elif (
                _is_slack_hit(hit)
                and _is_displayable_evidence_text(hit.text, incident)
            ):
                root_cause = hit.text.split(".")[0].strip()[:400]
            elif hit.jira_key and "block" in hit.text.lower():
                candidate = hit.text.split(".")[0].strip()[:400]
                if _is_displayable_evidence_text(candidate, incident):
                    root_cause = candidate
        if not workaround:
            sentence = _best_matching_sentence(
                hit.text, _SOLUTION_HINTS, incident=incident
            )
            if sentence:
                workaround = sentence

    return root_cause, workaround


def _is_solution_evidence_hit(hit: _GraphSearchHit) -> bool:
    if not _is_displayable_evidence_text(hit.text):
        return False
    lowered = hit.text.lower()
    if _text_has_hints(lowered, _SOLUTION_HINTS):
        return True
    if "runbook" in lowered or "playbook" in lowered:
        return not _is_metadata_only_reference(hit.text)
    return _is_slack_hit(hit) or _is_jira_hit(hit)


def _analyze_solutions_from_graph(
    hits: list[_GraphSearchHit],
    incident: IncidentSummary | None,
) -> str | None:
    """Synthesize workarounds from Cognee Slack/Jira/runbook evidence."""
    if not hits:
        return None

    scored: list[tuple[float, _GraphSearchHit]] = []
    for hit in hits:
        if not _is_solution_evidence_hit(hit):
            continue
        lowered = hit.text.lower()
        if not _text_has_hints(lowered, _SOLUTION_HINTS):
            if not ("runbook" in lowered or "playbook" in lowered):
                continue
            if _is_metadata_only_reference(hit.text):
                continue
        score = hit.similarity
        if _text_has_hints(lowered, _WORKAROUND_HINTS):
            score += 30.0
        if "runbook" in lowered or "playbook" in lowered:
            score += 22.0
        if _is_slack_hit(hit):
            score += 16.0
        if _is_jira_hit(hit):
            score += 14.0
        if incident and _text_matches_incident(hit.text, incident):
            score += 10.0
        scored.append((score, hit))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)
    for _, hit in scored[:4]:
        sentence = _best_matching_sentence(
            hit.text, _SOLUTION_HINTS, incident=incident
        )
        if sentence:
            return sentence[:400]

    return None


async def _fetch_cognee_solutions_narrative(
    incident: IncidentSummary | None,
    tenant_id: uuid.UUID,
    *,
    timeout_seconds: float = 12.0,
) -> str | None:
    """Ask Cognee for workarounds and solutions from linked tickets and Slack."""
    if not incident:
        return None

    import cognee
    from cognee.modules.search.types.SearchType import SearchType

    dataset = tenant_dataset_name(tenant_id)
    query = (
        f"What workarounds or solutions exist for incident: {incident.title}? "
        f"System scope: {incident.system_scope}. "
        + (f"Jira ticket: {incident.jira_id}. " if incident.jira_id else "")
        + "Search Slack incident threads, related Jira tickets, and runbooks in "
        "the knowledge graph. List concrete mitigation or fix steps only."
    )

    async def _run() -> list[Any]:
        async with tenant_cognee_context(tenant_id):
            try:
                results = await cognee.search(
                    query,
                    query_type=SearchType.GRAPH_COMPLETION,
                    datasets=[dataset],
                    top_k=5,
                )
            except TypeError:
                results = await cognee.search(
                    query,
                    datasets=[dataset],
                    top_k=5,
                )
            return results if isinstance(results, list) else list(results or [])

    try:
        results = await asyncio.wait_for(_run(), timeout=timeout_seconds)
    except (asyncio.TimeoutError, Exception):
        return None

    for item in results[:3]:
        text = _extract_search_text(item).strip()
        if not _is_displayable_evidence_text(text, incident):
            continue
        if _text_has_hints(text, _SOLUTION_HINTS):
            return text[:400]
        if "step" in text.lower() and _text_has_hints(text, ("mitigat", "fix")):
            return text[:400]
    return None


async def _resolve_workaround(
    *,
    hits: list[_GraphSearchHit],
    search_texts: list[str],
    incident: IncidentSummary | None,
    tenant_id: uuid.UUID,
    platform_workaround: str | None,
) -> tuple[str, bool]:
    cognee_solutions = await _fetch_cognee_solutions_narrative(incident, tenant_id)
    graph_solutions = _analyze_solutions_from_graph(hits, incident)
    synthesized = _synthesize_workaround(search_texts, incident)

    for candidate in (
        cognee_solutions,
        graph_solutions,
        platform_workaround,
        synthesized,
    ):
        picked = _pick_first_displayable(incident, candidate)
        if picked:
            return picked, True

    return _NO_WORKAROUND_MESSAGE, False


def _diagnostics_to_json(diagnostics: InvestigationDiagnostics) -> dict:
    return diagnostics.model_dump(mode="json", by_alias=True)


def _reference_type(text: str) -> str:
    lowered = text.lower()
    if "postmortem" in lowered or "post-mortem" in lowered:
        return "postmortem"
    if "slack" in lowered or "#" in text:
        return "slack"
    if "notion" in lowered or "runbook" in lowered or "playbook" in lowered:
        return "notion"
    if _JIRA_PATTERN.search(text) or "jira" in lowered:
        return "jira"
    if "notion.so" in lowered:
        return "notion"
    return "notion"


def _reference_title(text: str, ref_type: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        return lines[0][:120]
    jira = _parse_jira_id(text)
    if jira:
        return f"Jira {jira}"
    return f"{ref_type.title()} reference"


def _reference_url(text: str, ref_type: str) -> str:
    url_match = re.search(r"https?://\S+", text)
    if url_match:
        return url_match.group(0).rstrip(".,)")
    if ref_type == "slack":
        channel = re.search(r"#[\w-]+", text)
        return channel.group(0) if channel else "slack://thread"
    if ref_type == "jira":
        jira = _parse_jira_id(text)
        return f"jira://{jira}" if jira else "jira://ticket"
    return "notion://page"


def _presence_for_score(score: float) -> str:
    if score >= 85:
        return "online"
    if score >= 65:
        return "away"
    return "offline"


def invalidate_briefing_cache(
    tenant_id: uuid.UUID | None = None,
    incident_id: str | None = None,
) -> None:
    if tenant_id is None:
        _briefing_cache.clear()
        return
    if incident_id is None:
        for key in list(_briefing_cache):
            if key[0] == str(tenant_id):
                _briefing_cache.pop(key, None)
        return
    _briefing_cache.pop((str(tenant_id), incident_id), None)


def _lookup_jira_issue(
    issue_key: str,
    db: Session | None = None,
    tenant_id: uuid.UUID | None = None,
):
    for issue in get_cached_jira_issues():
        if issue.issue_key == issue_key:
            return issue
    if db is not None and tenant_id is not None:
        from app.services.integration_config_store import get_jira_config
        from app.services.jira_client import fetch_jira_issues

        config = get_jira_config(db, tenant_id)
        if config:
            try:
                for issue in fetch_jira_issues(config):
                    if issue.issue_key == issue_key:
                        return issue
            except Exception:
                return None
    return None


def _lookup_slack_thread(incident_id: str):
    if not incident_id.startswith("slack:"):
        return None
    parts = incident_id.split(":", 2)
    if len(parts) < 3:
        return None
    channel_id, thread_ts = parts[1], parts[2]
    for thread in get_cached_slack_threads():
        if thread.channel_id == channel_id and thread.thread_ts == thread_ts:
            return thread
    return None


def _component_owners_for_scope(
    components: list[Component],
    employees: list[Employee],
    scope: str,
) -> list[tuple[Employee, float]]:
    scope_lower = scope.lower().strip()
    if not scope_lower:
        return []
    matched_components = [
        component
        for component in components
        if component.name.lower() == scope_lower
        or scope_lower in component.name.lower()
        or component.name.lower() in scope_lower
    ]
    if not matched_components:
        return []

    owners: list[tuple[Employee, float]] = []
    component_ids = {component.id for component in matched_components}
    for employee in employees:
        share = sum(
            assignment.codebase_share_pct
            for assignment in employee.assignments
            if assignment.component_id in component_ids
        )
        if share <= 0 and not any(
            assignment.component_id in component_ids for assignment in employee.assignments
        ):
            continue
        score = min(95.0, 70.0 + share / 2)
        owners.append((employee, round(score, 1)))
    owners.sort(key=lambda item: item[1], reverse=True)
    return owners[:3]


def _operational_context_for_incident(
    db: Session,
    tenant_id: uuid.UUID,
    incident: IncidentSummary | None,
    employees: list[Employee],
    components: list[Component],
) -> tuple[
    list[SmeRecommendation],
    list[InvestigationReference],
    list[InvestigationReference],
    list[InvestigationReference],
]:
    """SMEs and references from Jira assignees, component owners, and Slack responders."""
    sme_scores: dict[str, tuple[Employee, float, str]] = {}
    slack_refs: list[InvestigationReference] = []
    jira_refs: list[InvestigationReference] = []
    notion_refs: list[InvestigationReference] = []

    def add_employee(
        employee: Employee,
        score: float,
        *,
        role_hint: str | None = None,
    ) -> None:
        role = role_hint or employee.role
        existing = sme_scores.get(employee.id)
        if not existing or score > existing[1]:
            sme_scores[employee.id] = (employee, score, role)

    if incident:
        for employee, score in _component_owners_for_scope(
            components, employees, incident.system_scope
        ):
            add_employee(employee, score, role_hint=f"{employee.role} · component owner")

        if incident.jira_id:
            issue = _lookup_jira_issue(incident.jira_id, db, tenant_id)
            if issue:
                jira_refs.append(
                    InvestigationReference(
                        id=f"jira-live-{issue.issue_key}",
                        type="jira",
                        title=f"{issue.issue_key}: {issue.summary or issue.issue_key}",
                        url=issue.issue_url or f"jira://{issue.issue_key}",
                        snippet=(
                            f"{issue.issue_type} · {issue.priority} · {issue.status}"
                            + (
                                f" · assignee mapped"
                                if issue.assignee_provider_user_id
                                else ""
                            )
                        ),
                    )
                )
                if issue.assignee_provider_user_id:
                    assignee_id = resolve_author_employee_id(
                        db,
                        tenant_id,
                        "jira",
                        issue.assignee_provider_user_id,
                        email_hint=issue.assignee_email,
                    )
                    assignee = next(
                        (row for row in employees if row.id == assignee_id),
                        None,
                    ) if assignee_id else None
                    if assignee:
                        add_employee(
                            assignee,
                            94.0,
                            role_hint="Jira assignee",
                        )

        if incident.source == "slack":
            thread = _lookup_slack_thread(incident.id)
            if thread:
                channel = thread.channel_name.lstrip("#") or thread.channel_id
                slack_refs.append(
                    InvestigationReference(
                        id=f"slack-live-{thread.channel_id}-{thread.thread_ts}",
                        type="slack",
                        title=thread.parent_text[:120],
                        url=thread.thread_url or f"slack://{channel}",
                        snippet=f"#{channel} incident thread",
                    )
                )
                if thread.resolved_by_employee_id:
                    resolver = next(
                        (
                            row
                            for row in employees
                            if row.id == thread.resolved_by_employee_id
                        ),
                        None,
                    )
                    if resolver:
                        add_employee(resolver, 90.0, role_hint="Resolved thread")
                for message in thread.messages[:12]:
                    if message.is_bot or not message.user_id:
                        continue
                    employee_id = resolve_author_employee_id(
                        db,
                        tenant_id,
                        "slack",
                        message.user_id,
                    )
                    responder = next(
                        (row for row in employees if row.id == employee_id),
                        None,
                    ) if employee_id else None
                    if responder:
                        add_employee(
                            responder,
                            82.0,
                            role_hint="Slack responder",
                        )

    smes = [
        SmeRecommendation(
            employee_id=employee.id,
            name=employee.name,
            role=role,
            compatibility_score=score,
            status=_presence_for_score(score),  # type: ignore[arg-type]
        )
        for employee, score, role in sme_scores.values()
    ]
    smes.sort(key=lambda row: row.compatibility_score, reverse=True)
    return smes[:5], slack_refs, jira_refs, notion_refs


def _merge_sme_recommendations(
    *groups: list[SmeRecommendation],
) -> list[SmeRecommendation]:
    merged: dict[str, SmeRecommendation] = {}
    for group in groups:
        for sme in group:
            existing = merged.get(sme.employee_id)
            if not existing or sme.compatibility_score > existing.compatibility_score:
                merged[sme.employee_id] = sme
    return sorted(
        merged.values(),
        key=lambda row: row.compatibility_score,
        reverse=True,
    )[:5]


def _merge_references(
    *groups: list[InvestigationReference],
) -> list[InvestigationReference]:
    seen: set[str] = set()
    merged: list[InvestigationReference] = []
    for group in groups:
        for ref in group:
            key = ref.url or ref.id
            if key in seen:
                continue
            seen.add(key)
            merged.append(ref)
    return merged


def _employee_interaction_counts(
    db: Session,
    tenant_id: uuid.UUID,
    component_ids: set[str],
) -> dict[str, tuple[int, int]]:
    """Return per-employee (slack_interactions, notion_interactions)."""
    slack_counts: dict[str, int] = {}
    notion_counts: dict[str, int] = {}

    if component_ids:
        notion_rows = (
            db.query(NotionDocSnapshot)
            .filter(
                NotionDocSnapshot.tenant_id == tenant_id,
                NotionDocSnapshot.component_id.in_(component_ids),
            )
            .all()
        )
        for row in notion_rows:
            if row.owner_employee_id:
                notion_counts[row.owner_employee_id] = (
                    notion_counts.get(row.owner_employee_id, 0) + 1
                )

    for thread in get_cached_slack_threads():
        for message in thread.messages:
            if message.is_bot or not message.user_id:
                continue
            employee_id = resolve_author_employee_id(
                db,
                tenant_id,
                "slack",
                message.user_id,
            )
            if employee_id:
                slack_counts[employee_id] = slack_counts.get(employee_id, 0) + 1

    return {
        employee_id: (
            slack_counts.get(employee_id, 0),
            notion_counts.get(employee_id, 0),
        )
        for employee_id in set(slack_counts) | set(notion_counts)
    }


def _load_graph_context(
    db: Session,
    tenant_id: uuid.UUID,
    incident_id: str | None,
    *,
    incident: IncidentSummary | None = None,
) -> _GraphContext:
    ctx = _GraphContext()
    ctx.components = (
        db.query(Component).filter(Component.tenant_id == tenant_id).all()
    )
    ctx.employees = (
        db.query(Employee)
        .options(joinedload(Employee.assignments))
        .filter(Employee.tenant_id == tenant_id)
        .all()
    )
    ctx.assignments = (
        db.query(Assignment).filter(Assignment.tenant_id == tenant_id).all()
    )
    if incident:
        ctx.incident = incident
    elif incident_id:
        ctx.incident = get_incident_by_id(db, tenant_id, incident_id)
    return ctx


def _score_employee(
    employee: Employee,
    message: str,
    corpus: str,
    component_ids: set[str],
    *,
    slack_interactions: int = 0,
    notion_interactions: int = 0,
    vector_similarity: float = 0.0,
) -> float:
    score = vector_similarity * 0.35
    name_lower = employee.name.lower()
    if name_lower in corpus or name_lower in message.lower():
        score += 25.0
    owned = {a.component_id for a in employee.assignments}
    overlap = len(owned & component_ids)
    score += min(30.0, overlap * 15.0)
    for assignment in employee.assignments:
        if assignment.component_id in component_ids:
            score += min(20.0, assignment.codebase_share_pct / 5)
    score += min(24.0, slack_interactions * 4.0)
    score += min(20.0, notion_interactions * 5.0)
    if employee.role.lower() in ("engineer", "manager", "lead"):
        score += 5.0
    return min(100.0, round(score, 1))


def _match_components(
    components: list[Component],
    message: str,
    corpus: str,
) -> list[Component]:
    matched: list[Component] = []
    combined = f"{message} {corpus}".lower()
    for component in components:
        if component.name.lower() in combined:
            matched.append(component)
    if not matched and components:
        for component in components:
            tokens = component.name.lower().split()
            if any(token in combined for token in tokens if len(token) > 3):
                matched.append(component)
    return matched[:4]


def _build_references_from_hits(
    hits: list[_GraphSearchHit],
    *,
    jira_id: str | None,
) -> tuple[
    list[InvestigationReference],
    list[InvestigationReference],
    list[InvestigationReference],
    list[InvestigationReference],
]:
    slack: list[InvestigationReference] = []
    jira: list[InvestigationReference] = []
    notion: list[InvestigationReference] = []
    postmortems: list[InvestigationReference] = []
    seen: set[str] = set()

    def add_ref(
        text: str,
        *,
        forced_type: str | None = None,
        url_override: str | None = None,
        title_override: str | None = None,
        ref_id: str | None = None,
    ) -> None:
        snippet = text.strip()[:240]
        if len(snippet) < 12 and not url_override:
            return
        key = (url_override or ref_id or snippet[:80]).lower()
        if key in seen:
            return
        seen.add(key)
        ref_type = forced_type or _reference_type(text)
        ref = InvestigationReference(
            id=ref_id or f"ref-{len(seen)}",
            type=ref_type,  # type: ignore[arg-type]
            title=title_override or _reference_title(text, ref_type),
            url=url_override or _reference_url(text, ref_type),
            snippet=snippet or title_override or ref_type,
        )
        if ref_type == "slack":
            slack.append(ref)
        elif ref_type == "jira":
            jira.append(ref)
        elif ref_type == "postmortem":
            postmortems.append(ref)
        else:
            notion.append(ref)

    for hit in hits:
        if hit.slack_thread_id:
            channel, _, ts = hit.slack_thread_id.partition(":")
            add_ref(
                hit.text,
                forced_type="slack",
                url_override=f"slack://{channel}/{ts}" if ts else f"slack://{channel}",
                title_override=_reference_title(hit.text, "slack"),
                ref_id=f"slack-{hit.slack_thread_id}",
            )
            continue
        if hit.notion_page_id:
            url = _reference_url(hit.text, "notion")
            if url == "notion://page":
                url = f"notion://{hit.notion_page_id}"
            add_ref(
                hit.text,
                forced_type="notion",
                url_override=url,
                ref_id=f"notion-{hit.notion_page_id}",
            )
            continue
        if hit.jira_key:
            add_ref(
                hit.text,
                forced_type="jira",
                url_override=f"jira://{hit.jira_key}",
                title_override=f"Jira {hit.jira_key}",
                ref_id=f"jira-{hit.jira_key}",
            )
            continue
        add_ref(hit.text)

    if jira_id:
        add_ref(
            f"Jira ticket {jira_id} linked to active incident investigation.",
            forced_type="jira",
            url_override=f"jira://{jira_id}",
            title_override=f"Jira {jira_id}",
            ref_id=f"jira-{jira_id}",
        )

    return slack, jira, notion, postmortems


def _build_references_from_search(
    search_texts: list[str],
    *,
    jira_id: str | None,
) -> tuple[
    list[InvestigationReference],
    list[InvestigationReference],
    list[InvestigationReference],
    list[InvestigationReference],
]:
    slack: list[InvestigationReference] = []
    jira: list[InvestigationReference] = []
    notion: list[InvestigationReference] = []
    postmortems: list[InvestigationReference] = []
    seen: set[str] = set()

    def add_ref(text: str, forced_type: str | None = None) -> None:
        snippet = text.strip()[:240]
        if len(snippet) < 20:
            return
        key = snippet[:80].lower()
        if key in seen:
            return
        seen.add(key)
        ref_type = forced_type or _reference_type(text)
        ref = InvestigationReference(
            id=f"ref-{len(seen)}",
            type=ref_type,  # type: ignore[arg-type]
            title=_reference_title(text, ref_type),
            url=_reference_url(text, ref_type),
            snippet=snippet,
        )
        if ref_type == "slack":
            slack.append(ref)
        elif ref_type == "jira":
            jira.append(ref)
        elif ref_type == "postmortem":
            postmortems.append(ref)
        else:
            notion.append(ref)

    for text in search_texts:
        add_ref(text)

    if jira_id:
        add_ref(
            f"Jira ticket {jira_id} linked to active incident investigation.",
            forced_type="jira",
        )

    return slack, jira, notion, postmortems


def _root_cause_from_live_incident(
    incident: IncidentSummary | None,
    db: Session,
    tenant_id: uuid.UUID,
) -> str | None:
    """Last-resort context when the Cognee graph returned no evidence nodes."""
    if not incident:
        return None

    if incident.jira_id:
        issue = _lookup_jira_issue(incident.jira_id, db, tenant_id)
        if issue:
            parts = [f"{issue.issue_key}: {issue.summary or incident.title}"]
            if issue.status:
                parts.append(f"Status {issue.status}")
            if issue.priority:
                parts.append(f"Priority {issue.priority}")
            return " · ".join(parts)[:400]

    if incident.source == "slack":
        thread = _lookup_slack_thread(incident.id)
        if thread and thread.parent_text.strip():
            return thread.parent_text.strip()[:400]

    if incident.title:
        return (
            f"{incident.title} — active incident in {incident.system_scope} scope."
        )[:400]
    return None


def _synthesize_root_cause(
    search_texts: list[str],
    incident: IncidentSummary | None,
    components: list[Component],
) -> str | None:
    prioritized = _prioritize_search_texts(search_texts, incident)
    for text in prioritized:
        if _text_has_hints(text, _ROOT_CAUSE_HINTS):
            sentence = text.split(".")[0].strip()
            if _is_displayable_evidence_text(sentence, incident):
                return sentence[:400]
    for text in prioritized:
        stripped = text.strip()
        if _is_displayable_evidence_text(stripped, incident):
            return stripped.split(".")[0].strip()[:400]
    if incident:
        return (
            f"Limited analysis available for {incident.system_scope}. "
            f"Review linked Jira and Slack context for \"{incident.title}\"."
        )[:400]
    if components:
        names = ", ".join(c.name for c in components[:2])
        return f"Related component scope: {names}."
    return None


def _synthesize_workaround(
    search_texts: list[str],
    incident: IncidentSummary | None = None,
) -> str | None:
    prioritized = _prioritize_search_texts(search_texts, incident)
    for text in prioritized:
        if _text_has_hints(text, _SOLUTION_HINTS):
            for sentence in text.split("."):
                stripped = sentence.strip()
                if (
                    _text_has_hints(stripped, _SOLUTION_HINTS)
                    and _is_displayable_evidence_text(stripped, incident)
                ):
                    return stripped[:400]
    for text in prioritized:
        lowered = text.lower()
        if ("runbook" in lowered or "playbook" in lowered) and not _is_metadata_only_reference(
            text
        ):
            sentence = text.split(".")[0].strip()
            if _is_displayable_evidence_text(sentence, incident):
                return sentence[:400]
    return None


def _compute_confidence(
    hits: list[_GraphSearchHit],
    graph_hops: list[_GraphHop],
    sme_count: int,
) -> float:
    edge_weights = {
        "BLOCKS": 6.0,
        "DISCUSSED_IN": 5.0,
        "OWNED_BY": 4.0,
        "ASSIGNED_TO": 4.0,
        "RESOLVED_BY": 3.0,
        "TRIGGERS": 5.0,
    }
    hop_bonus = sum(edge_weights.get(hop.edge, 2.0) for hop in graph_hops)
    hop_bonus = min(22.0, hop_bonus)

    if hits:
        avg_similarity = sum(hit.similarity for hit in hits) / len(hits)
        sme_bonus = min(12.0, sme_count * 3.0)
        return min(97.0, round(avg_similarity * 0.7 + hop_bonus + sme_bonus, 1))

    base = min(30.0, len(graph_hops) * 6.0)
    base += min(20.0, sme_count * 5.0)
    return min(55.0, round(max(base, 18.0), 1))


def _build_graph_hops(
    incident: IncidentSummary | None,
    matched_components: list[Component],
    matched_employees: list[tuple[Employee, float]],
    hits: list[_GraphSearchHit],
    *,
    jira_id: str | None,
    jira_tickets: list[InvestigationReference],
    slack_threads: list[InvestigationReference],
    operational_smes: list[SmeRecommendation],
) -> list[_GraphHop]:
    hops: list[GraphHop] = []
    seen: set[tuple[str, str, str]] = set()

    def add(from_node: str, edge: str, to_node: str) -> None:
        key = (from_node, edge, to_node)
        if key in seen:
            return
        seen.add(key)
        hops.append(_make_graph_hop(from_node, edge, to_node))

    component_names = [component.name for component in matched_components]
    for hit in hits:
        if hit.component_name and hit.component_name not in component_names:
            component_names.append(hit.component_name)
    if not component_names and incident:
        component_names.append(incident.system_scope)

    primary_component = (
        f"{component_names[0]} Component" if component_names else "System Component"
    )

    if jira_id:
        add(f"Jira {jira_id}", "BLOCKS", primary_component)

    for hit in hits:
        if hit.jira_key and hit.component_name:
            add(
                f"Jira {hit.jira_key}",
                "BLOCKS",
                f"{hit.component_name} Component",
            )
        elif hit.jira_key:
            add(f"Jira {hit.jira_key}", "BLOCKS", primary_component)

        if hit.component_name and _is_slack_hit(hit):
            add(
                f"{hit.component_name} Component",
                "DISCUSSED_IN",
                _extract_slack_channel_label(hit.text, incident),
            )
        elif _is_slack_hit(hit):
            add(
                primary_component,
                "DISCUSSED_IN",
                _extract_slack_channel_label(hit.text, incident),
            )

        if hit.component_name and hit.employee_name:
            add(
                f"{hit.component_name} Component",
                "OWNED_BY",
                hit.employee_name,
            )

    for ticket in jira_tickets[:2]:
        label = ticket.title if ticket.title else ticket.id
        if "jira" in ticket.type:
            add(label, "BLOCKS", primary_component)

    for thread in slack_threads[:2]:
        add(primary_component, "DISCUSSED_IN", thread.title[:80])

    matched_by_name = {component.name.lower(): component for component in matched_components}
    for component_name in component_names[:2]:
        component = matched_by_name.get(component_name.lower())
        if component:
            for employee, _ in matched_employees:
                if any(a.component_id == component.id for a in employee.assignments):
                    add(f"{component_name} Component", "OWNED_BY", employee.name)

    for sme in operational_smes[:2]:
        add(primary_component, "ASSIGNED_TO", sme.name)

    if incident and not hops:
        add(incident.title, "TRIGGERS", primary_component)

    return hops[:10]


def _build_search_query(
    message: str,
    incident: IncidentSummary | None,
) -> str:
    query_parts = [message]
    if incident:
        query_parts.insert(0, incident.id)
        query_parts.append(incident.title)
        query_parts.append(incident.system_scope)
        if incident.jira_id:
            query_parts.append(incident.jira_id)
        if incident.channel_name:
            query_parts.append(incident.channel_name)
    return " incident root cause workaround postmortem ".join(query_parts)


async def _search_incident_graph_fusion(
    queries: list[str],
    tenant_id: uuid.UUID,
    *,
    timeout_seconds: float = 15.0,
) -> list[Any]:
    if not queries:
        return []

    async def _run_all() -> list[Any]:
        batches = await asyncio.gather(
            *[
                _search_incident_graph(query, tenant_id, timeout_seconds=timeout_seconds)
                for query in queries
            ]
        )
        merged: list[Any] = []
        seen_texts: set[str] = set()
        for batch in batches:
            for item in batch:
                text = _extract_search_text(item)
                key = text[:120].lower()
                if not text or key in seen_texts:
                    continue
                seen_texts.add(key)
                merged.append(item)
        return merged

    try:
        return await asyncio.wait_for(_run_all(), timeout=timeout_seconds + 2)
    except (asyncio.TimeoutError, Exception):
        if len(queries) == 1:
            return await _search_incident_graph(
                queries[0], tenant_id, timeout_seconds=timeout_seconds
            )
        return []


def _fusion_search_queries(
    message: str,
    incident: IncidentSummary | None,
) -> list[str]:
    queries = [_build_search_query(message, incident)]
    if not incident:
        return queries

    scope = incident.system_scope
    if incident.jira_id:
        queries.append(
            f"{incident.jira_id} jira blocks {scope} component failure root cause why outage"
        )
    channel = (incident.channel_name or incident.system_scope or "").lstrip("#")
    queries.append(
        f"slack incident thread #{channel} {incident.title} "
        f"workaround solution mitigation fix resolve recovery runbook"
    )
    return queries[:3]


async def _search_incident_graph(
    search_query: str,
    tenant_id: uuid.UUID,
    *,
    timeout_seconds: float = 15.0,
) -> list[Any]:
    import cognee
    from cognee.modules.search.types.SearchType import SearchType

    dataset = tenant_dataset_name(tenant_id)

    async def _run_search() -> list[Any]:
        async with tenant_cognee_context(tenant_id):
            try:
                results = await cognee.search(
                    search_query,
                    query_type=SearchType.CHUNKS,
                    datasets=[dataset],
                    top_k=12,
                    include_references=True,
                )
            except TypeError:
                results = await cognee.search(
                    search_query,
                    datasets=[dataset],
                    top_k=12,
                )
            return results if isinstance(results, list) else list(results or [])

    try:
        return await asyncio.wait_for(_run_search(), timeout=timeout_seconds)
    except (asyncio.TimeoutError, Exception):
        return []


async def build_diagnostics(
    db: Session,
    tenant: Tenant,
    message: str,
    *,
    incident_id: str | None = None,
    incident: IncidentSummary | None = None,
    raw_results: list[Any] | None = None,
) -> InvestigationDiagnostics:
    jira_id = _parse_jira_id(message)
    ctx = _load_graph_context(
        db,
        tenant.id,
        incident_id,
        incident=incident,
    )
    if not jira_id and ctx.incident and ctx.incident.jira_id:
        jira_id = ctx.incident.jira_id

    if raw_results is None:
        fusion_queries = _fusion_search_queries(message, ctx.incident)
        raw_results = await _search_incident_graph_fusion(
            fusion_queries,
            tenant.id,
        )

    ctx.search_hits = _rank_search_hits_for_incident(
        _parse_graph_search_hits(raw_results),
        ctx.incident,
    )
    ctx.search_texts = [hit.text for hit in ctx.search_hits]
    corpus = " ".join(ctx.search_texts).lower()

    ctx.matched_components = _match_components(ctx.components, message, corpus)
    if not ctx.matched_components and ctx.incident:
        ctx.matched_components = _match_components(
            ctx.components,
            ctx.incident.system_scope,
            ctx.incident.system_scope.lower(),
        )

    component_ids = {c.id for c in ctx.matched_components}
    interaction_counts = _employee_interaction_counts(
        db,
        tenant.id,
        component_ids,
    )
    hit_similarity_by_employee: dict[str, float] = {}
    for hit in ctx.search_hits:
        if not hit.employee_name:
            continue
        for employee in ctx.employees:
            if employee.name.lower() == hit.employee_name.lower():
                prior = hit_similarity_by_employee.get(employee.id, 0.0)
                hit_similarity_by_employee[employee.id] = max(prior, hit.similarity)

    score_floor = 12.0 if not ctx.search_hits else 20.0
    employee_scores: list[tuple[Employee, float]] = []
    for employee in ctx.employees:
        slack_count, notion_count = interaction_counts.get(employee.id, (0, 0))
        score = _score_employee(
            employee,
            message,
            corpus,
            component_ids,
            slack_interactions=slack_count,
            notion_interactions=notion_count,
            vector_similarity=hit_similarity_by_employee.get(employee.id, 0.0),
        )
        if score >= score_floor:
            employee_scores.append((employee, score))
    employee_scores.sort(key=lambda item: item[1], reverse=True)
    ctx.matched_employees = employee_scores[:5]

    operational_smes, op_slack, op_jira, op_notion = _operational_context_for_incident(
        db,
        tenant.id,
        ctx.incident,
        ctx.employees,
        ctx.components,
    )

    ctx.slack_threads, ctx.jira_tickets, ctx.notion_pages, ctx.postmortems = (
        _build_references_from_hits(ctx.search_hits, jira_id=jira_id)
    )
    ctx.slack_threads = _merge_references(ctx.slack_threads, op_slack)
    ctx.jira_tickets = _merge_references(ctx.jira_tickets, op_jira)
    ctx.notion_pages = _merge_references(ctx.notion_pages, op_notion)

    ctx.graph_hops = _build_graph_hops(
        ctx.incident,
        ctx.matched_components,
        ctx.matched_employees,
        ctx.search_hits,
        jira_id=jira_id,
        jira_tickets=ctx.jira_tickets,
        slack_threads=ctx.slack_threads,
        operational_smes=operational_smes,
    )

    platform_root, platform_workaround = _extract_slack_jira_diagnostics(
        ctx.search_hits,
        ctx.incident,
    )

    cognee_narrative = await _fetch_cognee_root_cause_narrative(
        ctx.incident,
        tenant.id,
    )
    graph_root = _analyze_root_cause_from_graph(
        ctx.search_hits,
        ctx.incident,
        ctx.matched_components,
    )

    graph_smes = [
        SmeRecommendation(
            employee_id=employee.id,
            name=employee.name,
            role=employee.role,
            compatibility_score=score,
            status=_presence_for_score(score),  # type: ignore[arg-type]
        )
        for employee, score in ctx.matched_employees
    ]
    smes = _merge_sme_recommendations(graph_smes, operational_smes)

    flat_references = (
        ctx.slack_threads + ctx.jira_tickets + ctx.notion_pages + ctx.postmortems
    )

    live_root = (
        _root_cause_from_live_incident(ctx.incident, db, tenant.id)
        if not ctx.search_hits
        else None
    )

    workaround_text, workaround_available = await _resolve_workaround(
        hits=ctx.search_hits,
        search_texts=ctx.search_texts,
        incident=ctx.incident,
        tenant_id=tenant.id,
        platform_workaround=platform_workaround,
    )

    return InvestigationDiagnostics(
        probable_root_cause=(
            _pick_first_displayable(
                ctx.incident,
                graph_root,
                cognee_narrative,
                platform_root,
                _synthesize_root_cause(
                    ctx.search_texts, ctx.incident, ctx.matched_components
                ),
                live_root,
            )
            or (
                "Not enough incident context yet. Sync integrations from "
                "Settings, then refresh this briefing."
            )
        ),
        confidence_score=_compute_confidence(
            ctx.search_hits, ctx.graph_hops, len(smes)
        ),
        workaround=workaround_text,
        workaround_available=workaround_available,
        smes=smes,
        references=flat_references,
        slack_threads=ctx.slack_threads,
        jira_tickets=ctx.jira_tickets,
        notion_pages=ctx.notion_pages + ctx.postmortems,
    )


def _briefing_query_for_incident(incident: IncidentSummary) -> str:
    parts = [_BRIEFING_QUERY, incident.title, incident.system_scope]
    if incident.jira_id:
        parts.append(incident.jira_id)
    if incident.channel_name:
        parts.append(incident.channel_name)
    return " ".join(parts)


def _compose_chat_answer(
    message: str,
    diagnostics: InvestigationDiagnostics,
    search_hits: list[_GraphSearchHit],
) -> str:
    lowered = message.lower()
    sections: list[str] = []

    if search_hits:
        evidence_lines = [
            f"- {hit.text[:220]} (graph match {hit.similarity:.0f}%)"
            for hit in search_hits[:3]
        ]
        sections.append("**Graph evidence:**\n" + "\n".join(evidence_lines))

    if any(
        hint in lowered
        for hint in ("root cause", "why", "cause", "happening", "what is wrong")
    ):
        sections.append(f"**Root cause:** {diagnostics.probable_root_cause}")
    if any(
        hint in lowered
        for hint in ("workaround", "mitigation", "fix", "resolve", "emergency")
    ):
        sections.append(f"**Workaround:** {diagnostics.workaround}")
    if any(
        hint in lowered
        for hint in ("who", "own", "sme", "expert", "page", "escalat")
    ):
        if diagnostics.smes:
            experts = ", ".join(
                f"{sme.name} ({sme.compatibility_score:.0f}%)"
                for sme in diagnostics.smes[:3]
            )
            sections.append(f"**Recommended experts:** {experts}")
        else:
            sections.append(
                "**Recommended experts:** No strong owner match in the org graph yet."
            )
    if any(hint in lowered for hint in ("summar", "impact", "status", "update")):
        sections.append(f"**Impact summary:** {diagnostics.probable_root_cause}")

    if not sections:
        if search_hits:
            sections.append(
                "**Analysis:** "
                + search_hits[0].text[:360]
            )
        else:
            sections.append(f"**Analysis:** {diagnostics.probable_root_cause}")
        if diagnostics.workaround:
            sections.append(f"**Suggested workaround:** {diagnostics.workaround}")

    if diagnostics.references:
        sections.append(
            f"Found {len(diagnostics.references)} related references in the knowledge graph."
        )

    return "\n\n".join(sections)


async def stream_incident_briefing(
    incident: IncidentSummary,
    tenant: Tenant,
    db: Session,
):
    cache_key = (str(tenant.id), incident.id)
    cached = _briefing_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < _BRIEFING_CACHE_TTL_SECONDS:
        yield _status_event(
            "summarizing",
            f"Loaded cached briefing for {incident.title}…",
        )
        diag_chunk = {
            "type": "diagnostics",
            "diagnostics": _diagnostics_to_json(cached[1]),
        }
        yield f"data: {json.dumps(diag_chunk)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    message = _briefing_query_for_incident(incident)

    try:
        yield _status_event(
            "searching",
            f"Loading context for {incident.title}…",
        )

        yield _status_event(
            "matching",
            "Matching components, owners, and related references…",
        )
        diagnostics = await build_diagnostics(
            db,
            tenant,
            message,
            incident_id=incident.id,
            incident=incident,
        )

        _briefing_cache[cache_key] = (time.time(), diagnostics)

        yield _status_event("summarizing", "Preparing incident briefing…")

        diag_chunk = {
            "type": "diagnostics",
            "diagnostics": _diagnostics_to_json(diagnostics),
        }
        yield f"data: {json.dumps(diag_chunk)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"


async def stream_investigation_chat(
    payload: InvestigationChatRequest,
    tenant: Tenant,
    db: Session,
):
    ctx = _load_graph_context(db, tenant.id, payload.incident_id)
    search_query = _build_search_query(payload.message, ctx.incident)

    yield _status_event(
        "searching",
        "Searching tenant knowledge graph for incident context…",
    )
    raw_results = await _search_incident_graph(search_query, tenant.id)
    search_hits = _parse_graph_search_hits(raw_results)

    yield _status_event(
        "matching",
        "Matching components, owners, and related references…",
    )
    diagnostics = await build_diagnostics(
        db,
        tenant,
        payload.message,
        incident_id=payload.incident_id,
        incident=ctx.incident,
        raw_results=raw_results,
    )

    yield _status_event("summarizing", "Preparing graph-grounded answer…")

    answer = _compose_chat_answer(payload.message, diagnostics, search_hits)

    for token in answer.split(" "):
        chunk = {"type": "token", "content": token + " "}
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.02)

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def _status_event(phase: str, message: str) -> str:
    return f"data: {json.dumps({'type': 'status', 'phase': phase, 'message': message})}\n\n"
