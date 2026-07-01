"""Tenant percentile normalization for ERA operational signals."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.era.signals import EmployeeSignals
from app.services.era.types import DIMENSION_KEYS, DimensionKey


@dataclass
class TenantPercentiles:
    p90: dict[str, float] = field(default_factory=dict)
    employee_count: int = 0


NORMALIZED_KEYS = (
    "unresolved_issues",
    "open_tasks",
    "open_prs",
    "on_call_incidents_30d",
    "sprint_points",
    "after_hours_commits",
    "on_call_off_hours_messages",
)


def _percentile_90(values: list[float]) -> float:
    if not values:
        return 1.0
    if len(values) == 1:
        return max(values[0], 1.0)
    sorted_values = sorted(values)
    index = int(round(0.9 * (len(sorted_values) - 1)))
    return max(sorted_values[index], 1.0)


def build_tenant_percentiles(signals_list: list[EmployeeSignals]) -> TenantPercentiles:
    stats: dict[str, list[float]] = {key: [] for key in NORMALIZED_KEYS}
    for signals in signals_list:
        stats["unresolved_issues"].append(float(signals.unresolved_issues))
        stats["open_tasks"].append(float(signals.open_tasks))
        stats["open_prs"].append(float(signals.open_prs))
        stats["on_call_incidents_30d"].append(float(signals.on_call_incidents_30d))
        stats["sprint_points"].append(float(signals.sprint_points))
        stats["after_hours_commits"].append(float(signals.after_hours_commits))
        stats["on_call_off_hours_messages"].append(
            float(signals.on_call_off_hours_messages)
        )

    return TenantPercentiles(
        p90={key: _percentile_90(values) for key, values in stats.items()},
        employee_count=len(signals_list),
    )


def normalize_value(
    value: float,
    tenant_stats: TenantPercentiles,
    key: str,
) -> float:
    if tenant_stats.employee_count <= 1:
        return min(100.0, value)
    p90 = max(tenant_stats.p90.get(key, 1.0), 1.0)
    return min(100.0, (value / p90) * 100.0)


def absolute_operational_norm(value: float, scale: float) -> float:
    """Fallback when percentile cache is empty or single-employee tenant."""
    return min(100.0, value * scale)
