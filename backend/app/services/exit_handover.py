from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session, joinedload

from app.models.operational import Assignment, Employee
from app.schemas.era import EraEmployeeDetailResponse, EraEvidenceItem, EraMitigationItem
from app.schemas.exit import EmployeeOption, HandoverResponse
from app.services.exit_service import compile_exit_handover_file
from app.services.era.signals_builder import _undocumented_solved_incidents
from app.services.github_file_risk import get_employee_hotspots
from app.services.integration_config_store import get_jira_config
from app.services.role_utils import is_leadership_role


@dataclass
class EraHandoverContext:
    computed_at: datetime
    demo_mode: bool
    excluded: bool
    risk_score: float | None
    risk_level: str | None
    evidence: list[EraEvidenceItem] = field(default_factory=list)
    affected_components: list = field(default_factory=list)
    backup_candidates: list = field(default_factory=list)
    mitigations: list[EraMitigationItem] = field(default_factory=list)
    hotspots: list[dict] = field(default_factory=list)
    open_tasks: int = 0
    unresolved_issues: int = 0
    undocumented_incidents: int = 0
    documentation_score: float | None = None
    operational_score: float | None = None
    sections_included: list[str] = field(default_factory=list)


def list_exit_candidates(db: Session, tenant) -> list[EmployeeOption]:
    employees = (
        db.query(Employee)
        .filter(Employee.tenant_id == tenant.id)
        .order_by(Employee.name)
        .all()
    )
    candidates = [e for e in employees if not is_leadership_role(e.role)]
    if not candidates:
        return []
    return [EmployeeOption(id=e.id, name=e.name, role=e.role) for e in candidates]


def _hotfix_lines(employee_id: str, role: str, component_names: list[str]) -> list[str]:
    count = _undocumented_solved_incidents(employee_id, role)
    if count == 0:
        return ["No undocumented hotfixes flagged by Cognee graph traversal."]
    lines = []
    for index in range(count):
        component = component_names[index % len(component_names)] if component_names else "General"
        lines.append(
            f"- Hotfix #{index + 1} on **{component}**: production patch applied without "
            "runbook update — requires postmortem writeup."
        )
    return lines


def _tenant_demo_mode(db: Session, tenant) -> bool:
    return False


def _load_era_handover_context(
    db: Session,
    tenant,
    employee_id: str,
) -> EraHandoverContext | None:
    from app.services.era_analytics import get_era_employee_detail

    detail: EraEmployeeDetailResponse | None = get_era_employee_detail(
        db,
        tenant,
        employee_id,
        limit=1000,
        offset=0,
    )
    if detail is None:
        return None

    demo_mode = _tenant_demo_mode(db, tenant)
    employee = detail.employee
    if employee.excluded:
        return EraHandoverContext(
            computed_at=detail.computed_at,
            demo_mode=demo_mode,
            excluded=True,
            risk_score=None,
            risk_level=None,
        )

    hotspots_payload = get_employee_hotspots(db, tenant.id, employee_id)
    open_mitigations = [
        item
        for item in detail.mitigations
        if item.mitigation_status in {"open", "in_progress"}
    ]
    documentation_score = (
        employee.dimensions.documentation if employee.dimensions is not None else None
    )
    operational_score = (
        employee.dimensions.operational if employee.dimensions is not None else None
    )

    return EraHandoverContext(
        computed_at=detail.computed_at,
        demo_mode=demo_mode,
        excluded=False,
        risk_score=employee.risk_factor_score,
        risk_level=employee.risk_level,
        evidence=list(detail.evidence),
        affected_components=list(employee.affected_components or []),
        backup_candidates=list(detail.backup_candidates or []),
        mitigations=open_mitigations,
        hotspots=list(hotspots_payload.get("files") or []),
        open_tasks=employee.open_tasks,
        unresolved_issues=employee.unresolved_issues,
        undocumented_incidents=employee.undocumented_solved_incidents,
        documentation_score=documentation_score,
        operational_score=operational_score,
    )


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _render_critical_knowledge(evidence: list[EraEvidenceItem]) -> tuple[str, list[str]]:
    if not evidence:
        return "", []
    ranked = sorted(evidence, key=lambda item: item.impact_points, reverse=True)[:10]
    lines = []
    for item in ranked:
        source_links = ", ".join(
            f"[{source.label}]({source.url})"
            for source in item.sources
            if source.url
        )
        lines.append(
            f"- **{item.title}** ({item.dimension}, {item.severity}, "
            f"+{item.impact_points:.0f} pts) — {item.description}"
        )
        if source_links:
            lines.append(f"  - Sources: {source_links}")
    return "## Critical Knowledge to Transfer\n\n" + "\n".join(lines), ["critical_knowledge"]


