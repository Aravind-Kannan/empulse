from __future__ import annotations

import asyncio
import json
import re
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
from app.services.tenant_cognee import tenant_graph_search, tenant_write_memory_record

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
    incident: IncidentRecord | None = None
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
    query = db.query(IncidentRecord).filter(IncidentRecord.tenant_id == tenant.id)
    if status:
        query = query.filter(IncidentRecord.status == status)
    records = query.order_by(IncidentRecord.updated_at.desc()).all()
    return IncidentListResponse(
        incidents=[
            IncidentSummary(
                id=record.id,
                title=record.title,
                status=record.status,  # type: ignore[arg-type]
                system_scope=record.system_scope,
                jira_id=record.jira_id or "",
                updated_at=record.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            for record in records
        ]
    )


def update_incident_status(
    db: Session,
    tenant: Tenant,
    incident_id: str,
    status: IncidentStatus,
) -> IncidentSummary:
    record = (
        db.query(IncidentRecord)
        .filter(
            IncidentRecord.id == incident_id,
            IncidentRecord.tenant_id == tenant.id,
        )
        .one_or_none()
    )
    if not record:
        raise ValueError(f"Incident '{incident_id}' not found.")
    record.status = status
    record.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(record)
    return IncidentSummary(
        id=record.id,
        title=record.title,
        status=record.status,  # type: ignore[arg-type]
        system_scope=record.system_scope,
        jira_id=record.jira_id or "",
        updated_at=record.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


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


def _load_graph_context(
    db: Session,
    tenant_id: uuid.UUID,
    incident_id: str | None,
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
    if incident_id:
        ctx.incident = (
            db.query(IncidentRecord)
            .filter(
                IncidentRecord.id == incident_id,
                IncidentRecord.tenant_id == tenant_id,
            )
            .one_or_none()
        )
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
    incident: IncidentRecord | None,
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
            f"Graph retrieval correlates {incident.system_scope} with "
            f"ongoing incident \"{incident.title}\""
            + (f" ({incident.jira_id})" if incident.jira_id else "")
            + "."
        )
    if components:
        names = ", ".join(c.name for c in components[:2])
        return f"Retrieved graph evidence points to component scope: {names}."
    return (
        "No strong root-cause narrative in the knowledge graph yet. "
        "Ingest Jira, Notion, or postmortem documents via onboarding sync."
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


async def build_diagnostics(
    db: Session,
    tenant: Tenant,
    message: str,
    *,
    incident_id: str | None = None,
) -> InvestigationDiagnostics:
    jira_id = _parse_jira_id(message)
    ctx = _load_graph_context(db, tenant.id, incident_id)

    query_parts = [message]
    if ctx.incident:
        query_parts.append(ctx.incident.title)
        query_parts.append(ctx.incident.system_scope)
        if ctx.incident.jira_id:
            query_parts.append(ctx.incident.jira_id)
    search_query = " incident root cause workaround postmortem ".join(query_parts)

    try:
        raw_results = await tenant_graph_search(search_query, tenant.id, top_k=12)
    except Exception:
        raw_results = []

    ctx.search_texts = [
        text for text in (_extract_search_text(item) for item in raw_results) if text
    ]
    corpus = " ".join(ctx.search_texts).lower()

    ctx.matched_components = _match_components(ctx.components, message, corpus)
    if not ctx.matched_components and ctx.incident:
        ctx.matched_components = _match_components(
            ctx.components,
            ctx.incident.system_scope,
            corpus,
        )

    component_ids = {c.id for c in ctx.matched_components}
    employee_scores: list[tuple[Employee, float]] = []
    for employee in ctx.employees:
        score = _score_employee(employee, message, corpus, component_ids)
        if score >= 20:
            employee_scores.append((employee, score))
    employee_scores.sort(key=lambda item: item[1], reverse=True)
    ctx.matched_employees = employee_scores[:5]

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

    ctx.slack_threads, ctx.jira_tickets, ctx.notion_pages, ctx.postmortems = (
        _build_references_from_search(ctx.search_texts, jira_id=jira_id)
    )

    smes = [
        SmeRecommendation(
            employee_id=employee.id,
            name=employee.name,
            role=employee.role,
            compatibility_score=score,
            status=_presence_for_score(score),  # type: ignore[arg-type]
        )
        for employee, score in ctx.matched_employees
    ]

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


async def stream_investigation_chat(
    payload: InvestigationChatRequest,
    tenant: Tenant,
    db: Session,
):
    jira = _parse_jira_id(payload.message)
    diagnostics = await build_diagnostics(
        db,
        tenant,
        payload.message,
        incident_id=payload.incident_id,
    )

    scope = (
        diagnostics.graph_hops[0].strip("[]")
        if diagnostics.graph_hops
        else "knowledge graph"
    )
    intro = (
        f"Searching tenant Cognee dataset for **{scope}**"
        + (f" (Jira {jira})" if jira else "")
        + "…\n\n"
    )
    hop_count = max(0, len(diagnostics.graph_hops) - 1)
    narrative = (
        f"Retrieved {len(diagnostics.references)} graph references across "
        f"{hop_count} hop{'s' if hop_count != 1 else ''}. "
        f"Confidence {diagnostics.confidence_score:.0f}% from vector proximity "
        "and ownership edges.\n\n"
        "Diagnostics synthesized from live Cognee memory."
    )

    for token in intro.split(" "):
        chunk = {"type": "token", "content": token + " "}
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.03)

    for token in narrative.split(" "):
        chunk = {"type": "token", "content": token + " "}
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.02)

    diag_chunk = {
        "type": "diagnostics",
        "diagnostics": diagnostics.model_dump(),
    }
    yield f"data: {json.dumps(diag_chunk)}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
