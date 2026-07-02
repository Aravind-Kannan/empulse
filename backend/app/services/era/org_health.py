"""Organization health composite score (ERA Step 18)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.operational import DoaFileSnapshot, Employee, FileRiskSnapshot
from app.services.integration_telemetry import get_all_bus_factors
from app.services.role_utils import is_leadership_role

SMALL_TEAM_THRESHOLD = 3


@dataclass(frozen=True)
class OrgHealthResult:
    score: float
    caution_small_team: bool
    bus_factor_score: float
    single_author_score: float
    knowledge_spread_score: float
    activity_diversity_score: float


def _gini(values: list[float]) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return 0.0
    sorted_values = sorted(values)
    total = sum(sorted_values)
    if total <= 0:
        return 0.0
    n = len(sorted_values)
    weighted = sum((i + 1) * value for i, value in enumerate(sorted_values))
    return (2 * weighted) / (n * total) - (n + 1) / n


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def compute_org_health(db: Session, tenant_id: uuid.UUID) -> OrgHealthResult:
    team = [
        employee
        for employee in db.query(Employee)
        .filter(Employee.tenant_id == tenant_id, Employee.active.is_(True))
        .all()
        if not is_leadership_role(employee.role)
    ]
    team_size = len(team)
    caution_small_team = team_size < SMALL_TEAM_THRESHOLD

    bus_factors = get_all_bus_factors()
    if bus_factors:
        avg_bus = sum(bus_factors.values()) / len(bus_factors)
        bus_factor_score = _clamp_score((avg_bus / 4.0) * 100)
    else:
        file_rows = (
            db.query(FileRiskSnapshot.bus_factor)
            .filter(FileRiskSnapshot.tenant_id == tenant_id)
            .all()
        )
        if file_rows:
            avg_bus = sum(row[0] for row in file_rows) / len(file_rows)
            bus_factor_score = _clamp_score((avg_bus / 4.0) * 100)
        else:
            bus_factor_score = 50.0

    file_rows = (
        db.query(FileRiskSnapshot.bus_factor)
        .filter(FileRiskSnapshot.tenant_id == tenant_id)
        .all()
    )
    if file_rows:
        single_author_rate = sum(1 for (bus_factor,) in file_rows if bus_factor <= 1) / len(
            file_rows
        )
        single_author_score = _clamp_score((1.0 - single_author_rate) * 100)
    else:
        single_author_score = 50.0

    doa_rows = (
        db.query(DoaFileSnapshot.employee_id, DoaFileSnapshot.doa_score)
        .filter(DoaFileSnapshot.tenant_id == tenant_id)
        .all()
    )
    totals: dict[str, float] = {}
    for employee_id, doa_score in doa_rows:
        totals[employee_id] = totals.get(employee_id, 0.0) + doa_score
    active_ids = {employee.id for employee in team}
    active_totals = [value for key, value in totals.items() if key in active_ids]
    if len(active_totals) >= 2:
        gini = _gini(active_totals)
        knowledge_spread_score = _clamp_score((1.0 - gini) * 100)
    else:
        knowledge_spread_score = 50.0

    now = datetime.now(UTC)
    cutoff = now - timedelta(days=90)
    recent_contributors = {
        employee_id
        for employee_id, last_touch in (
            db.query(DoaFileSnapshot.employee_id, DoaFileSnapshot.last_touch_at)
            .filter(DoaFileSnapshot.tenant_id == tenant_id)
            .all()
        )
        if employee_id in active_ids
        and last_touch is not None
        and (
            last_touch.replace(tzinfo=UTC)
            if last_touch.tzinfo is None
            else last_touch.astimezone(UTC)
        )
        >= cutoff
    }
    if team_size > 0:
        activity_diversity_score = _clamp_score(
            (len(recent_contributors) / team_size) * 100
        )
    else:
        activity_diversity_score = 0.0

    score = _clamp_score(
        0.25 * bus_factor_score
        + 0.25 * single_author_score
        + 0.25 * knowledge_spread_score
        + 0.25 * activity_diversity_score
    )
    return OrgHealthResult(
        score=score,
        caution_small_team=caution_small_team,
        bus_factor_score=bus_factor_score,
        single_author_score=single_author_score,
        knowledge_spread_score=knowledge_spread_score,
        activity_diversity_score=activity_diversity_score,
    )
