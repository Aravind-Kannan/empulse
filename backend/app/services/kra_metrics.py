"""Deterministic KRA summary metrics (no Cognee scoring)."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.operational import Assignment, Component, Employee
from app.schemas.kra import (
    CriticalSpofComponent,
    CriticalSpofResult,
    KraMetricCoverage,
    KraSummaryResponse,
)
from app.services.integration_telemetry import (
    get_all_bus_factors,
    get_github_ownership,
    has_github_sync,
    hydrate_github_telemetry_from_db,
)


_KRA_SUMMARY_CACHE_TTL_SECONDS = 300.0
_kra_summary_cache: dict[uuid.UUID, tuple[float, KraSummaryResponse]] = {}


def invalidate_kra_summary_cache(tenant_id: uuid.UUID | None = None) -> None:
    if tenant_id is None:
        _kra_summary_cache.clear()
        return
    _kra_summary_cache.pop(tenant_id, None)


def _coverage_for_github() -> KraMetricCoverage:
    if has_github_sync():
        return KraMetricCoverage(github="confirmed", is_partial=False)
    return KraMetricCoverage(github="missing", is_partial=True)


def _empty_critical_spof_result(coverage: KraMetricCoverage) -> CriticalSpofResult:
    return CriticalSpofResult(count=0, components=[], data_completeness=coverage)


def _owners_by_component(
    db: Session,
    tenant_id: uuid.UUID,
) -> dict[str, set[str]]:
    owners: dict[str, set[str]] = defaultdict(set)
    assignments = (
        db.query(Assignment)
        .filter(Assignment.tenant_id == tenant_id)
        .all()
    )
    for assignment in assignments:
        owners[assignment.component_id].add(assignment.employee_id)

    if has_github_sync():
        github_ownership = get_github_ownership()
        for component_id, contributors in github_ownership.items():
            owners[component_id] = set(contributors.keys())

    return owners


def _employee_names(db: Session, tenant_id: uuid.UUID) -> dict[str, str]:
    rows = db.query(Employee).filter(Employee.tenant_id == tenant_id).all()
    return {row.id: row.name for row in rows}


def _is_critical_spof(
    *,
    criticality: str,
    component_id: str,
    owner_ids: set[str],
    bus_factors: dict[str, int],
    github_connected: bool,
) -> tuple[bool, bool]:
    if criticality != "tier1_revenue":
        return False, False

    github_verified = False
    if github_connected and bus_factors.get(component_id, 99) <= 1:
        github_verified = True
        return True, github_verified

    if len(owner_ids) <= 1:
        return True, github_verified

    return False, github_verified


def compute_critical_spof_count(
    db: Session,
    tenant_id: uuid.UUID,
) -> CriticalSpofResult:
    hydrate_github_telemetry_from_db(db, tenant_id)

    github_connected = has_github_sync()
    bus_factors = get_all_bus_factors() if github_connected else {}
    coverage = _coverage_for_github()

    employees = db.query(Employee).filter(Employee.tenant_id == tenant_id).all()
    components = db.query(Component).filter(Component.tenant_id == tenant_id).all()

    if not employees or not components:
        return _empty_critical_spof_result(coverage)

    owners_by_component = _owners_by_component(db, tenant_id)
    employee_names = _employee_names(db, tenant_id)

    critical_components: list[CriticalSpofComponent] = []
    for component in components:
        owner_ids = owners_by_component.get(component.id, set())
        is_spof, github_verified = _is_critical_spof(
            criticality=component.criticality,
            component_id=component.id,
            owner_ids=owner_ids,
            bus_factors=bus_factors,
            github_connected=github_connected,
        )
        if not is_spof:
            continue

        owner_name_list = [
            employee_names[owner_id]
            for owner_id in sorted(owner_ids)
            if owner_id in employee_names
        ]
        critical_components.append(
            CriticalSpofComponent(
                component_id=component.id,
                component_name=component.name,
                bus_factor=bus_factors.get(component.id),
                owner_count=len(owner_ids),
                owner_names=owner_name_list[:3],
                github_verified=github_verified,
                criticality=component.criticality,
            )
        )

    critical_components.sort(key=lambda row: row.component_name)
    return CriticalSpofResult(
        count=len(critical_components),
        components=critical_components,
        data_completeness=coverage,
    )


def get_kra_summary(db: Session, tenant_id: uuid.UUID) -> KraSummaryResponse:
    cached = _kra_summary_cache.get(tenant_id)
    if cached and (time.time() - cached[0]) < _KRA_SUMMARY_CACHE_TTL_SECONDS:
        return cached[1].model_copy(deep=True)

    summary = KraSummaryResponse(
        critical_spof=compute_critical_spof_count(db, tenant_id),
    )
    _kra_summary_cache[tenant_id] = (time.time(), summary)
    return summary.model_copy(deep=True)
