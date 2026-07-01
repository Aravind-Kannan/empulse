"""Notion-sourced ERA evidence items (ERA Step 06)."""

from __future__ import annotations

from app.services.integration_telemetry import (
    get_notion_employee_signals,
    get_notion_expertise_warnings,
    has_notion_sync,
)
from app.services.notion_telemetry import STALE_RUNBOOK_DAYS


def build_notion_evidence_items(
    employee_id: str,
    employee_name: str,
    *,
    notion_connected: bool,
    component_names: dict[str, str] | None = None,
) -> list[dict]:
    if not notion_connected or not has_notion_sync():
        return []

    signals = get_notion_employee_signals(employee_id)
    if not signals:
        return []

    items: list[dict] = []
    component_names = component_names or {}

    if signals.components_without_docs > 0:
        items.append(
            _evidence_item(
                employee_id=employee_id,
                suffix="no-runbook",
                dimension="documentation",
                severity="high" if signals.components_without_docs >= 2 else "medium",
                title=(
                    f"{signals.components_without_docs} owned components lack Notion runbooks"
                ),
                description=(
                    f"{employee_name} owns {signals.components_without_docs} components "
                    "with recent GitHub activity but no linked Notion documentation."
                ),
                impact_points=min(36.0, signals.components_without_docs * 12.0),
            )
        )

    if signals.stale_runbook_count > 0:
        items.append(
            _evidence_item(
                employee_id=employee_id,
                suffix="stale-runbook",
                dimension="documentation",
                severity="high" if signals.stale_runbook_count >= 2 else "medium",
                title=(
                    f"{signals.stale_runbook_count} stale runbooks "
                    f"(>{STALE_RUNBOOK_DAYS} days)"
                ),
                description=(
                    f"{employee_name} maintains {signals.stale_runbook_count} runbooks "
                    f"not updated in the last {STALE_RUNBOOK_DAYS} days on active components."
                ),
                impact_points=min(25.0, signals.stale_runbook_count * 5.0),
            )
        )

    if signals.sole_critical_runbook_count > 0:
        items.append(
            _evidence_item(
                employee_id=employee_id,
                suffix="sole-runbook-author",
                dimension="documentation",
                severity="medium",
                title=(
                    f"Only author of {signals.sole_critical_runbook_count} critical runbooks"
                ),
                description=(
                    f"{employee_name} is the sole documented owner for "
                    f"{signals.sole_critical_runbook_count} component runbooks."
                ),
                impact_points=min(20.0, signals.sole_critical_runbook_count * 8.0),
            )
        )

    if signals.undocumented_solved_incidents > 0:
        items.append(
            _evidence_item(
                employee_id=employee_id,
                suffix="undocumented-incidents",
                dimension="documentation",
                severity="medium",
                title=(
                    f"{signals.undocumented_solved_incidents} undocumented solved incidents"
                ),
                description=(
                    f"{employee_name} participates in incident response but owns "
                    f"{signals.undocumented_solved_incidents} components without authored docs."
                ),
                impact_points=min(30.0, signals.undocumented_solved_incidents * 10.0),
            )
        )

    for warning in get_notion_expertise_warnings():
        if warning.get("employee_id") != employee_id:
            continue
        component_name = warning.get("component_name") or component_names.get(
            warning.get("component_id", ""),
            "critical component",
        )
        tag = warning.get("tag", "topic")
        items.append(
            _evidence_item(
                employee_id=employee_id,
                suffix=f"sole-expert-{tag}",
                dimension="knowledge",
                severity="high",
                title=f"Sole Notion expertise tag for {component_name}",
                description=(
                    f"{employee_name} is the only person tagged with '{tag}' "
                    f"for tier-1 component {component_name}."
                ),
                impact_points=18.0,
            )
        )

    items.sort(key=lambda row: row["impact_points"], reverse=True)
    return items


def merge_notion_evidence(
    employee_id: str,
    employee_name: str,
    base_evidence: list[dict],
    *,
    notion_connected: bool,
    component_names: dict[str, str] | None = None,
    limit: int = 5,
) -> list[dict]:
    notion_items = build_notion_evidence_items(
        employee_id,
        employee_name,
        notion_connected=notion_connected,
        component_names=component_names,
    )
    if not notion_items:
        return base_evidence[:limit]

    merged = notion_items + [
        item
        for item in base_evidence
        if not (
            item.get("synthetic")
            and item.get("dimension") == "documentation"
            and item.get("sources")
            and item["sources"][0].get("provider") in {"notion", "slack"}
        )
    ]
    merged.sort(key=lambda row: row["impact_points"], reverse=True)
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in merged:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        deduped.append(item)
    return deduped[:limit]


def _evidence_item(
    *,
    employee_id: str,
    suffix: str,
    dimension: str,
    severity: str,
    title: str,
    description: str,
    impact_points: float,
    url: str | None = None,
) -> dict:
    return {
        "id": f"{employee_id}-notion-{suffix}",
        "dimension": dimension,
        "severity": severity,
        "title": title,
        "description": description,
        "impact_points": round(impact_points, 1),
        "sources": [
            {
                "provider": "notion",
                "label": title,
                "url": url,
            }
        ],
        "synthetic": False,
    }
