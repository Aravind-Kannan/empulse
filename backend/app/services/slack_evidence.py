"""Slack-sourced ERA evidence items with thread URLs only (ERA Step 07)."""

from __future__ import annotations

from app.services.integration_telemetry import (
    get_slack_employee_signals,
    get_slack_escalation_warnings,
    has_slack_sync,
)


def build_slack_evidence_items(
    employee_id: str,
    employee_name: str,
    *,
    slack_connected: bool,
) -> list[dict]:
    if not slack_connected or not has_slack_sync():
        return []

    signals = get_slack_employee_signals(employee_id)
    if not signals:
        return []

    items: list[dict] = []

    for evidence in signals.thread_evidence:
        if evidence.kind == "undocumented":
            items.append(
                _evidence_item(
                    employee_id=employee_id,
                    suffix=f"undocumented-{evidence.thread_url[-12:]}",
                    dimension="documentation",
                    severity="medium",
                    title=f"Resolved incident in #{evidence.channel_name} without runbook update",
                    description=(
                        f"{employee_name} resolved an incident thread "
                        f"('{evidence.title}') with no Notion runbook update within 7 days."
                    ),
                    impact_points=12.0,
                    url=evidence.thread_url,
                )
            )
        elif evidence.kind == "on_call":
            items.append(
                _evidence_item(
                    employee_id=employee_id,
                    suffix=f"oncall-{evidence.thread_url[-12:]}",
                    dimension="operational",
                    severity="medium",
                    title=f"On-call incident in #{evidence.channel_name}",
                    description=(
                        f"{employee_name} participated in an on-call incident thread "
                        f"('{evidence.title}')."
                    ),
                    impact_points=10.0,
                    url=evidence.thread_url,
                )
            )
        elif evidence.kind == "escalation":
            items.append(
                _evidence_item(
                    employee_id=employee_id,
                    suffix="escalation-shadow",
                    dimension="structural",
                    severity="high",
                    title=evidence.title,
                    description=(
                        f"{employee_name} is the repeated escalation target across "
                        "incident threads for a critical component."
                    ),
                    impact_points=22.0,
                    url=evidence.thread_url,
                )
            )
        elif evidence.kind == "sole_responder":
            items.append(
                _evidence_item(
                    employee_id=employee_id,
                    suffix=f"sole-{evidence.thread_url[-12:]}",
                    dimension="documentation",
                    severity="medium",
                    title=f"Sole responder in #{evidence.channel_name} incident thread",
                    description=(
                        f"{employee_name} was the only human responder in "
                        f"'{evidence.title}'."
                    ),
                    impact_points=8.0,
                    url=evidence.thread_url,
                )
            )

    if signals.on_call_incidents_30d >= 3 and not any(
        item["title"].startswith("On-call") for item in items
    ):
        items.append(
            _evidence_item(
                employee_id=employee_id,
                suffix="oncall-load",
                dimension="operational",
                severity="high" if signals.on_call_incidents_30d >= 5 else "medium",
                title=f"{signals.on_call_incidents_30d} on-call incidents in 30 days",
                description=(
                    f"{employee_name} participated in "
                    f"{signals.on_call_incidents_30d} on-call incident threads "
                    "in the last 30 days."
                ),
                impact_points=min(30.0, signals.on_call_incidents_30d * 6.0),
                url=_first_thread_url(signals),
            )
        )

    if signals.on_call_off_hours_messages >= 5:
        items.append(
            _evidence_item(
                employee_id=employee_id,
                suffix="after-hours",
                dimension="burnout",
                severity="medium",
                title="High after-hours Slack activity in on-call channels",
                description=(
                    f"{employee_name} posted {signals.on_call_off_hours_messages} "
                    "after-hours messages in on-call channels."
                ),
                impact_points=min(18.0, signals.on_call_off_hours_messages * 2.0),
                url=_first_thread_url(signals),
            )
        )

    for warning in get_slack_escalation_warnings():
        if warning.get("employee_id") != employee_id:
            continue
        if any(item.get("id", "").endswith("escalation-shadow") for item in items):
            continue
        items.append(
            _evidence_item(
                employee_id=employee_id,
                suffix="escalation-shadow",
                dimension="structural",
                severity="high",
                title=(
                    f"Last {warning.get('mention_count', 0)} "
                    f"#incidents threads escalated to {employee_name}"
                ),
                description=(
                    f"{employee_name} was @mentioned in "
                    f"{warning.get('mention_count', 0)} of "
                    f"{warning.get('thread_total', 0)} incident threads "
                    f"({warning.get('concentration_pct', 0)}% concentration)."
                ),
                impact_points=22.0,
                url=_first_thread_url(signals),
            )
        )

    items.sort(key=lambda row: row["impact_points"], reverse=True)
    return items


def merge_slack_evidence(
    employee_id: str,
    employee_name: str,
    base_evidence: list[dict],
    *,
    slack_connected: bool,
    limit: int = 5,
) -> list[dict]:
    slack_items = build_slack_evidence_items(
        employee_id,
        employee_name,
        slack_connected=slack_connected,
    )
    if not slack_items:
        return base_evidence[:limit]

    merged = slack_items + [
        item
        for item in base_evidence
        if not (
            item.get("synthetic")
            and item.get("dimension") in {"documentation", "operational", "structural", "burnout"}
            and item.get("sources")
            and item["sources"][0].get("provider") in {"slack", "notion"}
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


def _first_thread_url(signals) -> str | None:
    if signals.thread_evidence:
        return signals.thread_evidence[0].thread_url
    return None


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
        "id": f"{employee_id}-slack-{suffix}",
        "dimension": dimension,
        "severity": severity,
        "title": title,
        "description": description,
        "impact_points": round(impact_points, 1),
        "sources": [
            {
                "provider": "slack",
                "label": title,
                "url": url,
            }
        ],
        "synthetic": False,
    }
