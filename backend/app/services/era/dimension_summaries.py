"""Build per-dimension headline summaries from scoring factors."""

from __future__ import annotations

from app.services.era.types import DIMENSION_KEYS, DimensionFactor, DimensionKey, DimensionResult

PARTIAL_CONNECT_HINTS: dict[DimensionKey, str] = {
    "knowledge": "Sync GitHub for ownership and review signals",
    "operational": "Sync Jira for backlog and incident load",
    "documentation": "Sync Notion and Slack for documentation gaps",
    "structural": "Sync Slack and org chart for escalation patterns",
    "burnout": "Sync Jira and GitHub for workload trends",
}


def _factor_snippet(factor: DimensionFactor) -> str:
    if factor.impact_points <= 0:
        return ""
    label = factor.label
    value = factor.value
    if factor.key in {"ownership", "breadth"}:
        return f"{value:.0f}% {label.lower()}"
    if factor.key == "backup_review" and value > 0:
        return f"{value:.0f}% {label.lower()}"
    if value == int(value):
        return f"{label} ({int(value)})"
    return f"{label} ({value:.1f})"


def _headline_for_result(result: DimensionResult) -> str:
    ranked = sorted(
        (factor for factor in result.factors if factor.impact_points > 0),
        key=lambda factor: factor.impact_points,
        reverse=True,
    )
    snippets = [snippet for factor in ranked if (snippet := _factor_snippet(factor))]
    if snippets:
        return "; ".join(snippets[:2])
    if result.partial:
        return PARTIAL_CONNECT_HINTS.get(result.key, "Connect integrations for live signals")
    if result.score <= 0:
        return "No significant signal detected"
    return "Low contribution from available signals"


def build_dimension_summaries(
    dimension_results: list[DimensionResult],
) -> dict[str, dict]:
    summaries: dict[str, dict] = {}
    for result in dimension_results:
        if result.excluded:
            continue
        ranked_factors = sorted(
            (factor for factor in result.factors if factor.impact_points > 0),
            key=lambda factor: factor.impact_points,
            reverse=True,
        )[:3]
        summaries[result.key] = {
            "score": round(result.score, 1),
            "partial": result.partial,
            "headline": _headline_for_result(result),
            "top_factors": [
                {
                    "key": factor.key,
                    "label": factor.label,
                    "value": round(factor.value, 1),
                    "impact_points": round(factor.impact_points, 1),
                    "provider": factor.provider,
                    "synthetic": factor.synthetic,
                }
                for factor in ranked_factors
            ],
        }
    for key in DIMENSION_KEYS:
        summaries.setdefault(
            key,
            {
                "score": 0.0,
                "partial": False,
                "headline": "Not applicable",
                "top_factors": [],
            },
        )
    return summaries
