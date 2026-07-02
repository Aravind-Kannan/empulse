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

from app.models.operational import Assignment, Component, Employee, IncidentRecord
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
from app.services.tenant_cognee import tenant_graph_search, tenant_write_memory_record

_BRIEFING_CACHE_TTL_SECONDS = 300.0
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


@dataclass
class _GraphContext:
    search_texts: list[str] = field(default_factory=list)
    components: list[Component] = field(default_factory=list)
    employees: list[Employee] = field(default_factory=list)
    assignments: list[Assignment] = field(default_factory=list)
    incident: IncidentSummary | None = None
    matched_components: list[Component] = field(default_factory=list)
    matched_employees: list[tuple[Employee, float]] = field(default_factory=list)
    graph_hops: list[str] = field(default_factory=list)
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
    try:
        await tenant_write_memory_record(tenant_id, record)
    except Exception:
        pass


def _parse_jira_id(message: str) -> str | None:
    match = _JIRA_PATTERN.search(message)
    return match.group(0) if match else None


def _extract_search_text(item: Any) -> str:
    if item is None:
        return ""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("text", "content", "page_content", "snippet", "answer", "result"):
            value = item.get(key)
            if value:
                return str(value).strip()
        return json.dumps(item)[:600]
    for attr in ("text", "content", "page_content", "snippet"):
        if hasattr(item, attr):
            value = getattr(item, attr)
            if value:
                return str(value).strip()
    return str(item)[:600]


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
    if score >= 85:
        return "online"
    if score >= 65:
        return "away"
    return "offline"


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
) -> float:
    score = 0.0
    name_lower = employee.name.lower()
    if name_lower in corpus or name_lower in message.lower():
        score += 35.0
    owned = {a.component_id for a in employee.assignments}
    overlap = len(owned & component_ids)
    score += min(40.0, overlap * 20.0)
    for assignment in employee.assignments:
        if assignment.component_id in component_ids:
            score += min(25.0, assignment.codebase_share_pct / 4)
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


def _synthesize_root_cause(
    search_texts: list[str],
    incident: IncidentSummary | None,
    components: list[Component],
) -> str:
    for text in search_texts:
        lowered = text.lower()
        if any(hint in lowered for hint in _ROOT_CAUSE_HINTS):
            sentence = text.split(".")[0].strip()
            if len(sentence) > 30:
                return sentence[:400]
    if incident:
        return (
            f"Evidence links {incident.system_scope} to "
            f"\"{incident.title}\""
            + (f" ({incident.jira_id})" if incident.jira_id else "")
            + "."
        )
    if components:
        names = ", ".join(c.name for c in components[:2])
        return f"Retrieved graph evidence points to component scope: {names}."
    return (
        "Not enough context yet. Connect integrations and run onboarding sync, "
        "then ask a question in chat."
    )


def _synthesize_workaround(search_texts: list[str]) -> str:
    for text in search_texts:
        lowered = text.lower()
        if any(hint in lowered for hint in _WORKAROUND_HINTS):
            for sentence in text.split("."):
                if any(hint in sentence.lower() for hint in _WORKAROUND_HINTS):
                    return sentence.strip()[:400]
    for text in search_texts:
        if "runbook" in text.lower() or "playbook" in text.lower():
            return text.split(".")[0].strip()[:400]
    return (
        "No explicit workaround found in graph memory. "
        "Escalate to component owners and check linked runbooks."
    )


def _compute_confidence(
    search_texts: list[str],
    graph_hops: list[str],
    sme_count: int,
) -> float:
    base = min(55.0, len(search_texts) * 8.0)
    base += min(25.0, max(0, len(graph_hops) - 1) * 6.0)
    base += min(20.0, sme_count * 5.0)
    if not search_texts:
        base = max(base, 18.0)
    return min(97.0, round(base, 1))


def _build_search_query(
    message: str,
    incident: IncidentSummary | None,
) -> str:
    query_parts = [message]
    if incident:
        query_parts.append(incident.title)
        query_parts.append(incident.system_scope)
        if incident.jira_id:
            query_parts.append(incident.jira_id)
    return " incident root cause workaround postmortem ".join(query_parts)


