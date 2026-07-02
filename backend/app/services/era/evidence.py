"""Build ranked ERA evidence items from dimension factors."""

from __future__ import annotations

from app.services.era.types import DimensionFactor, DimensionKey, DimensionResult

SEVERITY_HIGH = 15.0
SEVERITY_MEDIUM = 8.0


def _severity(impact_points: float) -> str:
    if impact_points >= SEVERITY_HIGH:
        return "high"
    if impact_points >= SEVERITY_MEDIUM:
        return "medium"
    return "low"


def _factor_to_evidence(
    employee_id: str,
    dimension: DimensionKey,
    factor: DimensionFactor,
    index: int,
) -> dict:
    return {
        "id": f"{employee_id}-{dimension}-{factor.key}-{index}",
        "dimension": dimension,
        "severity": _severity(factor.impact_points),
        "title": factor.label,
        "description": (
            f"{factor.label} contributed {factor.impact_points:.1f} impact points "
            f"(signal value: {factor.value:.1f})."
        ),
        "impact_points": round(factor.impact_points, 1),
        "sources": [
            {
                "provider": factor.provider,
                "label": factor.label,
                "url": None,
            }
        ],
        "synthetic": factor.synthetic,
    }


def build_evidence_items(
    employee_id: str,
    dimension_results: list[DimensionResult],
    *,
    limit: int = 5,
) -> list[dict]:
    candidates: list[dict] = []
    for result in dimension_results:
        if result.excluded:
            continue
        for index, factor in enumerate(result.factors):
            if factor.impact_points <= 0:
                continue
            candidates.append(
                _factor_to_evidence(employee_id, result.key, factor, index)
            )

    candidates.sort(key=lambda item: item["impact_points"], reverse=True)
    return candidates[:limit]
