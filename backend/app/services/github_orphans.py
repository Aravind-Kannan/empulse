"""Orphan file detection and departure baselines (ERA Step 18)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.operational import (
    DoaFileSnapshot,
    Employee,
    EraDepartureOrphanBaseline,
    EraTeamHealthSnapshot,
)
from app.services.github_doa import DOA_AUTHOR_THRESHOLD

ORPHAN_DOA_THRESHOLD = DOA_AUTHOR_THRESHOLD
RECENT_OWNER_WINDOW_DAYS = 90
PRIOR_ACTIVITY_WINDOW_DAYS = 365


@dataclass(frozen=True)
class OrphanFile:
    component_id: str
    file_path: str
    former_employee_id: str | None = None


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def get_active_employee_ids(db: Session, tenant_id: uuid.UUID) -> set[str]:
    rows = (
        db.query(Employee.id)
        .filter(Employee.tenant_id == tenant_id, Employee.active.is_(True))
        .all()
    )
    return {row[0] for row in rows}


def _file_groups(
    db: Session,
    tenant_id: uuid.UUID,
) -> dict[tuple[str, str], list[DoaFileSnapshot]]:
    rows = (
        db.query(DoaFileSnapshot)
        .filter(DoaFileSnapshot.tenant_id == tenant_id)
        .all()
    )
    grouped: dict[tuple[str, str], list[DoaFileSnapshot]] = defaultdict(list)
    for row in rows:
        grouped[(row.component_id, row.file_path)].append(row)
    return grouped


def list_orphan_files(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    repo_allowlist: list[str] | None = None,
) -> list[OrphanFile]:
    if repo_allowlist is not None and len(repo_allowlist) == 0:
        return []

    now = datetime.now(UTC)
    activity_cutoff = now - timedelta(days=PRIOR_ACTIVITY_WINDOW_DAYS)
    owner_cutoff = now - timedelta(days=RECENT_OWNER_WINDOW_DAYS)
    active_ids = get_active_employee_ids(db, tenant_id)
    grouped = _file_groups(db, tenant_id)

    orphans: list[OrphanFile] = []
    for (component_id, file_path), snapshots in grouped.items():
        touches = [row.last_touch_at for row in snapshots if row.last_touch_at]
        if not touches:
            continue
        last_touch = max(_aware(touch) for touch in touches)
        if last_touch < activity_cutoff:
            continue

        has_active_owner = False
        former_owner_id: str | None = None
        for row in snapshots:
            if row.employee_id not in active_ids:
                if row.doa_score >= ORPHAN_DOA_THRESHOLD:
                    former_owner_id = row.employee_id
                continue
            if row.doa_score < ORPHAN_DOA_THRESHOLD:
                continue
            if row.last_touch_at and _aware(row.last_touch_at) >= owner_cutoff:
                has_active_owner = True
                break

        if not has_active_owner:
            orphans.append(
                OrphanFile(
                    component_id=component_id,
                    file_path=file_path,
                    former_employee_id=former_owner_id,
                )
            )
    return orphans


def count_orphan_files(db: Session, tenant_id: uuid.UUID) -> int:
    return len(list_orphan_files(db, tenant_id))


def snapshot_departure_orphan_baseline(
    db: Session,
    tenant_id: uuid.UUID,
    employee_id: str,
) -> int:
    """Snapshot sole-author files when an employee is marked inactive."""
    grouped = _file_groups(db, tenant_id)
    now = datetime.now(UTC)
    created = 0

    for (component_id, file_path), snapshots in grouped.items():
        high_doa = [
            row
            for row in snapshots
            if row.employee_id == employee_id and row.doa_score >= ORPHAN_DOA_THRESHOLD
        ]
        if not high_doa:
            continue
        other_high_doa = [
            row
            for row in snapshots
            if row.employee_id != employee_id and row.doa_score >= ORPHAN_DOA_THRESHOLD
        ]
        if other_high_doa:
            continue

        top_score = max(row.doa_score for row in high_doa)
        existing = (
            db.query(EraDepartureOrphanBaseline)
            .filter(
                EraDepartureOrphanBaseline.tenant_id == tenant_id,
                EraDepartureOrphanBaseline.employee_id == employee_id,
                EraDepartureOrphanBaseline.component_id == component_id,
                EraDepartureOrphanBaseline.file_path == file_path,
            )
            .one_or_none()
        )
        if existing:
            continue

        db.add(
            EraDepartureOrphanBaseline(
                tenant_id=tenant_id,
                employee_id=employee_id,
                component_id=component_id,
                file_path=file_path,
                doa_score=top_score,
                snapshotted_at=now,
            )
        )
        created += 1
    return created


def count_departure_orphan_delta(db: Session, tenant_id: uuid.UUID) -> int:
    """Files from departure baselines that are currently orphaned."""
    baselines = (
        db.query(EraDepartureOrphanBaseline)
        .filter(EraDepartureOrphanBaseline.tenant_id == tenant_id)
        .all()
    )
    if not baselines:
        return 0
    orphan_keys = {
        (item.component_id, item.file_path)
        for item in list_orphan_files(db, tenant_id)
    }
    return sum(
        1
        for row in baselines
        if (row.component_id, row.file_path) in orphan_keys
    )


def orphan_delta_90d(db: Session, tenant_id: uuid.UUID) -> int:
    today = datetime.now(UTC).date()
    current_count = count_orphan_files(db, tenant_id)
    baseline_row = (
        db.query(EraTeamHealthSnapshot)
        .filter(
            EraTeamHealthSnapshot.tenant_id == tenant_id,
            EraTeamHealthSnapshot.snapshot_date <= today - timedelta(days=90),
        )
        .order_by(EraTeamHealthSnapshot.snapshot_date.desc())
        .first()
    )
    if baseline_row is None:
        return 0
    return current_count - baseline_row.orphan_file_count


def build_orphan_evidence_items(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    limit: int = 5,
) -> list[dict]:
    """Team-level orphan evidence for ERA feeds."""
    baselines = (
        db.query(EraDepartureOrphanBaseline)
        .filter(EraDepartureOrphanBaseline.tenant_id == tenant_id)
        .order_by(EraDepartureOrphanBaseline.snapshotted_at.desc())
        .all()
    )
    if not baselines:
        return []

    by_employee: dict[str, list[EraDepartureOrphanBaseline]] = defaultdict(list)
    for row in baselines:
        by_employee[row.employee_id].append(row)

    orphan_keys = {
        (item.component_id, item.file_path)
        for item in list_orphan_files(db, tenant_id)
    }

    items: list[dict] = []
    for employee_id, rows in by_employee.items():
        orphaned_paths = [
            row.file_path
            for row in rows
            if (row.component_id, row.file_path) in orphan_keys
        ]
        if not orphaned_paths:
            continue
        employee = (
            db.query(Employee)
            .filter(Employee.tenant_id == tenant_id, Employee.id == employee_id)
            .one_or_none()
        )
        name = employee.name if employee else employee_id
        sample = ", ".join(orphaned_paths[:3])
        items.append(
            {
                "id": f"orphan-departure-{employee_id}",
                "dimension": "structural",
                "severity": "high",
                "title": f"{len(orphaned_paths)} files became orphaned after departure",
                "description": (
                    f"{len(orphaned_paths)} files became orphaned after {name} departure. "
                    f"Affected: {sample}"
                ),
                "impact_points": min(100.0, 18.0 + len(orphaned_paths) * 2.0),
                "sources": [],
                "synthetic": False,
            }
        )
        if len(items) >= limit:
            break
    return items
