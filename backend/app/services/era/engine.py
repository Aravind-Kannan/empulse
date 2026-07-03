"""Score a single employee from signals through all ERA v2 dimensions."""

from __future__ import annotations

from app.services.era.composite import (
    compute_composite,
    compute_recovery_estimate_weeks,
    risk_level,
)
from app.services.era.dimensions import (
    compute_burnout,
    compute_documentation,
    compute_knowledge,
    compute_operational,
    compute_structural,
)
from app.services.era.dimension_summaries import build_dimension_summaries
from app.services.era.evidence import build_evidence_items
from app.services.era.normalize import TenantPercentiles
from app.services.era.signals import EmployeeSignals
from app.services.era.types import DIMENSION_KEYS, DimensionKey, EraScoreResult, RoleProfile
from app.services.role_utils import is_leadership_role


def score_employee(
    signals: EmployeeSignals,
    tenant_stats: TenantPercentiles,
    *,
    role_profile: RoleProfile | None = None,
    evidence_limit: int = 5,
) -> EraScoreResult:
    if is_leadership_role(signals.role):
        return EraScoreResult(
            dimensions={key: 0.0 for key in DIMENSION_KEYS},
            composite=0.0,
            risk_level="low",
            excluded=True,
            exclusion_reason="leadership_role",
            evidence=[],
        )

    dimension_results = [
        compute_knowledge(signals, tenant_stats),
        compute_operational(signals, tenant_stats),
        compute_documentation(signals),
        compute_structural(signals),
        compute_burnout(signals, tenant_stats),
    ]

    if dimension_results[3].excluded:
        return EraScoreResult(
            dimensions={key: 0.0 for key in DIMENSION_KEYS},
            composite=0.0,
            risk_level="low",
            excluded=True,
            exclusion_reason="structural_leadership",
            evidence=[],
        )

    dimensions: dict[DimensionKey, float] = {
        result.key: result.score for result in dimension_results
    }
    partial_dimensions: dict[DimensionKey, bool] = {
        result.key: result.partial
        for result in dimension_results
        if result.partial
    }

    composite, pre_cap = compute_composite(
        dimensions,
        signals,
        role_profile=role_profile,
        partial_dimensions=partial_dimensions,
    )
    all_evidence = build_evidence_items(
        signals.employee_id, dimension_results, limit=1000
    )
    evidence = all_evidence[:evidence_limit]
    burnout_score = dimensions["burnout"]

    return EraScoreResult(
        dimensions=dimensions,
        composite=composite,
        risk_level=risk_level(composite),
        evidence=evidence,
        all_evidence=all_evidence,
        evidence_total_count=len(all_evidence),
        departure_watchlist=burnout_score > 60,
        pre_cap_score=pre_cap,
        recovery_estimate_weeks=compute_recovery_estimate_weeks(
            signals,
            dimensions["knowledge"],
            dimensions["documentation"],
        ),
        partial_dimensions=partial_dimensions,
        dimension_summaries=build_dimension_summaries(dimension_results),
    )
