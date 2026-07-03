from collections import defaultdict
from types import SimpleNamespace

from sqlalchemy.orm import Session, joinedload

from app.models.operational import Assignment, Component, Employee
from app.schemas.kra import KraAnalyticsResponse, KraLink, KraNode, KraSpofReason
from app.services.github_component_display import (
    format_github_component_name_from_description,
    github_provision_key,
    is_github_managed_component,
)
from app.services.integration_telemetry import (
    SPOF_OWNERSHIP_THRESHOLD,
    get_all_bus_factors,
    get_github_ownership,
    get_notion_component_sources,
    has_github_sync,
    has_notion_sync,
    hydrate_notion_telemetry_from_db,
    is_github_spof,
)
from app.services.role_utils import is_leadership_role


def _compute_spof_reasons(
    component_id: str,
    *,
    structural_spof: bool,
    github_verified: bool,
    bus_factor: int | None,
    owner_count: int,
    links: list[KraLink],
    employee_names: dict[str, str],
    github_synced: bool,
) -> list[KraSpofReason]:
    reasons: list[KraSpofReason] = []

    if structural_spof:
        reasons.append(
            KraSpofReason(
                kind="single_owner",
                title="Single owner on org chart",
                detail="Only one engineer is linked to this component.",
            )
        )

    component_shares = [
        (link.source, link.codebase_share_pct)
        for link in links
        if link.target == component_id and link.codebase_share_pct is not None
    ]
    if github_synced and component_shares:
        dominant_id, max_pct = max(component_shares, key=lambda row: row[1])
        if max_pct > SPOF_OWNERSHIP_THRESHOLD and (
            owner_count > 1 or github_verified
        ):
            dominant_name = employee_names.get(dominant_id, dominant_id)
            other_parts = [
                f"{employee_names.get(employee_id, employee_id)} {pct:.0f}%"
                for employee_id, pct in sorted(
                    component_shares, key=lambda row: -row[1]
                )
                if employee_id != dominant_id
            ]
            detail = (
                f"{dominant_name} holds {max_pct:.0f}% of recent change volume "
                f"(>{SPOF_OWNERSHIP_THRESHOLD:.0f}% threshold)."
            )
            if other_parts:
                detail += f" Others: {', '.join(other_parts)}."
            reasons.append(
                KraSpofReason(
                    kind="dominant_owner",
                    title="Dominant owner",
                    detail=detail,
                )
            )

    if github_verified and github_synced and bus_factor is not None and bus_factor <= 1:
        reasons.append(
            KraSpofReason(
                kind="low_bus_factor",
                title="Bus factor ≤ 1",
                detail=(
                    f"Bus factor is {bus_factor} — only one engineer is "
                    "DOA-authoritative (score ≥ 0.75) on enough files. Other "
                    "contributors may have minor edits only (Fritz DOA model), "
                    "not enough for operational backup."
                ),
            )
        )

    return reasons


def _collapse_github_duplicate_components(
    components: list,
    assignments: list,
) -> tuple[list, list, dict[str, str]]:
    """One graph node per GitHub path even if Postgres has legacy duplicate rows."""
    manual: list = []
    by_key: dict[str, list] = defaultdict(list)
    for component in components:
        key = github_provision_key(component.description)
        if (component.description or "").startswith("AUTO:") and key:
            by_key[key].append(component)
        else:
            manual.append(component)

    alias: dict[str, str] = {}
    kept = list(manual)
    assignment_counts: dict[str, int] = defaultdict(int)
    for assignment in assignments:
        assignment_counts[assignment.component_id] += 1

    for group in by_key.values():
        if len(group) == 1:
            kept.append(group[0])
            continue

        def rank(component) -> tuple[int, int]:
            return (assignment_counts.get(component.id, 0), len(component.id))

        keeper = max(group, key=rank)
        kept.append(keeper)
        for component in group:
            if component.id != keeper.id:
                alias[component.id] = keeper.id

    if not alias:
        return components, assignments, alias

    kept_ids = {component.id for component in kept}
    collapsed_assignments: list = []
    seen_pairs: set[tuple[str, str]] = set()
    for assignment in assignments:
        component_id = alias.get(assignment.component_id, assignment.component_id)
        if component_id not in kept_ids:
            continue
        pair = (assignment.employee_id, component_id)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        collapsed_assignments.append(
            SimpleNamespace(
                employee_id=assignment.employee_id,
                component_id=component_id,
                codebase_share_pct=assignment.codebase_share_pct,
            )
        )

    return kept, collapsed_assignments, alias


def _dedupe_links(links: list[KraLink]) -> list[KraLink]:
    best: dict[tuple[str, str], KraLink] = {}
    for link in links:
        key = (link.source, link.target)
        existing = best.get(key)
        if existing is None or (link.codebase_share_pct or 0) > (
            existing.codebase_share_pct or 0
        ):
            best[key] = link
    return list(best.values())


def _normalize_share_percentages(shares: dict[str, float]) -> dict[str, float]:
    if not shares:
        return {}
    total = sum(shares.values())
    if total <= 0:
        return shares
    if abs(total - 100.0) <= 0.05:
        return {employee_id: round(pct, 1) for employee_id, pct in shares.items()}
    return {
        employee_id: round((pct / total) * 100, 1)
        for employee_id, pct in shares.items()
    }


def _merge_github_ownership(
    github_ownership: dict[str, dict[str, float]],
    component_alias: dict[str, str],
) -> dict[str, dict[str, float]]:
    merged: dict[str, dict[str, float]] = defaultdict(dict)
    for component_id, contributors in github_ownership.items():
        canonical_id = component_alias.get(component_id, component_id)
        for employee_id, share_pct in contributors.items():
            current = merged[canonical_id].get(employee_id, 0.0)
            merged[canonical_id][employee_id] = max(current, share_pct)
    return dict(merged)


