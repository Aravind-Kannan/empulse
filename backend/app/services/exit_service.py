"""Cognee graph synthesis for employee exit handover documents."""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models.operational import Assignment, Component, Employee, EmployeeIdentity, NotionDocSnapshot
from app.schemas.era import EraAffectedComponent
from app.services.cognee_era_metrics import calculate_graph_contribution_share, total_component_count
from app.services.era.engine import score_employee
from app.services.era.metadata import build_affected_components
from app.services.era.normalize import build_tenant_percentiles
from app.services.era.signals_builder import build_signals_for_employee
from app.services.era_analytics import (
    _jira_connected,
    _merge_integration_evidence,
    _notion_connected,
    _slack_connected,
    get_jira_backlog_boost,
)
from app.services.github_file_risk import get_employee_hotspots
from app.services.integration_telemetry import (
    get_cached_jira_issues,
    get_cached_slack_threads,
    get_component_bus_factor,
    get_github_ownership,
    get_slack_employee_signals,
    has_github_sync,
    hydrate_integration_telemetry,
)
from app.services.role_utils import is_leadership_role
from app.services.tenant_cognee import tenant_cognee_context
from app.tenancy import tenant_dataset_name

logger = logging.getLogger(__name__)

_DOC_KINDS = frozenset({"runbook", "architecture", "playbook", "postmortem", "wiki"})
_TROUBLESHOOTING_HINTS = (
    "root cause",
    "investigat",
    "diagnos",
    "outage",
    "incident",
    "failed",
    "error",
    "timeout",
    "mitigat",
    "resolved",
    "sev",
)
_SOLE_OWNERSHIP_PCT = 85.0


@dataclass
class HandoverCompilation:
    employee_name: str
    component_lines: list[str] = field(default_factory=list)
    knowledge_risk_lines: list[str] = field(default_factory=list)
    jira_lines: list[str] = field(default_factory=list)
    incident_lines: list[str] = field(default_factory=list)
    slack_lines: list[str] = field(default_factory=list)
    gap_lines: list[str] = field(default_factory=list)
    graph_insight_lines: list[str] = field(default_factory=list)
    risk_summary_lines: list[str] = field(default_factory=list)


