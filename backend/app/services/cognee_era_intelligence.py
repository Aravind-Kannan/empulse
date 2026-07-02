"""Cognee-backed ERA intelligence: backups, blast radius, evidence enrichment (Step 10)."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.operational import Employee
from app.schemas.era import EraAffectedComponent, EraBackupCandidate, EraRecoveryEstimate
from app.services.identity_resolver import resolve_author_employee_id
from app.services.integration_telemetry import (
    get_cached_jira_issues,
    get_github_activities,
    get_github_ownership,
    get_notion_component_sources,
    get_review_network,
    has_github_sync,
    has_jira_sync,
    has_notion_sync,
    is_github_spof,
)


class CogneeUnavailable(Exception):
    """Raised when tenant-scoped Cognee graph queries cannot be completed."""


CACHE_TTL = timedelta(hours=1)
_RAMPING_REVIEW_THRESHOLD = 3
_BACKUP_WEIGHT_DOA = 0.4
_BACKUP_WEIGHT_REVIEWS = 0.35
_BACKUP_WEIGHT_COMMITS = 0.25


@dataclass
class EmployeeIntelligenceResult:
    backup_candidates: list[EraBackupCandidate]
    enriched_evidence: list[dict]
    warnings: list[str]
    blast_radius_narrative: str | None
    recovery_estimate: EraRecoveryEstimate | None


_intelligence_cache: dict[str, tuple[datetime, EmployeeIntelligenceResult]] = {}


def reset_intelligence_cache_for_tests() -> None:
    _intelligence_cache.clear()


def _cache_key(tenant_id: uuid.UUID, employee_id: str) -> str:
    return f"{tenant_id}:{employee_id}"


def _employee_name_map(db: Session, tenant_id: uuid.UUID) -> dict[str, str]:
    return {
        row.id: row.name
        for row in db.query(Employee).filter(Employee.tenant_id == tenant_id).all()
    }


def _review_counts_for_author(author_employee_id: str) -> dict[str, int]:
    network = get_review_network()
    if network is None:
        return {}
    counts: dict[str, int] = {}
    for edge in network.edges:
        if edge.author_employee_id != author_employee_id:
            continue
        counts[edge.reviewer_employee_id] = (
            counts.get(edge.reviewer_employee_id, 0) + edge.review_count
        )
    return counts


def _recent_commits_by_employee(
    db: Session,
    tenant_id: uuid.UUID,
    component_id: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for activity in get_github_activities():
        if activity.author_type == "Bot":
            continue
        touched = any(
            file_change.component_id == component_id for file_change in activity.files
        )
        if not touched:
            continue
        author_id = resolve_author_employee_id(
            db,
            tenant_id,
            "github",
            activity.author_provider_user_id,
            demo_fallback_employee_id=None,
            quarantine_event_type="github_pr",
            quarantine_payload={"pr_number": activity.pr_number},
        )
        if not author_id:
            continue
        counts[author_id] = counts.get(author_id, 0) + 1
    return counts


def _backup_score(
    *,
    doa_secondary_pct: float,
    review_participation: int,
    recent_commits: int,
) -> float:
    return round(
        doa_secondary_pct * _BACKUP_WEIGHT_DOA
        + review_participation * _BACKUP_WEIGHT_REVIEWS
        + recent_commits * _BACKUP_WEIGHT_COMMITS,
        2,
    )


def _backup_label(review_participation: int) -> str:
    return "ramping" if review_participation >= _RAMPING_REVIEW_THRESHOLD else "secondary"


def find_backup_candidates(
    db: Session,
    tenant_id: uuid.UUID,
    employee_id: str,
    component_id: str,
    *,
    component_name: str,
    limit: int = 3,
) -> list[EraBackupCandidate]:
    """Rank backup engineers for one component from DOA, reviews, and commits."""
    ownership = get_github_ownership().get(component_id, {})
    if not ownership:
        return []

    review_counts = _review_counts_for_author(employee_id)
    commit_counts = _recent_commits_by_employee(db, tenant_id, component_id)
    employee_names = _employee_name_map(db, tenant_id)

    ranked: list[EraBackupCandidate] = []
    for candidate_id, ownership_pct in ownership.items():
        if candidate_id == employee_id or ownership_pct <= 0:
            continue
        review_count = review_counts.get(candidate_id, 0)
        recent_commits = commit_counts.get(candidate_id, 0)
        ranked.append(
            EraBackupCandidate(
                employee_id=candidate_id,
                name=employee_names.get(candidate_id, candidate_id),
                component_id=component_id,
                component_name=component_name,
                ownership_pct=round(ownership_pct, 1),
                review_count=review_count,
                recent_commits=recent_commits,
                score=_backup_score(
                    doa_secondary_pct=ownership_pct,
                    review_participation=review_count,
                    recent_commits=recent_commits,
                ),
                label=_backup_label(review_count),
            )
        )

    ranked.sort(
        key=lambda row: (-row.score, -row.ownership_pct, -row.review_count, row.name),
    )
    return ranked[:limit]


def find_backup_candidates_for_employee(
    db: Session,
    tenant_id: uuid.UUID,
    employee: Employee,
    affected_components: list[EraAffectedComponent],
    *,
    limit_per_component: int = 3,
) -> list[EraBackupCandidate]:
    if not has_github_sync():
        return []

    candidates: list[EraBackupCandidate] = []
    for component in affected_components:
        if not component.spof and not is_github_spof(component.id):
            continue
        candidates.extend(
            find_backup_candidates(
                db,
                tenant_id,
                employee.id,
                component.id,
                component_name=component.name,
                limit=limit_per_component,
            )
        )
    return candidates


def detect_documentation_gaps(
    component_ids: list[str],
    *,
    notion_connected: bool,
) -> list[str]:
    """Components with code activity but no Notion documentedBy coverage."""
    if not notion_connected or not has_notion_sync():
        return []
    gaps: list[str] = []
    for component_id in component_ids:
        if component_id not in get_github_ownership():
            continue
        if get_notion_component_sources(component_id):
            continue
        gaps.append(component_id)
    return gaps


def _jira_links_by_component() -> dict[str, list[dict]]:
    if not has_jira_sync():
        return {}
    grouped: dict[str, list[dict]] = {}
    for issue in get_cached_jira_issues():
        if issue.is_done or not issue.component_id:
            continue
        grouped.setdefault(issue.component_id, []).append(
            {
                "provider": "jira",
                "label": f"{issue.issue_key} ({issue.priority})",
                "url": issue.issue_url,
            }
        )
    return grouped


def _employee_component_ids_from_prs(
    db: Session,
    tenant_id: uuid.UUID,
    employee_id: str,
) -> set[str]:
    component_ids: set[str] = set()
    for activity in get_github_activities():
        if activity.author_type == "Bot":
            continue
        author_id = resolve_author_employee_id(
            db,
            tenant_id,
            "github",
            activity.author_provider_user_id,
            demo_fallback_employee_id=None,
            quarantine_event_type="github_pr",
            quarantine_payload={"pr_number": activity.pr_number},
        )
        if author_id != employee_id:
            continue
        for file_change in activity.files:
            if file_change.component_id:
                component_ids.add(file_change.component_id)
    return component_ids


def enrich_evidence_with_graph_links(
    db: Session,
    tenant_id: uuid.UUID,
    employee_id: str,
    evidence: list[dict],
    *,
    jira_connected: bool,
) -> list[dict]:
    """
    Append graph-derived Jira links where PR activity touches components with
    open Jira tickets (PR → modifies → Component ← blocksComponent ← JiraTicket).
    """
    if not jira_connected:
        return evidence

    jira_by_component = _jira_links_by_component()
    if not jira_by_component:
        return evidence

    touched_components = _employee_component_ids_from_prs(db, tenant_id, employee_id)
    if not touched_components:
        touched_components = set(jira_by_component)

    enriched: list[dict] = []
    for item in evidence:
        row = dict(item)
        sources = list(row.get("sources") or [])
        existing_urls = {source.get("url") for source in sources if source.get("url")}
        added = False
        for component_id in touched_components:
            for jira_source in jira_by_component.get(component_id, []):
                url = jira_source.get("url")
                if url and url in existing_urls:
                    continue
                sources.append(jira_source)
                added = True
                if url:
                    existing_urls.add(url)
        if added:
            description = row.get("description", "")
            if "graph-linked Jira" not in description:
                row["description"] = (
                    f"{description} Graph-linked Jira tickets on touched components."
                ).strip()
        row["sources"] = sources
        enriched.append(row)
    return enriched


def refine_recovery_estimate(
    base: EraRecoveryEstimate | None,
    *,
    blast_radius_narrative: str | None,
    spof_count: int,
) -> EraRecoveryEstimate | None:
    if base is None:
        return None
    extra = 0
    if spof_count >= 2:
        extra += 1
    if blast_radius_narrative and len(blast_radius_narrative.split()) > 12:
        extra += 1
    if extra == 0:
        return base
    return EraRecoveryEstimate(min=base.min, max=base.max + extra)


async def fetch_blast_radius_narrative(
    tenant_id: uuid.UUID,
    employee_name: str,
    component_names: list[str],
) -> str | None:
    if not component_names:
        return None
    from app.services.tenant_cognee import tenant_graph_search

    components_clause = ", ".join(component_names[:6])
    query = (
        f"What systems depend on {employee_name}'s owned components "
        f"({components_clause})?"
    )
    try:
        results = await tenant_graph_search(query, tenant_id, top_k=5)
    except Exception as exc:
        raise CogneeUnavailable(str(exc)) from exc

    if not results:
        return None

    snippets: list[str] = []
    for result in results[:3]:
        text = _result_to_text(result).strip()
        if text:
            snippets.append(text)
    if not snippets:
        return None
    return " ".join(snippets)[:500]


def _result_to_text(result: object) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("text", "content", "summary", "answer"):
            value = result.get(key)
            if isinstance(value, str):
                return value
    return str(result)


def _run_cognee(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    new_loop = asyncio.new_event_loop()
    try:
        return new_loop.run_until_complete(coro)
    finally:
        new_loop.close()


def build_employee_detail_intelligence(
    db: Session,
    tenant_id: uuid.UUID,
    employee: Employee,
    evidence: list[dict],
    affected_components: list[EraAffectedComponent],
    *,
    jira_connected: bool,
    notion_connected: bool,
    recovery_estimate: EraRecoveryEstimate | None,
    use_cache: bool = True,
) -> EmployeeIntelligenceResult:
    cache_key = _cache_key(tenant_id, employee.id)
    if use_cache:
        cached = _intelligence_cache.get(cache_key)
        if cached and datetime.now(UTC) - cached[0] < CACHE_TTL:
            return cached[1]

    warnings: list[str] = []
    backup_candidates = find_backup_candidates_for_employee(
        db,
        tenant_id,
        employee,
        affected_components,
    )

    enriched_evidence = enrich_evidence_with_graph_links(
        db,
        tenant_id,
        employee.id,
        evidence,
        jira_connected=jira_connected,
    )

    doc_gaps = detect_documentation_gaps(
        [component.id for component in affected_components],
        notion_connected=notion_connected,
    )
    if doc_gaps:
        warnings.append("documentation_gap_detected")

    blast_radius_narrative: str | None = None
    component_names = [component.name for component in affected_components]
    try:
        blast_radius_narrative = _run_cognee(
            fetch_blast_radius_narrative(tenant_id, employee.name, component_names)
        )
    except CogneeUnavailable:
        warnings.append("cognee_degraded")

    spof_count = sum(1 for component in affected_components if component.spof)
    refined_recovery = refine_recovery_estimate(
        recovery_estimate,
        blast_radius_narrative=blast_radius_narrative,
        spof_count=spof_count,
    )

    result = EmployeeIntelligenceResult(
        backup_candidates=backup_candidates,
        enriched_evidence=enriched_evidence,
        warnings=warnings,
        blast_radius_narrative=blast_radius_narrative,
        recovery_estimate=refined_recovery,
    )
    _intelligence_cache[cache_key] = (datetime.now(UTC), result)
    return result
