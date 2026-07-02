"""GitHub-sourced ERA evidence items with real PR URLs (Step 04)."""

from __future__ import annotations

from app.services.integration_telemetry import (
    get_component_bus_factor,
    get_doa_decay_evidence,
    get_employee_max_doa_pct,
    get_github_employee_context,
    get_github_ownership,
    get_team_risky_changes,
    has_doa_ownership,
    is_github_spof,
)


def build_github_evidence_items(
    employee_id: str,
    employee_name: str,
    *,
    component_names: dict[str, str],
    github_connected: bool,
) -> list[dict]:
    if not github_connected:
        return []

    context = get_github_employee_context(employee_id)
    ownership = get_github_ownership()
    use_doa = has_doa_ownership()
    items: list[dict] = []

    if use_doa:
        max_doa = get_employee_max_doa_pct(employee_id)
        if max_doa >= 50:
            items.append(
                _evidence_item(
                    employee_id=employee_id,
                    suffix="doa-max",
                    dimension="knowledge",
                    severity="high" if max_doa >= 75 else "medium",
                    title=f"{employee_name} DOA {max_doa:.0f}% on owned files",
                    description=(
                        f"Fritz et al. Degree of Authorship peaks at {max_doa:.1f}% "
                        "across mapped repository files."
                    ),
                    impact_points=min(100.0, max_doa * 0.55),
                    url=context.latest_pr_url,
                )
            )

        for decay in get_doa_decay_evidence():
            if decay["employee_id"] != employee_id:
                continue
            component_name = component_names.get(
                decay["component_id"], decay["component_id"]
            )
            items.append(
                _evidence_item(
                    employee_id=employee_id,
                    suffix=f"decay-{decay['file_path']}",
                    dimension="knowledge",
                    severity="medium",
                    title=(
                        f"Knowledge decay on {component_name} "
                        f"({decay['doa_score'] * 100:.0f}% DOA)"
                    ),
                    description=(
                        f"You haven't touched {decay['file_path']} in "
                        f"{decay['months_idle']} months despite team edits "
                        f"(decay {decay['decay_score'] * 100:.0f}%)."
                    ),
                    impact_points=18.0,
                    url=context.latest_pr_url,
                )
            )

    for component_id, contributors in ownership.items():
        pct = contributors.get(employee_id, 0.0)
        component_name = component_names.get(component_id, component_id)
        pr_url = context.top_pr_url_by_component.get(component_id)
        bus_factor = get_component_bus_factor(component_id)

        if pct > 70:
            metric = "DOA" if use_doa else "LOC"
            items.append(
                _evidence_item(
                    employee_id=employee_id,
                    suffix=f"ownership-{component_id}",
                    dimension="knowledge",
                    severity="high" if pct > 85 else "medium",
                    title=f"{employee_name} owns {pct:.0f}% of {component_name}",
                    description=(
                        f"{metric}-weighted ownership on {component_name} is {pct:.1f}% "
                        "over the last 6 months."
                    ),
                    impact_points=min(100.0, pct * 0.5),
                    url=pr_url,
                )
            )

        if is_github_spof(component_id) and employee_id in contributors:
            if contributors[employee_id] == max(contributors.values()):
                bf_note = f" Bus factor: {bus_factor}." if bus_factor is not None else ""
                items.append(
                    _evidence_item(
                        employee_id=employee_id,
                        suffix=f"spof-{component_id}",
                        dimension="knowledge",
                        severity="high",
                        title=f"Sole contributor on {component_name}",
                        description=(
                            f"{employee_name} is the dominant contributor on {component_name} "
                            f"({contributors[employee_id]:.0f}% "
                            f"{'DOA' if use_doa else 'LOC'} footprint).{bf_note}"
                        ),
                        impact_points=35.0,
                        url=pr_url,
                    )
                )

    if context.open_prs > 5:
        items.append(
            _evidence_item(
                employee_id=employee_id,
                suffix="open-prs",
                dimension="operational",
                severity="medium",
                title=f"{context.open_prs} open pull requests",
                description=f"{employee_name} has {context.open_prs} open PRs on the tracked repo.",
                impact_points=min(30.0, context.open_prs * 3.0),
                url=context.latest_pr_url,
            )
        )

    if context.backup_review_score < 30 and context.recent_pr_count > 0:
        pr_url = context.no_backup_pr_urls[0] if context.no_backup_pr_urls else context.latest_pr_url
        items.append(
            _evidence_item(
                employee_id=employee_id,
                suffix="no-backup-review",
                dimension="knowledge",
                severity="medium",
                title=f"No backup reviewer on last {context.recent_pr_count} PRs",
                description=(
                    f"Only {context.unique_reviewers} unique reviewers on "
                    f"{employee_name}'s recent pull requests "
                    f"({context.sole_reviewer_count} with sole reviewer)."
                ),
                impact_points=20.0,
                url=pr_url,
                synthetic=False,
            )
        )

    for risky in get_team_risky_changes():
        if risky.author_employee_id != employee_id:
            continue
        items.append(
            _evidence_item(
                employee_id=employee_id,
                suffix=f"risky-{risky.rule}-{risky.pr_number}",
                dimension="knowledge",
                severity=risky.severity,
                title=risky.title,
                description=risky.description,
                impact_points=risky.impact_points,
                url=risky.pr_url,
                synthetic=False,
            )
        )

    items.sort(key=lambda row: row["impact_points"], reverse=True)
    return items


def merge_github_evidence(
    employee_id: str,
    employee_name: str,
    base_evidence: list[dict],
    *,
    component_names: dict[str, str],
    github_connected: bool,
    limit: int = 5,
    db=None,
    tenant_id=None,
) -> list[dict]:
    github_items = build_github_evidence_items(
        employee_id,
        employee_name,
        component_names=component_names,
        github_connected=github_connected,
    )
    if db is not None and tenant_id is not None and github_connected:
        from app.services.github_file_risk import build_file_risk_evidence_items

        github_items = (
            build_file_risk_evidence_items(db, tenant_id, employee_id, employee_name)
            + github_items
        )
    if not github_items:
        return base_evidence[:limit]

    merged = github_items + [
        item
        for item in base_evidence
        if not (
            item.get("sources")
            and item["sources"][0].get("provider") == "github"
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
    synthetic: bool = False,
) -> dict:
    return {
        "id": f"{employee_id}-github-{suffix}",
        "dimension": dimension,
        "severity": severity,
        "title": title,
        "description": description,
        "impact_points": round(impact_points, 1),
        "sources": [
            {
                "provider": "github",
                "label": title,
                "url": url,
            }
        ],
        "synthetic": synthetic,
    }
