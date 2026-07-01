"""ERA v2 five-dimension scoring engine."""

from app.services.era.composite import (
    ROLE_WEIGHTS,
    compute_composite,
    criticality_multiplier,
    detect_role_profile,
    risk_level,
)
from app.services.era.engine import score_employee
from app.services.era.normalize import TenantPercentiles, build_tenant_percentiles
from app.services.era.signals import EmployeeSignals
from app.services.era.types import DIMENSION_KEYS, EraScoreResult

__all__ = [
    "DIMENSION_KEYS",
    "EmployeeSignals",
    "EraScoreResult",
    "ROLE_WEIGHTS",
    "TenantPercentiles",
    "build_tenant_percentiles",
    "compute_composite",
    "criticality_multiplier",
    "detect_role_profile",
    "risk_level",
    "score_employee",
]