def _render_owned_components(affected_components: list) -> tuple[str, list[str]]:
    if not affected_components:
        return "", []
    lines = []
    for component in affected_components:
        spof_flag = " — SPOF" if component.spof else ""
        ownership = (
            f" — {component.ownership_pct:.0f}% ownership"
            if component.ownership_pct is not None
            else ""
        )
        lines.append(
            f"- **{component.name}**{ownership}{spof_flag} "
            f"({component.criticality})"
        )
    return "## Owned Components & SPOF Flags\n\n" + "\n".join(lines), ["owned_components"]


def _render_successor(backup_candidates: list) -> tuple[str, list[str]]:
    if not backup_candidates:
        return "", []
    top = backup_candidates[0]
    return (
        "## Suggested Successor\n\n"
        f"- **{top.name}** — {top.component_name} "
        f"({top.ownership_pct:.0f}% ownership, {top.label}; "
        f"{top.review_count} reviews, {top.recent_commits} recent commits)",
        ["suggested_successor"],
    )


def _render_open_mitigations(mitigations: list[EraMitigationItem]) -> tuple[str, list[str]]:
    if not mitigations:
        return "", []
    lines = []
    for item in mitigations:
        checkbox = "[ ]" if item.mitigation_status != "done" else "[x]"
        status_note = (
            " _(in progress)_" if item.mitigation_status == "in_progress" else ""
        )
        lines.append(
            f"- {checkbox} {item.title}{status_note} _({item.priority})_"
        )
    return "## Open Mitigations\n\n" + "\n".join(lines), ["open_mitigations"]


def _render_tacit_gaps(ctx: EraHandoverContext) -> tuple[str, list[str]]:
    if ctx.undocumented_incidents <= 0 and not ctx.documentation_score:
        return "", []
    doc_note = (
        f" (documentation risk: {ctx.documentation_score:.0f}%)"
        if ctx.documentation_score is not None
        else ""
    )
    if ctx.undocumented_incidents <= 0:
        lines = [
            f"- Documentation dimension elevated{doc_note} — review runbooks and incident writeups."
        ]
    else:
        lines = [
            f"- {ctx.undocumented_incidents} undocumented solved incident(s) flagged{doc_note}."
        ]
    return "## Tacit Knowledge Gaps\n\n" + "\n".join(lines), ["tacit_knowledge_gaps"]


def _render_hotspots(hotspots: list[dict]) -> tuple[str, list[str]]:
    if not hotspots:
        return "", []
    lines = []
    for file_row in hotspots[:10]:
        component = file_row.get("component_name") or file_row.get("component_id") or "Unknown"
        lines.append(
            f"- `{file_row.get('file_path', 'unknown')}` — churn "
            f"{file_row.get('churn_score', 0)}, bus factor "
            f"{file_row.get('bus_factor', '?')} ({component})"
        )
    return "## Hotspot Files (Critical Quadrant)\n\n" + "\n".join(lines), ["hotspot_files"]


def _render_ops_backlog(
    db: Session,
    tenant,
    ctx: EraHandoverContext,
) -> tuple[str, list[str]]:
    if ctx.open_tasks <= 0 and ctx.unresolved_issues <= 0:
        return "", []
    jira_config = get_jira_config(db, tenant.id)
    jira_link = ""
    if jira_config and jira_config.site_url:
        jira_link = f" — [View in Jira]({jira_config.site_url.rstrip('/')}/issues/?filter=-1)"
    ops_note = (
        f" (operational risk: {ctx.operational_score:.0f}%)"
        if ctx.operational_score is not None
        else ""
    )
    return (
        "## Jira / Ops Backlog\n\n"
        f"- {ctx.open_tasks} open task(s), {ctx.unresolved_issues} unresolved issue(s){ops_note}{jira_link}",
        ["jira_ops_backlog"],
    )


