"""ERA v2 scoring types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

DimensionKey = Literal[
    "knowledge", "operational", "documentation", "structural", "burnout"
]
RoleProfile = Literal["ic", "manager", "on_call"]

DIMENSION_KEYS: tuple[DimensionKey, ...] = (
    "knowledge",
    "operational",
    "documentation",
    "structural",
    "burnout",
)


@dataclass(frozen=True)
class DimensionFactor:
    key: str
    label: str
    value: float
    impact_points: float
    provider: str = "internal"
    synthetic: bool = False


@dataclass
class DimensionResult:
    key: DimensionKey
    score: float
    factors: list[DimensionFactor] = field(default_factory=list)
    excluded: bool = False
    partial: bool = False


@dataclass
class EraScoreResult:
    dimensions: dict[DimensionKey, float]
    composite: float
    risk_level: str
    evidence: list[dict] = field(default_factory=list)
    excluded: bool = False
    exclusion_reason: str | None = None
    departure_watchlist: bool = False
    pre_cap_score: float | None = None
    recovery_estimate_weeks: dict[str, int] | None = None
    partial_dimensions: dict[DimensionKey, bool] = field(default_factory=dict)
    evidence_total_count: int = 0
    all_evidence: list[dict] = field(default_factory=list)
