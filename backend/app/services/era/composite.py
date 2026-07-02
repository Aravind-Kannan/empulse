"""Composite scoring: role weights, tenure modifier, recovery estimate."""

from __future__ import annotations

from app.services.era.signals import EmployeeSignals
from app.services.era.types import DIMENSION_KEYS, DimensionKey, RoleProfile
from app.services.role_utils import is_leadership_role

ROLE_WEIGHTS: dict[RoleProfile, dict[DimensionKey, float]] = {
    "ic": {
        "knowledge": 0.35,
        "operational": 0.25,
        "documentation": 0.20,
        "structural": 0.10,
        "burnout": 0.10,
    },
    "manager": {
        "knowledge": 0.20,
        "operational": 0.20,
        "documentation": 0.15,
        "structural": 0.30,
        "burnout": 0.15,
    },
    "on_call": {
        "knowledge": 0.30,
        "operational": 0.30,
        "documentation": 0.15,
        "structural": 0.10,
        "burnout": 0.15,
    },
}

CRITICALITY_MULTIPLIERS = {
    "tier1_revenue": 1.5,
    "tier2_core": 1.0,
    "tier3_support": 0.6,
}


def criticality_multiplier(criticality: str) -> float:
    return CRITICALITY_MULTIPLIERS.get(criticality, 1.0)


def detect_role_profile(signals: EmployeeSignals) -> RoleProfile:
    if signals.direct_reports > 0:
        return "manager"
    if signals.on_call_rotation_active:
        return "on_call"
    return "ic"


def risk_level(score: float) -> str:
    if score > 75:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def renormalize_weights(
    weights: dict[DimensionKey, float],
    partial_dimensions: dict[DimensionKey, bool],
) -> dict[DimensionKey, float]:
    adjusted = dict(weights)
    if partial_dimensions.get("knowledge"):
        knowledge_weight = adjusted.get("knowledge", 0.0)
        adjusted["knowledge"] = 0.0
        remaining_total = sum(
            value for key, value in adjusted.items() if key != "knowledge"
        ) or 1.0
        for key in adjusted:
            if key != "knowledge":
                adjusted[key] += (adjusted[key] / remaining_total) * knowledge_weight
    total = sum(adjusted.values()) or 1.0
    return {key: value / total for key, value in adjusted.items()}


def apply_tenure_modifier(
    composite: float,
    signals: EmployeeSignals,
    knowledge_score: float,
) -> float:
    tenure_months = signals.tenure_months
    if tenure_months < 6 and knowledge_score < 50:
        return composite * 0.85
    if tenure_months < 6 and knowledge_score >= 70:
        return composite * 1.10
    if tenure_months > 60 and knowledge_score > 80:
        return composite * 1.05
    return composite


def compute_recovery_estimate_weeks(
    signals: EmployeeSignals,
    knowledge_score: float,
    documentation_score: float,
) -> dict[str, int]:
    weeks_min = signals.spof_component_count * 2 + int(documentation_score // 20)
    weeks_max = (
        weeks_min + signals.owned_component_count + int(knowledge_score // 15)
    )
    return {
        "min": max(1, min(26, weeks_min)),
        "max": max(1, min(26, weeks_max)),
    }


def compute_composite(
    dimensions: dict[DimensionKey, float],
    signals: EmployeeSignals,
    *,
    role_profile: RoleProfile | None = None,
    partial_dimensions: dict[DimensionKey, bool] | None = None,
) -> tuple[float, float | None]:
    if is_leadership_role(signals.role):
        return 0.0, 0.0

    profile = role_profile or detect_role_profile(signals)
    weights = dict(ROLE_WEIGHTS[profile])
    partials = partial_dimensions or {}
    weights = renormalize_weights(weights, partials)

    raw = sum(dimensions[key] * weights[key] for key in DIMENSION_KEYS)
    modified = apply_tenure_modifier(raw, signals, dimensions["knowledge"])
    pre_cap = modified if modified > 100 else None
    return min(100.0, round(modified, 1)), pre_cap