def _render_era_sections(
    db: Session,
    tenant,
    ctx: EraHandoverContext,
) -> tuple[str, list[str]]:
    sections: list[str] = []
    included: list[str] = []

    for renderer in (
        lambda: _render_critical_knowledge(ctx.evidence),
        lambda: _render_owned_components(ctx.affected_components),
        lambda: _render_successor(ctx.backup_candidates),
        lambda: _render_open_mitigations(ctx.mitigations),
        lambda: _render_tacit_gaps(ctx),
        lambda: _render_hotspots(ctx.hotspots),
        lambda: _render_ops_backlog(db, tenant, ctx),
    ):
        block, keys = renderer()
        if block:
            sections.append(block)
            included.extend(keys)

    if not sections:
        sections.append(
            "## ERA Risk Context\n\n"
            "- No ERA evidence signals available — using standard Cognee handover template."
        )
        included.append("era_fallback")

    return "\n\n".join(sections), included


def _era_header_lines(ctx: EraHandoverContext) -> list[str]:
    lines = [
        "> Generated from ownership assignments, integration telemetry, risk scoring, "
        "and knowledge-graph retrieval.",
        (
            f"> **ERA risk assessment** computed at {_format_datetime(ctx.computed_at)}"
            + (
                f" — composite risk **{ctx.risk_score:.0f}%** ({ctx.risk_level})"
                if ctx.risk_score is not None and ctx.risk_level
                else ""
            )
        ),
    ]
    if ctx.demo_mode:
        lines.append("> ⚠ *Demo mode: ERA data is illustrative sample data.*")
    return lines


async def build_handover_markdown(
    db: Session,
    employee_id: str,
    tenant,
    *,
    prefill_era: bool = False,
) -> HandoverResponse:
    employee = (
        db.query(Employee)
        .options(joinedload(Employee.assignments).joinedload(Assignment.component))
        .filter(Employee.id == employee_id, Employee.tenant_id == tenant.id)
        .first()
    )

    if not employee:
        raise ValueError(f"Employee '{employee_id}' not found.")

    employee_name = employee.name
    markdown = await compile_exit_handover_file(db, employee_id, tenant.id)

    era_ctx: EraHandoverContext | None = None
    era_sections = ""
    era_sections_included: list[str] = []
    era_risk_score: float | None = None
    era_computed_at: datetime | None = None

    if prefill_era:
        era_ctx = _load_era_handover_context(db, tenant, employee_id)
        if era_ctx is not None and not era_ctx.excluded:
            era_sections, era_sections_included = _render_era_sections(db, tenant, era_ctx)
            era_risk_score = era_ctx.risk_score
            era_computed_at = era_ctx.computed_at

    if era_sections:
        lines = markdown.splitlines()
        insert_at = 2 if len(lines) > 1 and lines[1].startswith(">") else 1
        preamble = lines[:insert_at]
        remainder = lines[insert_at:]
        markdown = "\n".join(
            preamble + ["", era_sections, ""] + remainder
        )

    if era_ctx and not era_ctx.excluded:
        header_lines = _era_header_lines(era_ctx)
        lines = markdown.splitlines()
        markdown = "\n".join(lines[:1] + [""] + header_lines + lines[1:])

    safe_name = employee_name.lower().replace(" ", "-")
    return HandoverResponse(
        employee_id=employee_id,
        employee_name=employee_name,
        markdown=markdown,
        filename=f"handover-{safe_name}.md",
        era_risk_score=era_risk_score,
        era_sections_included=era_sections_included,
        era_computed_at=era_computed_at,
        prefill_from_era=prefill_era and era_ctx is not None and not era_ctx.excluded,
    )