async def _search_incident_graph(
    search_query: str,
    tenant_id: uuid.UUID,
    *,
    timeout_seconds: float = 15.0,
) -> list[Any]:
    try:
        return await asyncio.wait_for(
            tenant_graph_search(search_query, tenant_id, top_k=12),
            timeout=timeout_seconds,
        )
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
        search_query = _build_search_query(message, ctx.incident)
        raw_results = await _search_incident_graph(search_query, tenant.id)

    ctx.search_texts = [
        text for text in (_extract_search_text(item) for item in raw_results) if text
    ]
    corpus = " ".join(ctx.search_texts).lower()

    ctx.matched_components = _match_components(ctx.components, message, corpus)
    if not ctx.matched_components and ctx.incident:
        ctx.matched_components = _match_components(
            ctx.components,
            ctx.incident.system_scope,
            ctx.incident.system_scope.lower(),
        )

    component_ids = {c.id for c in ctx.matched_components}
    score_floor = 12.0 if not ctx.search_texts else 20.0
    employee_scores: list[tuple[Employee, float]] = []
    for employee in ctx.employees:
        score = _score_employee(employee, message, corpus, component_ids)
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

    incident_label = (
        f"[{ctx.incident.title}]" if ctx.incident else "[Incident query]"
    )
    ctx.graph_hops = [incident_label]
    for component in ctx.matched_components:
        ctx.graph_hops.append(f"-> [{component.name} Component]")
        owners = [
            emp
            for emp, _ in ctx.matched_employees
            if any(a.component_id == component.id for a in emp.assignments)
        ]
        for owner in owners[:2]:
            ctx.graph_hops.append(f"-> [{owner.name} Owner]")
    if jira_id:
        ctx.graph_hops.append(f"-> [Jira {jira_id}]")
    for sme in operational_smes[:2]:
        ctx.graph_hops.append(f"-> [{sme.name} SME]")

    ctx.slack_threads, ctx.jira_tickets, ctx.notion_pages, ctx.postmortems = (
        _build_references_from_search(ctx.search_texts, jira_id=jira_id)
    )
    ctx.slack_threads = _merge_references(ctx.slack_threads, op_slack)
    ctx.jira_tickets = _merge_references(ctx.jira_tickets, op_jira)
    ctx.notion_pages = _merge_references(ctx.notion_pages, op_notion)

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

    return InvestigationDiagnostics(
        probable_root_cause=_synthesize_root_cause(
            ctx.search_texts, ctx.incident, ctx.matched_components
        ),
        confidence_score=_compute_confidence(
            ctx.search_texts, ctx.graph_hops, len(smes)
        ),
        workaround=_synthesize_workaround(ctx.search_texts),
        smes=smes,
        references=flat_references,
        slack_threads=ctx.slack_threads,
        jira_tickets=ctx.jira_tickets,
        notion_pages=ctx.notion_pages + ctx.postmortems,
        graph_hops=ctx.graph_hops,
    )


def _briefing_query_for_incident(incident: IncidentSummary) -> str:
    parts = [_BRIEFING_QUERY, incident.title, incident.system_scope]
    if incident.jira_id:
        parts.append(incident.jira_id)
    if incident.channel_name:
        parts.append(incident.channel_name)
    return " ".join(parts)


def _compose_chat_answer(message: str, diagnostics: InvestigationDiagnostics) -> str:
    lowered = message.lower()
    sections: list[str] = []

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
            "diagnostics": cached[1].model_dump(),
        }
        yield f"data: {json.dumps(diag_chunk)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    message = _briefing_query_for_incident(incident)
    search_query = _build_search_query(message, incident)

    try:
        yield _status_event(
            "searching",
            f"Loading context for {incident.title}…",
        )
        raw_results = await _search_incident_graph(search_query, tenant.id)

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
            raw_results=raw_results,
        )

        _briefing_cache[cache_key] = (time.time(), diagnostics)

        yield _status_event("summarizing", "Preparing incident briefing…")

        diag_chunk = {
            "type": "diagnostics",
            "diagnostics": diagnostics.model_dump(),
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
        "Searching knowledge graph for Slack threads, Jira tickets, and runbooks…",
    )
    raw_results = await _search_incident_graph(search_query, tenant.id)

    yield _status_event(
        "matching",
        "Matching components, owners, and related references…",
    )
    diagnostics = await build_diagnostics(
        db,
        tenant,
        payload.message,
        incident_id=payload.incident_id,
        raw_results=raw_results,
    )

    yield _status_event("summarizing", "Preparing answer…")

    answer = _compose_chat_answer(payload.message, diagnostics)

    for token in answer.split(" "):
        chunk = {"type": "token", "content": token + " "}
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.02)

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def _status_event(phase: str, message: str) -> str:
    return f"data: {json.dumps({'type': 'status', 'phase': phase, 'message': message})}\n\n"
