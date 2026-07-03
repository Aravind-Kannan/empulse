"""Degree of Authorship (DOA) — Fritz et al. model for GitHub file ownership (Step 14)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.operational import Assignment, Component, DoaFileSnapshot, Employee
from app.services.github_code import GitHubCodeFileSnapshot
from app.services.github_types import GitHubCommitActivity, GitHubPullRequestActivity
from app.services.github_touch import FileTouch, build_file_touch_indexes, events_to_doa_touches
from app.services.identity_resolver import resolve_author_employee_id

DOA_AUTHOR_THRESHOLD = 0.75
FA_WEIGHT = 0.4
DL_WEIGHT = 0.3
AC_WEIGHT = 0.3
MAX_FILES_PER_COMPONENT = 500
BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".jar",
    ".woff",
    ".woff2",
    ".ico",
    ".bin",
}
VENDOR_PREFIXES = ("vendor/", "node_modules/", "third_party/", "dist/", "build/")


@dataclass
class DoaContributorScore:
    employee_id: str
    doa_score: float
    is_author: bool
    last_touch_at: datetime | None
    decay_score: float


@dataclass
class DoaComputationResult:
    snapshots: list[DoaFileSnapshot] = field(default_factory=list)
    ownership: dict[str, dict[str, float]] = field(default_factory=dict)
    bus_factor_by_component: dict[str, int] = field(default_factory=dict)
    employee_max_doa_pct: dict[str, float] = field(default_factory=dict)
    decay_evidence: list[dict] = field(default_factory=list)


def _parse_merged_at(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _should_exclude_path(path: str) -> bool:
    normalized = path.lower().lstrip("/")
    if any(normalized.endswith(ext) for ext in BINARY_EXTENSIONS):
        return True
    return any(normalized.startswith(prefix) for prefix in VENDOR_PREFIXES)


def should_exclude_repo_path(path: str) -> bool:
    """Skip vendor trees and binary blobs during full-repository walks."""
    return _should_exclude_path(path)


def _fritz_doa_score(
    *,
    is_first_author: bool,
    deliveries: int,
    max_deliveries: int,
    acceptances: int,
    max_acceptances: int,
) -> float:
    fa = 1.0 if is_first_author else 0.0
    dl_norm = deliveries / max_deliveries if max_deliveries else 0.0
    ac_norm = acceptances / max_acceptances if max_acceptances else 0.0
    return min(1.0, FA_WEIGHT * fa + DL_WEIGHT * dl_norm + AC_WEIGHT * ac_norm)


def _compute_acceptances(touches: list[FileTouch]) -> dict[str, int]:
    """Changes by others since each contributor's last touch (knowledge decay input)."""
    acceptances: dict[str, int] = defaultdict(int)
    last_touch_index: dict[str, int] = {}

    for index, touch in enumerate(touches):
        employee_id = touch.employee_id
        prev = last_touch_index.get(employee_id)
        if prev is not None:
            for prior in touches[prev + 1 : index]:
                if prior.employee_id != employee_id:
                    acceptances[employee_id] += 1
        last_touch_index[employee_id] = index

    for employee_id, last_index in last_touch_index.items():
        for later in touches[last_index + 1 :]:
            if later.employee_id != employee_id:
                acceptances[employee_id] += 1

    return acceptances


def _decay_score(touches: list[FileTouch], employee_id: str) -> float:
    if not touches:
        return 0.0
    last_index = max(
        (index for index, touch in enumerate(touches) if touch.employee_id == employee_id),
        default=-1,
    )
    if last_index < 0:
        return 0.0
    since = touches[last_index + 1 :]
    if not since:
        return 0.0
    others = sum(1 for touch in since if touch.employee_id != employee_id)
    return others / len(since)


