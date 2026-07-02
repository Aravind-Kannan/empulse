"""Jira-sourced ERA evidence items with issue URLs (Step 05)."""

from __future__ import annotations

from app.services.integration_telemetry import get_jira_employee_signals, has_jira_sync


def build_jira_evidence_items(
    employee_id: str,
    employee_name: str,
    *,
    jira_connected: bool,
) -> list[dict]:
    if not jira_connected or not has_jira_sync():
        return []

    signals = get_jira_employee_signals(employee_id)
    if not signals:
        return []

    items: list[dict] = []
    sample_url = signals.sample_issue_urls[0] if signals.sample_issue_urls else None

    if signals.open_p1_p2 >= 3:
        items.append(
            _evidence_item(
                employee_id=employee_id,
                suffix="open-p1-p2",
                dimension="operational",
                severity="high" if signals.open_p1_p2 >= 5 else "medium",
                title=f"{signals.open_p1_p2} high-priority open issues",
                description=(
                    f"{employee_name} has {signals.open_p1_p2} open P1/P2 issues in Jira."
                ),
                impact_points=min(40.0, signals.open_p1_p2 * 8.0),
                url=sample_url,
            )
        )

    if signals.jira_backlog_boost > 0:
        items.append(
            _evidence_item(
                employee_id=employee_id,
                suffix="unassigned-critical",
                dimension="operational",
                severity="high" if signals.jira_backlog_boost >= 3 else "medium",
                title=(
                    f"{signals.jira_backlog_boost} unassigned critical bugs on owned components"
                ),
                description=(
                    f"{signals.jira_backlog_boost} unassigned high-priority bugs are "
                    f"attributed to {employee_name} as the main engineer on affected components."
                ),
                impact_points=min(35.0, signals.jira_backlog_boost * 10.0),
                url=sample_url,
            )
        )

    if signals.epic_owner_count >= 2:
        items.append(
            _evidence_item(
                employee_id=employee_id,
                suffix="epic-owner",
                dimension="structural",
                severity="medium",
                title=f"Single owner of {signals.epic_owner_count} epics",
                description=(
                    f"{employee_name} is assignee on {signals.epic_owner_count} open epics."
                ),
                impact_points=min(30.0, signals.epic_owner_count * 8.0),
                url=sample_url,
            )
        )

    items.sort(key=lambda row: row["impact_points"], reverse=True)
    return items


def build_team_unassigned_p1_evidence_items(
    db,
    tenant_id,
    *,
    limit: int = 5,
) -> list[dict]:
    """Team-level unassigned P1 evidence for ERA feeds (Step 17)."""
    from app.models.operational import Component
    from app.services.integration_telemetry import get_unassigned_p1_by_component, has_jira_sync

    if not has_jira_sync():
        return []

    component_names = {
        row.id: row.name
        for row in db.query(Component).filter(Component.tenant_id == tenant_id).all()
    }
    items: list[dict] = []
    for component_id, issues in get_unassigned_p1_by_component().items():
        if not issues:
            continue
        component_name = component_names.get(component_id, component_id)
        sample_url = next((issue.issue_url for issue in issues if issue.issue_url), None)
        items.append(
            _evidence_item(
                employee_id="team",
                suffix=f"unassigned-p1-{component_id}",
                dimension="operational",
                severity="high",
                title=f"Unassigned P1 on {component_name}",
                description=(
                    f"{len(issues)} unassigned high-priority bug(s) on {component_name} "
                    "— triage ownership in Jira."
                ),
                impact_points=min(45.0, 20.0 + len(issues) * 8.0),
                url=sample_url,
            )
        )
        if len(items) >= limit:
            break
    items.sort(key=lambda row: row["impact_points"], reverse=True)
    return items


def merge_jira_evidence(
    employee_id: str,
    employee_name: str,
    base_evidence: list[dict],
    *,
    jira_connected: bool,
    limit: int = 5,
) -> list[dict]:
    jira_items = build_jira_evidence_items(
        employee_id,
        employee_name,
        jira_connected=jira_connected,
    )
    if not jira_items:
        return base_evidence[:limit]

    merged = jira_items + [
        item
        for item in base_evidence
        if not (
            item.get("sources")
            and item["sources"][0].get("provider") == "jira"
            and item.get("synthetic")
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
    url: str | None,
) -> dict:
    return {
        "id": f"{employee_id}-jira-{suffix}",
        "dimension": dimension,
        "severity": severity,
        "title": title,
        "description": description,
        "impact_points": round(impact_points, 1),
        "sources": [
            {
                "provider": "jira",
                "label": title,
                "url": url,
            }
        ],
        "synthetic": False,
    }