def _extract_search_text(item: Any) -> str:
    if item is None:
        return ""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("text", "content", "chunk", "summary", "answer"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return str(item).strip()
    for attr in ("text", "content", "chunk", "summary"):
        value = getattr(item, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(item).strip()


async def _cognee_handover_search(
    tenant_id: uuid.UUID,
    query: str,
    *,
    top_k: int = 8,
) -> list[str]:
    import cognee
    from cognee.modules.search.types.SearchType import SearchType

    dataset = tenant_dataset_name(tenant_id)
    texts: list[str] = []

    async def _run() -> list[Any]:
        async with tenant_cognee_context(tenant_id):
            try:
                results = await cognee.search(
                    query,
                    query_type=SearchType.CHUNKS,
                    datasets=[dataset],
                    top_k=top_k,
                    include_references=True,
                )
            except TypeError:
                results = await cognee.search(
                    query,
                    datasets=[dataset],
                    top_k=top_k,
                )
            return results if isinstance(results, list) else list(results or [])

    try:
        raw = await asyncio.wait_for(_run(), timeout=18.0)
    except Exception as exc:
        logger.warning("exit handover cognee search failed tenant=%s: %s", tenant_id, exc)
        return texts

    seen: set[str] = set()
    for item in raw:
        text = _extract_search_text(item)
        normalized = re.sub(r"\s+", " ", text).strip()
        if len(normalized) < 40 or normalized in seen:
            continue
        seen.add(normalized)
        texts.append(normalized[:500])
    return texts


async def _cognee_handover_research(
    tenant_id: uuid.UUID,
    employee: Employee,
    owned_names: list[str],
) -> dict[str, list[str]]:
    """Targeted multi-query graph retrieval — one query per handover facet."""
    name = employee.name
    components_clause = ", ".join(owned_names[:8]) or "engineering systems"
    queries = {
        "knowledge": (
            f"Sole owner SPOF bus factor tacit knowledge risk for {name} "
            f"on components: {components_clause}"
        ),
        "incidents": (
            f"Open incidents outages production failures troubleshooting threads "
            f"involving {name} on {components_clause}"
        ),
        "operations": (
            f"Jira tickets tasks backlog assigned to {name} for {components_clause}"
        ),
        "documentation": (
            f"Missing runbooks architecture postmortems documentation gaps "
            f"for {name} owned components {components_clause}"
        ),
        "blast_radius": (
            f"What systems and downstream services depend on {name}'s owned "
            f"components ({components_clause})?"
        ),
    }

    keys = list(queries.keys())
    results = await asyncio.gather(
        *[
            _cognee_handover_search(tenant_id, queries[key], top_k=8)
            for key in keys
        ],
        return_exceptions=True,
    )

    buckets: dict[str, list[str]] = {key: [] for key in keys}
    for key, result in zip(keys, results, strict=True):
        if isinstance(result, Exception):
            logger.warning(
                "exit handover cognee bucket %s failed tenant=%s: %s",
                key,
                tenant_id,
                result,
            )
            continue
        buckets[key] = result
    return buckets


def _provider_user_ids(
    db: Session,
    tenant_id: uuid.UUID,
    employee_id: str,
    provider: str,
) -> set[str]:
    rows = (
        db.query(EmployeeIdentity.provider_username_or_id)
        .filter(
            EmployeeIdentity.tenant_id == tenant_id,
            EmployeeIdentity.employee_id == employee_id,
            EmployeeIdentity.provider == provider,
        )
        .all()
    )
    return {str(row[0]) for row in rows if row[0]}


def _load_employee(db: Session, tenant_id: uuid.UUID, employee_id: str) -> Employee:
    employee = (
        db.query(Employee)
        .options(joinedload(Employee.assignments).joinedload(Assignment.component))
        .filter(Employee.id == employee_id, Employee.tenant_id == tenant_id)
        .first()
    )
    if not employee:
        raise ValueError(f"Employee '{employee_id}' not found.")
    return employee


def _integration_flags(db: Session, tenant_id: uuid.UUID) -> tuple[bool, bool, bool, bool]:
    from app.services.integration_telemetry import has_github_sync

    return (
        has_github_sync(),
        _jira_connected(db, tenant_id),
        _notion_connected(db, tenant_id),
        _slack_connected(db, tenant_id),
    )


def _handover_risk_bundle(
    db: Session,
    tenant_id: uuid.UUID,
    employee: Employee,
) -> tuple[list[dict], list[EraAffectedComponent], float, str | None]:
    """ERA scoring + merged evidence without async Cognee intelligence."""
    if is_leadership_role(employee.role):
        return [], [], 0.0, None

    github_connected, jira_connected, notion_connected, slack_connected = (
        _integration_flags(db, tenant_id)
    )
    total_components = total_component_count(
        db.query(Component).filter(Component.tenant_id == tenant_id).all()
    )
    all_employees = (
        db.query(Employee)
        .filter(Employee.tenant_id == tenant_id)
        .options(joinedload(Employee.assignments).joinedload(Assignment.component))
        .all()
    )
    jira_boost = get_jira_backlog_boost(employee.id)
    codebase_share_pct = calculate_graph_contribution_share(
        employee_id=employee.id,
        assignments=employee.assignments,
        total_components=total_components,
        jira_backlog_boost=jira_boost,
    )

    signals = build_signals_for_employee(
        employee,
        all_employees=all_employees,
        total_components=total_components,
        codebase_share_pct=codebase_share_pct,
        jira_backlog_boost=jira_boost,
        github_connected=github_connected,
        jira_connected=jira_connected,
        notion_connected=notion_connected,
        slack_connected=slack_connected,
    )
    peer_signals = []
    for peer in all_employees:
        if is_leadership_role(peer.role) or peer.id == employee.id:
            continue
        peer_signals.append(
            build_signals_for_employee(
                peer,
                all_employees=all_employees,
                total_components=total_components,
                codebase_share_pct=calculate_graph_contribution_share(
                    employee_id=peer.id,
                    assignments=peer.assignments,
                    total_components=total_components,
                    jira_backlog_boost=get_jira_backlog_boost(peer.id),
                ),
                jira_backlog_boost=get_jira_backlog_boost(peer.id),
                github_connected=github_connected,
                jira_connected=jira_connected,
                notion_connected=notion_connected,
                slack_connected=slack_connected,
            )
        )
    tenant_stats = build_tenant_percentiles([signals, *peer_signals])
    score_result = score_employee(signals, tenant_stats, evidence_limit=1000)
    component_names = {
        assignment.component.id: assignment.component.name
        for assignment in employee.assignments
    }
    evidence = _merge_integration_evidence(
        db,
        tenant_id,
        signals.employee_id,
        signals.name,
        score_result.all_evidence,
        component_names=component_names,
        github_connected=github_connected,
        jira_connected=jira_connected,
        notion_connected=notion_connected,
        slack_connected=slack_connected,
        limit=1000,
    )
    affected = build_affected_components(employee, github_connected=github_connected)
    risk_level = score_result.risk_level if not score_result.excluded else None
    return evidence, affected, score_result.composite, risk_level


def _compile_risk_summary(
    composite: float,
    risk_level: str | None,
    evidence: list[dict],
) -> list[str]:
    if not evidence and composite <= 0:
        return []
    lines: list[str] = []
    if composite > 0 and risk_level:
        lines.append(
            f"- Composite departure risk **{composite:.0f}%** ({risk_level}) "
            "from ownership, operational backlog, and documentation signals."
        )
    knowledge_items = [
        item
        for item in evidence
        if item.get("dimension") in {"knowledge", "structural", "documentation"}
    ]
    for item in sorted(
        knowledge_items,
        key=lambda row: row.get("impact_points", 0),
        reverse=True,
    )[:5]:
        lines.append(
            f"- **{item.get('title', 'Risk signal')}** "
            f"({item.get('dimension')}, {item.get('severity', 'medium')}) — "
            f"{item.get('description', '')}"
        )
    return lines


def _compile_explicit_ownership(
    employee: Employee,
    affected: list[EraAffectedComponent],
) -> list[str]:
    spof_ids = {component.id for component in affected if component.spof}
    lines: list[str] = []
    for assignment in sorted(
        employee.assignments,
        key=lambda row: row.codebase_share_pct,
        reverse=True,
    ):
        component = assignment.component
        spof_note = " · **SPOF**" if component.id in spof_ids else ""
        lines.append(
            f"- **{component.name}** — {assignment.codebase_share_pct:.0f}% codebase "
            f"share · {component.criticality} · {component.open_tasks_count} open tasks · "
            f"{component.unresolved_incidents} unresolved incidents{spof_note}"
        )
        if component.description.strip():
            lines.append(f"  - {component.description.strip()[:240]}")
    if not lines:
        lines.append("- No component ownership assignments found for this engineer.")
    return lines


def _compile_knowledge_risks(
    employee: Employee,
    affected: list[EraAffectedComponent],
    evidence: list[dict],
    hotspots: dict[str, Any],
) -> list[str]:
    lines: list[str] = []
    ownership = get_github_ownership() if has_github_sync() else {}

    for component in affected:
        if not component.spof:
            continue
        owner_pct = component.ownership_pct
        owner_note = (
            f"{owner_pct:.0f}% GitHub ownership"
            if owner_pct is not None
            else "assignment-only ownership"
        )
        lines.append(
            f"- **{component.name}** — single-point-of-failure · {owner_note} · "
            f"{component.criticality}"
        )

    for assignment in employee.assignments:
        component = assignment.component
        github_pct = ownership.get(component.id, {}).get(employee.id)
        if github_pct is not None and github_pct >= _SOLE_OWNERSHIP_PCT:
            lines.append(
                f"- **{component.name}** — sole codebase owner "
                f"({github_pct:.0f}% GitHub / DOA share)"
            )
        elif assignment.codebase_share_pct >= _SOLE_OWNERSHIP_PCT and github_pct is None:
            lines.append(
                f"- **{component.name}** — dominant assignment owner "
                f"({assignment.codebase_share_pct:.0f}% share)"
            )
        if has_github_sync():
            bus_factor = get_component_bus_factor(component.id)
            if bus_factor is not None and bus_factor <= 1:
                lines.append(
                    f"- **{component.name}** — bus factor **{bus_factor}** "
                    "(critical files have a single authoritative author)"
                )

    for item in sorted(
        evidence,
        key=lambda row: row.get("impact_points", 0),
        reverse=True,
    )[:6]:
        if item.get("dimension") not in {"knowledge", "structural"}:
            continue
        lines.append(
            f"- **{item.get('title', 'Knowledge risk')}** — {item.get('description', '')}"
        )

    for file_row in hotspots.get("files", [])[:8]:
        lines.append(
            f"- `{file_row.get('file_path', 'unknown')}` — critical hotspot, churn "
            f"{file_row.get('churn_score', 0)}, bus factor "
            f"{file_row.get('bus_factor', '?')} "
            f"({file_row.get('component_name', 'component')})"
        )

    if not lines:
        lines.append("- No elevated sole-owner knowledge risks in current telemetry.")
    return lines


def _compile_open_jira_tasks(
    db: Session,
    tenant_id: uuid.UUID,
    employee: Employee,
    owned_component_ids: set[str],
) -> list[str]:
    hydrate_integration_telemetry(db, tenant_id)
    jira_ids = _provider_user_ids(db, tenant_id, employee.id, "jira")
    email = employee.email.strip().lower()
    lines: list[str] = []
    seen_keys: set[str] = set()

    for issue in get_cached_jira_issues():
        if issue.is_done:
            continue
        assignee_match = (
            issue.assignee_provider_user_id in jira_ids
            if issue.assignee_provider_user_id
            else False
        )
        email_match = (
            (issue.assignee_email or "").strip().lower() == email if email else False
        )
        component_match = (
            issue.component_id in owned_component_ids if issue.component_id else False
        )
        if not assignee_match and not email_match and not component_match:
            continue
        if issue.issue_key in seen_keys:
            continue
        seen_keys.add(issue.issue_key)
        detail = issue.summary or issue.issue_key
        if issue.description_text:
            detail = f"{detail} — {issue.description_text[:180]}"
        scope = "assigned" if assignee_match or email_match else "owned component"
        lines.append(
            f"- **{issue.issue_key}** ({issue.priority}, {issue.status}, {scope}): "
            f"{detail}"
        )

    if not lines:
        lines.append("- No active Jira issues linked to this engineer in sync telemetry.")
    return lines


def _compile_open_incidents(
    db: Session,
    tenant_id: uuid.UUID,
    employee: Employee,
    owned_component_ids: set[str],
) -> list[str]:
    hydrate_integration_telemetry(db, tenant_id)
    jira_ids = _provider_user_ids(db, tenant_id, employee.id, "jira")
    slack_ids = _provider_user_ids(db, tenant_id, employee.id, "slack")
    email = employee.email.strip().lower()
    lines: list[str] = []

    for assignment in employee.assignments:
        component = assignment.component
        if component.unresolved_incidents <= 0:
            continue
        lines.append(
            f"- **{component.name}** — {component.unresolved_incidents} unresolved "
            "incident(s) on owned system"
        )

    for issue in get_cached_jira_issues():
        if issue.is_done or not issue.is_bug_or_incident:
            continue
        assignee_match = issue.assignee_provider_user_id in jira_ids
        email_match = (issue.assignee_email or "").strip().lower() == email if email else False
        component_match = issue.component_id in owned_component_ids if issue.component_id else False
        if not assignee_match and not email_match and not component_match:
            continue
        lines.append(
            f"- **{issue.issue_key}** ({issue.priority}, {issue.status}): "
            f"{issue.summary[:200]}"
        )

    for thread in get_cached_slack_threads():
        if thread.resolved_at:
            continue
        channel = thread.channel_name.lstrip("#") or thread.channel_id
        involved = any(
            message.user_id in slack_ids
            for message in thread.messages
            if message.user_id and not message.is_bot
        )
        if not involved:
            continue
        lines.append(
            f"- #{channel} — active incident thread: {thread.parent_text.strip()[:200]}"
        )
        if len(lines) >= 12:
            break

    if not lines:
        lines.append("- No open production incidents attributed to this engineer.")
    return lines[:12]


def _compile_slack_troubleshooting(
    db: Session,
    tenant_id: uuid.UUID,
    employee: Employee,
    graph_snippets: list[str],
) -> list[str]:
    hydrate_integration_telemetry(db, tenant_id)
    lines: list[str] = []
    slack_ids = _provider_user_ids(db, tenant_id, employee.id, "slack")

    signals = get_slack_employee_signals(employee.id)
    if signals:
        for evidence in signals.thread_evidence[:8]:
            lines.append(
                f"- #{evidence.channel_name}: **{evidence.title[:120]}** "
                f"({evidence.kind}) — {evidence.thread_url}"
            )

    for thread in get_cached_slack_threads():
        channel = thread.channel_name.lstrip("#") or thread.channel_id
        for message in thread.messages:
            if message.is_bot or not message.user_id:
                continue
            if message.user_id not in slack_ids:
                continue
            lowered = message.text.lower()
            if not any(hint in lowered for hint in _TROUBLESHOOTING_HINTS):
                continue
            lines.append(
                f"- #{channel} thread `{thread.thread_ts}`: {message.text.strip()[:220]}"
            )
            if len(lines) >= 12:
                break
        if len(lines) >= 12:
            break

    for snippet in graph_snippets:
        lowered = snippet.lower()
        if not any(hint in lowered for hint in _TROUBLESHOOTING_HINTS):
            continue
        lines.append(f"- Retrieved context: {snippet[:280]}")

    if not lines:
        lines.append("- No Slack troubleshooting threads attributed to this engineer.")
    return lines[:15]


def _compile_documentation_gaps(
    db: Session,
    tenant_id: uuid.UUID,
    employee: Employee,
    graph_snippets: list[str],
) -> list[str]:
    component_ids = {assignment.component_id for assignment in employee.assignments}
    if not component_ids:
        return ["- No owned components — documentation gap scan not applicable."]

    docs = (
        db.query(NotionDocSnapshot)
        .filter(
            NotionDocSnapshot.tenant_id == tenant_id,
            NotionDocSnapshot.is_archived.is_(False),
            NotionDocSnapshot.component_id.in_(component_ids),
        )
        .all()
    )
    documented: dict[str, list[NotionDocSnapshot]] = {}
    for doc in docs:
        if doc.component_id and doc.page_kind in _DOC_KINDS:
            documented.setdefault(doc.component_id, []).append(doc)

    lines: list[str] = []
    for assignment in employee.assignments:
        component = assignment.component
        linked = documented.get(component.id, [])
        if linked:
            titles = ", ".join(doc.title[:60] for doc in linked[:2])
            lines.append(f"- **{component.name}** — covered by: {titles}")
            continue
        lines.append(
            f"- **{component.name}** — **writeup required**: missing runbook, "
            f"architecture doc, or postmortem "
            f"({component.unresolved_incidents} live incidents on record)."
        )

    signals = get_slack_employee_signals(employee.id)
    if signals and signals.undocumented_solved_incidents > 0:
        lines.append(
            f"- **Untracked hotfixes:** {signals.undocumented_solved_incidents} "
            "resolved incident thread(s) without matching documentation."
        )

    for snippet in graph_snippets:
        lowered = snippet.lower()
        if not any(
            token in lowered
            for token in ("runbook", "postmortem", "documentation", "notion", "wiki", "gap")
        ):
            continue
        lines.append(f"- Retrieved context: {snippet[:280]}")

    return lines


def _compile_graph_insights(buckets: dict[str, list[str]]) -> list[str]:
    lines: list[str] = []
    for bucket, snippets in buckets.items():
        if bucket == "documentation":
            continue
        for snippet in snippets[:3]:
            label = bucket.replace("_", " ")
            lines.append(f"- **{label.title()}:** {snippet}")
    if not lines:
        lines.append("- No supplemental knowledge-graph context retrieved for this engineer.")
    return lines[:12]


def _render_markdown(compilation: HandoverCompilation) -> str:
    section_one = list(compilation.component_lines)
    if compilation.knowledge_risk_lines:
        section_one.append("")
        section_one.append("**Sole-owner & knowledge transfer risks**")
        section_one.extend(compilation.knowledge_risk_lines)

    section_two = list(compilation.jira_lines)
    if compilation.incident_lines:
        section_two.append("")
        section_two.append("**Open incidents & production issues**")
        section_two.extend(compilation.incident_lines)

    parts = [
        f"# Employee Handover Blueprint: {compilation.employee_name}",
        "> Compiled from ownership assignments, integration telemetry (GitHub, Jira, "
        "Slack, Notion), risk scoring, and targeted knowledge-graph retrieval.",
    ]
    if compilation.risk_summary_lines:
        parts.append("\n".join(f"> {line.lstrip('- ')}" for line in compilation.risk_summary_lines[:3]))

    parts.extend(
        [
            "## 1. System Components Requiring Transfer",
            "\n".join(section_one),
            "## 2. Active Open Tasks (Jira Operations)",
            "\n".join(section_two),
            "## 3. Implicit Troubleshooting Areas (Slack Context Extracted)",
            "\n".join(compilation.slack_lines + compilation.graph_insight_lines),
            "## 4. Documentation Gaps & Untracked Hotfixes Needing Writeups",
            "\n".join(compilation.gap_lines),
        ]
    )
    return "\n\n".join(parts) + "\n"


async def compile_exit_handover_file(
    db: Session,
    employee_id: str,
    tenant_id: uuid.UUID,
) -> str:
    """
    Multi-source handover synthesis for one employee within a tenant dataset.

    PostgreSQL ownership + ERA risk scoring + integration telemetry, enriched by
    targeted Cognee CHUNKS retrieval over `tenant_dataset_name(tenant_id)`.
    """
    employee = _load_employee(db, tenant_id, employee_id)
    hydrate_integration_telemetry(db, tenant_id)
    owned_names = [assignment.component.name for assignment in employee.assignments]
    owned_component_ids = {assignment.component_id for assignment in employee.assignments}

    evidence, affected, composite, risk_level = _handover_risk_bundle(db, tenant_id, employee)
    hotspots = get_employee_hotspots(db, tenant_id, employee.id)

    graph_buckets = await _cognee_handover_research(tenant_id, employee, owned_names)

    compilation = HandoverCompilation(
        employee_name=employee.name,
        risk_summary_lines=_compile_risk_summary(composite, risk_level, evidence),
        component_lines=_compile_explicit_ownership(employee, affected),
        knowledge_risk_lines=_compile_knowledge_risks(
            employee,
            affected,
            evidence,
            hotspots,
        ),
        jira_lines=_compile_open_jira_tasks(
            db,
            tenant_id,
            employee,
            owned_component_ids,
        ),
        incident_lines=_compile_open_incidents(db, tenant_id, employee, owned_component_ids),
        slack_lines=_compile_slack_troubleshooting(
            db,
            tenant_id,
            employee,
            graph_buckets.get("incidents", []) + graph_buckets.get("blast_radius", []),
        ),
        gap_lines=_compile_documentation_gaps(
            db,
            tenant_id,
            employee,
            graph_buckets.get("documentation", []),
        ),
        graph_insight_lines=_compile_graph_insights(graph_buckets),
    )
    return _render_markdown(compilation)
