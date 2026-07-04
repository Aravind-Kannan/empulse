"""Deterministic KRA summary metrics (no Cognee scoring)."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.orm import Session

from app.models.operational import Assignment, Component, Employee, NotionDocSnapshot
from app.schemas.kra import (
    CriticalSpofComponent,
    CriticalSpofResult,
    DocumentationCoverageResult,
    DocumentationCoveredComponent,
    DocumentationGapComponent,
    KraMetricCoverage,
    KraSummaryResponse,
)
from app.services.integration_telemetry import (
    get_all_bus_factors,
    get_github_activities,
    get_github_ownership,
    get_notion_component_sources,
    has_github_sync,
    has_notion_sync,
    hydrate_github_telemetry_from_db,
    hydrate_integration_telemetry,
    hydrate_notion_telemetry_from_db,
    is_github_spof_component,
)
from app.services.integration_config_store import get_notion_config
from app.services.notion_client import (
    browser_notion_page_url,
    notion_slug_from_url,
)
from app.services.notion_telemetry import utc_dt

DOC_FRESHNESS_DAYS = 180
GITHUB_ACTIVITY_DAYS = 90


def _browser_doc_url(url: str | None, page_id: str | None = None) -> str | None:
    if not url and not page_id:
        return None
    normalized = browser_notion_page_url(page_id or "", url)
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return normalized
    return None


def _doc_link_priority(row: NotionDocSnapshot) -> tuple[int, datetime]:
    """Prefer slugged Notion URLs and GitHub doc-pack links over bare page ids."""
    url = (row.page_url or "").lower()
    score = 0
    if url.startswith(("https://github.com/", "http://github.com/")):
        score = 30
    elif notion_slug_from_url(row.page_url or ""):
        score = 20
    elif "notion.com" in url or "notion.so" in url:
        score = 5
    edited = utc_dt(row.last_edited_at) or datetime.min.replace(tzinfo=UTC)
    return (score, edited)


def _strip_notion_source_prefix(label: str) -> str:
    if label.lower().startswith("notion:"):
        return label.split(":", 1)[1].strip() or label
    return label


def _component_doc_display(
    linked_docs: list[NotionDocSnapshot],
    telemetry_sources: list[str],
) -> tuple[list[str], list[str]]:
    """Return aligned doc labels and browser-openable URLs (freshest first)."""
    if linked_docs:
        ordered = sorted(
            linked_docs,
            key=_doc_link_priority,
            reverse=True,
        )
        labels: list[str] = []
        urls: list[str] = []
        for row in ordered:
            url = _browser_doc_url(row.page_url, row.page_id)
            if not url:
                continue
            labels.append(row.title)
            urls.append(url)
        if labels:
            return labels, urls

    labels = [_strip_notion_source_prefix(source) for source in telemetry_sources]
    return labels, []


_KRA_SUMMARY_CACHE_TTL_SECONDS = 300.0
_kra_summary_cache: dict[uuid.UUID, tuple[float, KraSummaryResponse]] = {}


def invalidate_kra_summary_cache(tenant_id: uuid.UUID | None = None) -> None:
    if tenant_id is None:
        _kra_summary_cache.clear()
        return
    _kra_summary_cache.pop(tenant_id, None)


def _coverage_for_github() -> KraMetricCoverage:
    if has_github_sync():
        return KraMetricCoverage(github="confirmed", is_partial=False)
    return KraMetricCoverage(github="missing", is_partial=True)


def _empty_critical_spof_result(coverage: KraMetricCoverage) -> CriticalSpofResult:
    return CriticalSpofResult(count=0, components=[], data_completeness=coverage)


def _owners_by_component(
    db: Session,
    tenant_id: uuid.UUID,
) -> dict[str, set[str]]:
    owners: dict[str, set[str]] = defaultdict(set)
    assignments = (
        db.query(Assignment)
        .filter(Assignment.tenant_id == tenant_id)
        .all()
    )
    for assignment in assignments:
        owners[assignment.component_id].add(assignment.employee_id)

    if has_github_sync():
        github_ownership = get_github_ownership()
        for component_id, contributors in github_ownership.items():
            owners[component_id] = set(contributors.keys())

    return owners


def _employee_names(db: Session, tenant_id: uuid.UUID) -> dict[str, str]:
    rows = db.query(Employee).filter(Employee.tenant_id == tenant_id).all()
    return {row.id: row.name for row in rows}


def _is_critical_spof(
    *,
    criticality: str,
    component_id: str,
    owner_ids: set[str],
    bus_factors: dict[str, int],
    github_connected: bool,
    github_ownership: dict[str, dict[str, float]],
) -> tuple[bool, bool]:
    if criticality != "tier1_revenue":
        return False, False

    github_verified = False
    if github_connected:
        contributors = github_ownership.get(component_id, {})
        bus_factor = bus_factors.get(component_id)
        if is_github_spof_component(contributors, bus_factor=bus_factor):
            github_verified = bus_factor is not None and bus_factor <= 1
            return True, github_verified

    if len(owner_ids) <= 1:
        return True, github_verified

    return False, github_verified


def compute_critical_spof_count(
    db: Session,
    tenant_id: uuid.UUID,
) -> CriticalSpofResult:
    hydrate_github_telemetry_from_db(db, tenant_id)

    github_connected = has_github_sync()
    bus_factors = get_all_bus_factors() if github_connected else {}
    github_ownership = get_github_ownership() if github_connected else {}
    coverage = _coverage_for_github()

    employees = db.query(Employee).filter(Employee.tenant_id == tenant_id).all()
    components = db.query(Component).filter(Component.tenant_id == tenant_id).all()

    if not employees or not components:
        return _empty_critical_spof_result(coverage)

    owners_by_component = _owners_by_component(db, tenant_id)
    employee_names = _employee_names(db, tenant_id)

    critical_components: list[CriticalSpofComponent] = []
    for component in components:
        owner_ids = owners_by_component.get(component.id, set())
        is_spof, github_verified = _is_critical_spof(
            criticality=component.criticality,
            component_id=component.id,
            owner_ids=owner_ids,
            bus_factors=bus_factors,
            github_connected=github_connected,
            github_ownership=github_ownership,
        )
        if not is_spof:
            continue

        owner_name_list = [
            employee_names[owner_id]
            for owner_id in sorted(owner_ids)
            if owner_id in employee_names
        ]
        critical_components.append(
            CriticalSpofComponent(
                component_id=component.id,
                component_name=component.name,
                bus_factor=bus_factors.get(component.id),
                owner_count=len(owner_ids),
                owner_names=owner_name_list[:3],
                github_verified=github_verified,
                criticality=component.criticality,
            )
        )

    critical_components.sort(key=lambda row: row.component_name)
    return CriticalSpofResult(
        count=len(critical_components),
        components=critical_components,
        data_completeness=coverage,
    )


def _parse_merged_at(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _components_with_recent_prs() -> set[str]:
    cutoff = datetime.now(UTC) - timedelta(days=GITHUB_ACTIVITY_DAYS)
    active: set[str] = set()
    for activity in get_github_activities():
        merged_at = _parse_merged_at(activity.merged_at)
        if merged_at is None or merged_at < cutoff:
            continue
        for file_change in activity.files:
            if file_change.component_id:
                active.add(file_change.component_id)
    return active


def _days_since_last_pr(component_id: str) -> int | None:
    latest: datetime | None = None
    for activity in get_github_activities():
        merged_at = _parse_merged_at(activity.merged_at)
        if merged_at is None:
            continue
        for file_change in activity.files:
            if file_change.component_id != component_id:
                continue
            if latest is None or merged_at > latest:
                latest = merged_at
    if latest is None:
        return None
    return max(0, (datetime.now(UTC) - latest).days)


def _coverage_for_documentation(
    *,
    notion_configured: bool,
    notion_telemetry_ready: bool,
    github_connected: bool,
    has_assignments: bool,
) -> KraMetricCoverage:
    if not notion_configured:
        notion: Literal["confirmed", "partial", "missing"] = "missing"
    elif notion_telemetry_ready:
        notion = "confirmed"
    else:
        notion = "partial"
    if github_connected:
        github: Literal["confirmed", "partial", "missing"] = "confirmed"
    elif has_assignments:
        github = "partial"
    else:
        github = "missing"
    is_partial = notion != "confirmed" or github != "confirmed"
    return KraMetricCoverage(github=github, notion=notion, is_partial=is_partial)


def _empty_documentation_coverage(coverage: KraMetricCoverage) -> DocumentationCoverageResult:
    return DocumentationCoverageResult(
        coverage_pct=None,
        active_component_count=0,
        covered_count=0,
        covered_components=[],
        gap_components=[],
        data_completeness=coverage,
    )


def compute_documentation_coverage(
    db: Session,
    tenant_id: uuid.UUID,
) -> DocumentationCoverageResult:
    hydrate_github_telemetry_from_db(db, tenant_id)
    hydrate_notion_telemetry_from_db(db, tenant_id)

    github_connected = has_github_sync()
    notion_configured = get_notion_config(db, tenant_id) is not None
    notion_telemetry_ready = has_notion_sync()
    assignments = (
        db.query(Assignment)
        .filter(Assignment.tenant_id == tenant_id)
        .all()
    )
    assigned_component_ids = {row.component_id for row in assignments}
    coverage = _coverage_for_documentation(
        notion_configured=notion_configured,
        notion_telemetry_ready=notion_telemetry_ready,
        github_connected=github_connected,
        has_assignments=bool(assigned_component_ids),
    )

    if not notion_configured:
        return _empty_documentation_coverage(coverage)

    if not notion_telemetry_ready:
        return _empty_documentation_coverage(coverage)

    components = db.query(Component).filter(Component.tenant_id == tenant_id).all()
    if not components:
        return _empty_documentation_coverage(coverage)

    recent_pr_components = _components_with_recent_prs()
    github_ownership = get_github_ownership() if github_connected else {}

    active_components: list[Component] = []
    for component in components:
        has_assignment = component.id in assigned_component_ids
        if github_connected:
            if component.id in github_ownership or component.id in recent_pr_components:
                active_components.append(component)
        elif has_assignment:
            active_components.append(component)

    if not active_components:
        return _empty_documentation_coverage(coverage)

    snapshot_rows = (
        db.query(NotionDocSnapshot)
        .filter(
            NotionDocSnapshot.tenant_id == tenant_id,
            NotionDocSnapshot.is_archived.is_(False),
        )
        .all()
    )
    docs_by_component: dict[str, list[NotionDocSnapshot]] = defaultdict(list)
    for row in snapshot_rows:
        if row.component_id:
            docs_by_component[row.component_id].append(row)

    stale_cutoff = datetime.now(UTC) - timedelta(days=DOC_FRESHNESS_DAYS)
    covered_count = 0
    covered_components: list[DocumentationCoveredComponent] = []
    gap_components: list[DocumentationGapComponent] = []

    for component in active_components:
        telemetry_sources = get_notion_component_sources(component.id)
        linked_docs = docs_by_component.get(component.id, [])
        documented = bool(telemetry_sources) or bool(linked_docs)

        last_edit: datetime | None = None
        if linked_docs:
            freshest = max(
                linked_docs,
                key=lambda row: utc_dt(row.last_edited_at)
                or datetime.min.replace(tzinfo=UTC),
            )
            last_edit = utc_dt(freshest.last_edited_at)

        display_sources, page_urls = _component_doc_display(
            linked_docs,
            telemetry_sources,
        )
        if not display_sources and linked_docs:
            display_sources = [row.title for row in linked_docs]

        is_fresh = False
        if documented and last_edit is not None:
            is_fresh = last_edit >= stale_cutoff
        elif documented and telemetry_sources and not linked_docs:
            is_fresh = True

        if documented and is_fresh:
            covered_count += 1
            covered_components.append(
                DocumentationCoveredComponent(
                    component_id=component.id,
                    component_name=component.name,
                    last_doc_edit=last_edit.isoformat() if last_edit else None,
                    notion_sources=display_sources,
                    notion_page_urls=page_urls,
                )
            )
            continue

        gap_components.append(
            DocumentationGapComponent(
                component_id=component.id,
                component_name=component.name,
                gap_reason="stale" if documented else "missing",
                last_doc_edit=last_edit.isoformat() if last_edit else None,
                notion_sources=display_sources,
                notion_page_urls=page_urls,
                days_since_activity=_days_since_last_pr(component.id)
                if github_connected
                else None,
            )
        )

    coverage_pct = round(100 * covered_count / len(active_components))
    covered_components.sort(key=lambda row: row.component_name)
    gap_components.sort(key=lambda row: row.component_name)
    return DocumentationCoverageResult(
        coverage_pct=coverage_pct,
        active_component_count=len(active_components),
        covered_count=covered_count,
        covered_components=covered_components,
        gap_components=gap_components,
        data_completeness=coverage,
    )


def get_kra_summary(db: Session, tenant_id: uuid.UUID) -> KraSummaryResponse:
    cached = _kra_summary_cache.get(tenant_id)
    if cached and (time.time() - cached[0]) < _KRA_SUMMARY_CACHE_TTL_SECONDS:
        return cached[1].model_copy(deep=True)

    hydrate_integration_telemetry(db, tenant_id)

    summary = KraSummaryResponse(
        critical_spof=compute_critical_spof_count(db, tenant_id),
        documentation_coverage=compute_documentation_coverage(db, tenant_id),
    )
    _kra_summary_cache[tenant_id] = (time.time(), summary)
    return summary.model_copy(deep=True)