def _ownership_links_for_component(
    component,
    assignments: list,
    github_ownership: dict[str, dict[str, float]],
    *,
    github_synced: bool,
) -> list[KraLink]:
    github_contributors = github_ownership.get(component.id, {})
    github_managed = is_github_managed_component(component.description)

    if github_synced and github_managed and github_contributors:
        return [
            KraLink(
                source=employee_id,
                target=component.id,
                relationship="owns",
                codebase_share_pct=share_pct,
                ownership_source="github",
            )
            for employee_id, share_pct in sorted(
                github_contributors.items(),
                key=lambda row: -row[1],
            )
        ]

    assignment_shares = {
        assignment.employee_id: float(assignment.codebase_share_pct)
        for assignment in assignments
        if assignment.component_id == component.id
    }
    normalized = _normalize_share_percentages(assignment_shares)
    return [
        KraLink(
            source=employee_id,
            target=component.id,
            relationship="owns",
            codebase_share_pct=share_pct,
            ownership_source="org_chart",
        )
        for employee_id, share_pct in sorted(
            normalized.items(),
            key=lambda row: -row[1],
        )
    ]


def _doc_sources_for_component(
    component_id: str,
    name: str,
    description: str | None = None,
) -> list[str]:
    if not has_notion_sync():
        return []
    sources = get_notion_component_sources(component_id)
    if sources:
        return sources
    display_name = format_github_component_name_from_description(description) or name
    return [f"No Notion runbook for {display_name}"]


def _build_graph(
    employees: list,
    components: list,
    assignments: list,
    *,
    component_alias: dict[str, str] | None = None,
) -> KraAnalyticsResponse:
    nodes: list[KraNode] = []

    alias = component_alias or {}

    for employee in employees:
        if is_leadership_role(employee.role):
            continue
        nodes.append(
            KraNode(
                id=employee.id,
                label=employee.name,
                type="engineer",
                role=employee.role,
            )
        )

    component_nodes: list[KraNode] = []
    for component in components:
        component_nodes.append(
            KraNode(
                id=component.id,
                label=component.name,
                type="component",
                description=component.description,
                documentation_sources=_doc_sources_for_component(
                    component.id, component.name, component.description
                ),
            )
        )
    nodes.extend(component_nodes)

    github_synced = has_github_sync()
    github_ownership: dict[str, dict[str, float]] = {}
    if github_synced:
        github_ownership = _merge_github_ownership(get_github_ownership(), alias)

    links: list[KraLink] = []
    for component in components:
        links.extend(
            _ownership_links_for_component(
                component,
                assignments,
                github_ownership,
                github_synced=github_synced,
            )
        )

    engineers_by_component: dict[str, set[str]] = defaultdict(set)
    for link in links:
        engineers_by_component[link.target].add(link.source)

    bus_factors = get_all_bus_factors() if github_synced else {}
    employee_names = {
        node.id: node.label for node in nodes if node.type == "engineer"
    }

    for node in nodes:
        if node.type != "component":
            continue
        owner_count = len(engineers_by_component.get(node.id, set()))
        structural_spof = owner_count <= 1
        github_spof = is_github_spof(node.id) or any(
            is_github_spof(dup_id)
            for dup_id, keeper_id in alias.items()
            if keeper_id == node.id
        )
        bus_factor = bus_factors.get(node.id)
        node.is_spof = structural_spof or github_spof
        node.github_verified_spof = github_spof
        node.bus_factor = bus_factor
        if node.is_spof:
            node.spof_reasons = _compute_spof_reasons(
                node.id,
                structural_spof=structural_spof,
                github_verified=github_spof,
                bus_factor=bus_factor,
                owner_count=owner_count,
                links=links,
                employee_names=employee_names,
                github_synced=github_synced,
            )

    links = _dedupe_links(links)
    return KraAnalyticsResponse(nodes=nodes, links=links)


def _empty_graph() -> KraAnalyticsResponse:
    return KraAnalyticsResponse(nodes=[], links=[])


def get_kra_graph(db: Session, tenant) -> KraAnalyticsResponse:
    hydrate_notion_telemetry_from_db(db, tenant.id)
    employees = db.query(Employee).filter(Employee.tenant_id == tenant.id).all()
    components = db.query(Component).filter(Component.tenant_id == tenant.id).all()
    assignments = (
        db.query(Assignment)
        .filter(Assignment.tenant_id == tenant.id)
        .options(joinedload(Assignment.employee), joinedload(Assignment.component))
        .all()
    )

    if not employees or not components:
        return _empty_graph()

    class _EmployeeView:
        def __init__(self, emp: Employee):
            self.id = emp.id
            self.name = emp.name
            self.role = emp.role

    class _ComponentView:
        def __init__(self, comp: Component):
            self.id = comp.id
            self.name = comp.name
            self.description = comp.description

    class _AssignmentView:
        def __init__(self, asn: Assignment):
            self.employee_id = asn.employee_id
            self.component_id = asn.component_id
            self.codebase_share_pct = asn.codebase_share_pct

    component_views = [_ComponentView(c) for c in components]
    assignment_views = [_AssignmentView(a) for a in assignments]
    collapsed_components, collapsed_assignments, alias = (
        _collapse_github_duplicate_components(component_views, assignment_views)
    )

    return _build_graph(
        [_EmployeeView(e) for e in employees],
        collapsed_components,
        collapsed_assignments,
        component_alias=alias,
    )