def compute_doa_for_file(
    touches: list[FileTouch],
) -> list[DoaContributorScore]:
    if not touches:
        return []

    deliveries: dict[str, int] = defaultdict(int)
    first_author = touches[0].employee_id
    last_touch: dict[str, datetime] = {}

    for touch in touches:
        deliveries[touch.employee_id] += 1
        last_touch[touch.employee_id] = touch.touched_at

    acceptances = _compute_acceptances(touches)
    max_deliveries = max(deliveries.values()) if deliveries else 1
    max_acceptances = max(acceptances.values()) if acceptances else 1

    scores: list[DoaContributorScore] = []
    for employee_id, count in deliveries.items():
        doa = _fritz_doa_score(
            is_first_author=employee_id == first_author,
            deliveries=count,
            max_deliveries=max_deliveries,
            acceptances=acceptances.get(employee_id, 0),
            max_acceptances=max_acceptances,
        )
        scores.append(
            DoaContributorScore(
                employee_id=employee_id,
                doa_score=round(doa, 4),
                is_author=doa >= DOA_AUTHOR_THRESHOLD,
                last_touch_at=last_touch.get(employee_id),
                decay_score=round(_decay_score(touches, employee_id), 4),
            )
        )
    return scores


def compute_bus_factor(authoritative_by_file: dict[str, list[str]]) -> int:
    """Minimum authoritative authors (DOA > 0.75) to cover >50% of files."""
    if not authoritative_by_file:
        return 0

    files = list(authoritative_by_file.keys())
    target = (len(files) // 2) + 1
    author_files: dict[str, set[str]] = defaultdict(set)
    for file_path, authors in authoritative_by_file.items():
        for author in authors:
            author_files[author].add(file_path)

    covered: set[str] = set()
    bus_factor = 0
    remaining = dict(author_files)
    while len(covered) < target and remaining:
        best_author = max(
            remaining,
            key=lambda author: len(remaining[author] - covered),
        )
        covered |= remaining.pop(best_author)
        bus_factor += 1
    return bus_factor


def _blame_line_weights_by_login(snap: GitHubCodeFileSnapshot) -> dict[str, int]:
    weights: dict[str, int] = defaultdict(int)
    for row in snap.blame_ranges:
        login = (row.author_login or "").strip()
        if not login or login.lower() == "unknown":
            continue
        lines = max(1, row.ending_line - row.starting_line + 1)
        weights[login] += lines
    return dict(weights)


def dominant_blame_author_login(snap: GitHubCodeFileSnapshot) -> str | None:
    """Author with the most blamed lines in a file snapshot."""
    weights = _blame_line_weights_by_login(snap)
    if not weights:
        return snap.primary_authors[0] if snap.primary_authors else None
    return max(weights, key=weights.get)


def _group_code_snapshot_blame(
    snapshots: list[GitHubCodeFileSnapshot],
) -> dict[tuple[str, str], dict[str, int]]:
    """Merge blame line weights per (component_id, file_path) across refs/branches."""
    grouped: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for snap in snapshots:
        if not snap.component_id or _should_exclude_path(snap.file_path):
            continue
        weights = _blame_line_weights_by_login(snap)
        if not weights:
            continue
        key = (snap.component_id, snap.file_path)
        for login, line_count in weights.items():
            grouped[key][login] += line_count
    return {key: dict(weights) for key, weights in grouped.items()}


def compute_doa_from_code_snapshots(
    db: Session,
    tenant_id: uuid.UUID,
    snapshots: list[GitHubCodeFileSnapshot],
) -> DoaComputationResult:
    """Build per-file DOA from git blame line ownership (full-repo sync)."""
    per_component_files: dict[str, dict[str, list[DoaContributorScore]]] = defaultdict(dict)
    employee_max_doa: dict[str, float] = defaultdict(float)
    authoritative_by_component: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    now = datetime.now(UTC)

    for (component_id, file_path), weights in _group_code_snapshot_blame(snapshots).items():
        total_lines = sum(weights.values()) or 1
        scores: list[DoaContributorScore] = []
        for login, line_count in weights.items():
            employee_id = resolve_author_employee_id(
                db,
                tenant_id,
                "github",
                f"gh-{login}",
                quarantine_event_type="github_blame",
                quarantine_payload={
                    "file_path": file_path,
                    "author_login": login,
                },
            )
            if not employee_id:
                continue
            share = line_count / total_lines
            is_author = share >= DOA_AUTHOR_THRESHOLD
            scores.append(
                DoaContributorScore(
                    employee_id=employee_id,
                    doa_score=round(share, 4),
                    is_author=is_author,
                    last_touch_at=now,
                    decay_score=0.0,
                )
            )
            employee_max_doa[employee_id] = max(
                employee_max_doa[employee_id],
                share * 100.0,
            )
            if is_author:
                authoritative_by_component[component_id][file_path].append(
                    employee_id
                )

        if scores:
            per_component_files[component_id][file_path] = scores

    ownership: dict[str, dict[str, float]] = {}
    bus_factor_by_component: dict[str, int] = {}

    for component_id, files in per_component_files.items():
        if len(files) > MAX_FILES_PER_COMPONENT:
            top_paths = sorted(
                files.keys(),
                key=lambda path: sum(score.doa_score for score in files[path]),
                reverse=True,
            )[:MAX_FILES_PER_COMPONENT]
            files = {path: files[path] for path in top_paths}

        contributor_weight: dict[str, float] = defaultdict(float)
        for file_scores in files.values():
            for score in file_scores:
                contributor_weight[score.employee_id] += score.doa_score

        total_weight = sum(contributor_weight.values()) or 1.0
        ownership[component_id] = {
            employee_id: round((weight / total_weight) * 100, 1)
            for employee_id, weight in contributor_weight.items()
        }

        auth_map = {
            path: authors
            for path, authors in authoritative_by_component.get(component_id, {}).items()
            if path in files
        }
        bus_factor_by_component[component_id] = compute_bus_factor(auth_map)

    return DoaComputationResult(
        ownership=dict(ownership),
        bus_factor_by_component=bus_factor_by_component,
        employee_max_doa_pct=dict(employee_max_doa),
        decay_evidence=[],
    )


def persist_doa_from_code_snapshots(
    db: Session,
    tenant_id: uuid.UUID,
    snapshots: list[GitHubCodeFileSnapshot],
    *,
    computed_at: datetime | None = None,
) -> DoaComputationResult:
    """Replace DOA file snapshots with blame-derived ownership from a repo walk."""
    result = compute_doa_from_code_snapshots(db, tenant_id, snapshots)
    valid_components = {
        row[0]
        for row in db.query(Component.id).filter(Component.tenant_id == tenant_id).all()
    }
    valid_employees = {
        row[0]
        for row in db.query(Employee.id).filter(Employee.tenant_id == tenant_id).all()
    }
    if not valid_employees:
        valid_employees = {
            row[0]
            for row in db.query(Assignment.employee_id)
            .filter(Assignment.tenant_id == tenant_id)
            .all()
        }

    now = computed_at or datetime.now(UTC)
    db.query(DoaFileSnapshot).filter(DoaFileSnapshot.tenant_id == tenant_id).delete(
        synchronize_session=False
    )

    persisted: list[DoaFileSnapshot] = []
    for (component_id, file_path), weights in _group_code_snapshot_blame(snapshots).items():
        if component_id not in valid_components:
            continue
        total_lines = sum(weights.values()) or 1
        for login, line_count in weights.items():
            employee_id = resolve_author_employee_id(
                db,
                tenant_id,
                "github",
                f"gh-{login}",
                quarantine_event_type="github_blame",
                quarantine_payload={
                    "file_path": file_path,
                    "author_login": login,
                },
            )
            if not employee_id or employee_id not in valid_employees:
                continue
            share = line_count / total_lines
            row = DoaFileSnapshot(
                tenant_id=tenant_id,
                component_id=component_id,
                file_path=file_path,
                employee_id=employee_id,
                doa_score=round(share, 4),
                is_author=share >= DOA_AUTHOR_THRESHOLD,
                last_touch_at=now,
                decay_score=0.0,
                computed_at=now,
            )
            db.add(row)
            persisted.append(row)

    db.flush()
    result.snapshots = persisted
    return result


def compute_doa_from_activities(
    db: Session,
    tenant_id: uuid.UUID,
    activities: list[GitHubPullRequestActivity],
    commit_activities: list[GitHubCommitActivity] | None = None,
) -> DoaComputationResult:
    """Build per-file DOA from merged PR activity and direct branch commits."""
    file_events, _ = build_file_touch_indexes(
        db, tenant_id, activities, commit_activities
    )
    file_touches = events_to_doa_touches(file_events)

    per_component_files: dict[str, dict[str, list[DoaContributorScore]]] = defaultdict(dict)
    employee_max_doa: dict[str, float] = defaultdict(float)
    authoritative_by_component: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    decay_evidence: list[dict] = []
    now = datetime.now(UTC)

    for (component_id, file_path), touches in file_touches.items():
        scores = compute_doa_for_file(touches)
        if not scores:
            continue
        per_component_files[component_id][file_path] = scores
        for score in scores:
            employee_max_doa[score.employee_id] = max(
                employee_max_doa[score.employee_id],
                score.doa_score * 100.0,
            )
            if score.is_author:
                authoritative_by_component[component_id][file_path].append(
                    score.employee_id
                )
            if score.decay_score >= 0.6 and score.doa_score >= 0.5:
                months_idle = 0
                if score.last_touch_at:
                    months_idle = max(
                        0,
                        int((now - score.last_touch_at).days / 30),
                    )
                decay_evidence.append(
                    {
                        "employee_id": score.employee_id,
                        "component_id": component_id,
                        "file_path": file_path,
                        "decay_score": score.decay_score,
                        "doa_score": score.doa_score,
                        "months_idle": months_idle,
                    }
                )

    ownership: dict[str, dict[str, float]] = {}
    bus_factor_by_component: dict[str, int] = {}

    for component_id, files in per_component_files.items():
        if len(files) > MAX_FILES_PER_COMPONENT:
            top_paths = sorted(
                files.keys(),
                key=lambda path: sum(score.doa_score for score in files[path]),
                reverse=True,
            )[:MAX_FILES_PER_COMPONENT]
            files = {path: files[path] for path in top_paths}

        contributor_weight: dict[str, float] = defaultdict(float)
        for scores in files.values():
            for score in scores:
                contributor_weight[score.employee_id] += score.doa_score

        total_weight = sum(contributor_weight.values()) or 1.0
        ownership[component_id] = {
            employee_id: round((weight / total_weight) * 100, 1)
            for employee_id, weight in contributor_weight.items()
        }

        auth_map = {
            path: authors
            for path, authors in authoritative_by_component.get(component_id, {}).items()
            if path in files
        }
        bus_factor_by_component[component_id] = compute_bus_factor(auth_map)

    return DoaComputationResult(
        ownership=dict(ownership),
        bus_factor_by_component=bus_factor_by_component,
        employee_max_doa_pct=dict(employee_max_doa),
        decay_evidence=decay_evidence,
    )


def persist_doa_snapshots(
    db: Session,
    tenant_id: uuid.UUID,
    activities: list[GitHubPullRequestActivity],
    commit_activities: list[GitHubCommitActivity] | None = None,
    *,
    computed_at: datetime | None = None,
) -> DoaComputationResult:
    result = compute_doa_from_activities(db, tenant_id, activities, commit_activities)
    valid_components = {
        row[0]
        for row in db.query(Component.id).filter(Component.tenant_id == tenant_id).all()
    }
    valid_employees = {
        row[0]
        for row in db.query(Employee.id).filter(Employee.tenant_id == tenant_id).all()
    }
    if not valid_employees:
        valid_employees = {
            row[0]
            for row in db.query(Assignment.employee_id)
            .filter(Assignment.tenant_id == tenant_id)
            .all()
        }

    now = computed_at or datetime.now(UTC)
    db.query(DoaFileSnapshot).filter(DoaFileSnapshot.tenant_id == tenant_id).delete(
        synchronize_session=False
    )

    file_events, _ = build_file_touch_indexes(
        db, tenant_id, activities, commit_activities
    )
    file_touches = events_to_doa_touches(file_events)

    snapshots: list[DoaFileSnapshot] = []
    for (component_id, file_path), touches in file_touches.items():
        if component_id not in valid_components:
            continue
        for score in compute_doa_for_file(touches):
            if score.employee_id not in valid_employees:
                continue
            row = DoaFileSnapshot(
                tenant_id=tenant_id,
                component_id=component_id,
                file_path=file_path,
                employee_id=score.employee_id,
                doa_score=score.doa_score,
                is_author=score.is_author,
                last_touch_at=score.last_touch_at,
                decay_score=score.decay_score,
                computed_at=now,
            )
            db.add(row)
            snapshots.append(row)

    db.flush()
    result.snapshots = snapshots
    return result
