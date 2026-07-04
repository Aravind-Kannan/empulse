"""File-level churn × ownership risk matrix (ERA Step 13)."""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.operational import Component, Employee, FileRiskSnapshot
from app.services.github_doa import DOA_AUTHOR_THRESHOLD, _should_exclude_path, compute_doa_for_file
from app.services.role_utils import is_leadership_role
from app.services.github_touch import FileTouch as DoaFileTouch
from app.services.github_touch import build_file_touch_indexes
from app.services.github_types import GitHubCommitActivity, GitHubPullRequestActivity

logger = logging.getLogger(__name__)

ANALYSIS_WINDOW_DAYS = 90
HIGH_CHURN_PR_THRESHOLD = 3
MIN_TOUCHES = 3
SMALL_TEAM_SIZE_THRESHOLD = 8
SMALL_TEAM_HIGH_CHURN_THRESHOLD = 2
SMALL_TEAM_MIN_TOUCHES = 2
MIN_CONTRIBUTOR_COVERAGE_PCT = 50.0
MIN_BUS_FACTOR_COVERAGE_PCT = 25.0
MAX_PRIMARY_OWNER_DOA_PCT = 75.0

TEST_PATH_MARKERS = (
    "/test/",
    "/tests/",
    "/__tests__/",
    "/spec/",
    "/mocks/",
)
EXACT_EXCLUDE_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "go.sum",
    "cargo.lock",
}

Quadrant = str  # critical | stable_niche | active_shared | healthy


@dataclass
class FileRiskRecord:
    component_id: str
    repo_path: str
    file_path: str
    churn_score: int
    contributor_count: int
    bus_factor: int
    quadrant: Quadrant
    primary_owner_employee_id: str | None
    primary_owner_doa_pct: float | None = None
    computed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def _parse_merged_at(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def should_exclude_file_path(path: str) -> bool:
    normalized = path.lower().lstrip("/")
    if normalized in EXACT_EXCLUDE_FILES:
        return True
    if any(marker in normalized for marker in TEST_PATH_MARKERS):
        return True
    return _should_exclude_path(path)


def _active_engineering_team_size(db: Session, tenant_id: uuid.UUID) -> int:
    team = [
        employee
        for employee in db.query(Employee)
        .filter(Employee.tenant_id == tenant_id, Employee.active.is_(True))
        .all()
        if not is_leadership_role(employee.role)
    ]
    return max(len(team), 1)


def _high_churn_threshold(team_size: int) -> int:
    if team_size <= SMALL_TEAM_SIZE_THRESHOLD:
        return SMALL_TEAM_HIGH_CHURN_THRESHOLD
    return HIGH_CHURN_PR_THRESHOLD


def _min_touches_threshold(team_size: int) -> int:
    if team_size <= SMALL_TEAM_SIZE_THRESHOLD:
        return SMALL_TEAM_MIN_TOUCHES
    return MIN_TOUCHES


def _contributor_coverage_pct(contributor_count: int, team_size: int) -> float:
    return (contributor_count / max(team_size, 1)) * 100.0


def _bus_factor_coverage_pct(bus_factor: int, team_size: int) -> float:
    return (bus_factor / max(team_size, 1)) * 100.0


def _has_ownership_risk(
    *,
    contributor_count: int,
    team_size: int,
    bus_factor: int,
    primary_owner_doa_pct: float | None,
) -> bool:
    if _contributor_coverage_pct(contributor_count, team_size) < MIN_CONTRIBUTOR_COVERAGE_PCT:
        return True
    if _bus_factor_coverage_pct(bus_factor, team_size) < MIN_BUS_FACTOR_COVERAGE_PCT:
        return True
    if primary_owner_doa_pct is not None and primary_owner_doa_pct >= MAX_PRIMARY_OWNER_DOA_PCT:
        return True
    return False


def classify_quadrant(
    *,
    churn_score: int,
    contributor_count: int,
    team_size: int = 20,
    bus_factor: int = 1,
    primary_owner_doa_pct: float | None = None,
) -> Quadrant:
    high_churn = churn_score >= _high_churn_threshold(team_size)
    ownership_risk = _has_ownership_risk(
        contributor_count=contributor_count,
        team_size=team_size,
        bus_factor=bus_factor,
        primary_owner_doa_pct=primary_owner_doa_pct,
    )
    if ownership_risk and high_churn:
        return "critical"
    if ownership_risk:
        return "stable_niche"
    if high_churn:
        return "active_shared"
    return "healthy"


def _file_bus_factor(doa_scores: dict[str, float]) -> int:
    authors = sum(1 for score in doa_scores.values() if score >= DOA_AUTHOR_THRESHOLD)
    return max(authors, 1) if doa_scores else 0


def compute_file_risk_from_activities(
    db: Session,
    tenant_id: uuid.UUID,
    activities: list[GitHubPullRequestActivity],
    commit_activities: list[GitHubCommitActivity] | None = None,
    *,
    repo_path: str = "",
    window_days: int = ANALYSIS_WINDOW_DAYS,
    computed_at: datetime | None = None,
) -> list[FileRiskRecord]:
    now = computed_at or datetime.now(UTC)
    cutoff = now - timedelta(days=window_days)
    team_size = _active_engineering_team_size(db, tenant_id)
    min_touches = _min_touches_threshold(team_size)

    file_events, _ = build_file_touch_indexes(
        db,
        tenant_id,
        activities,
        commit_activities,
        exclude_path=should_exclude_file_path,
    )

    pr_ids_by_file: dict[tuple[str, str], set[str]] = defaultdict(set)
    contributors_by_file: dict[tuple[str, str], set[str]] = defaultdict(set)
    touches_by_file: dict[tuple[str, str], list[DoaFileTouch]] = defaultdict(list)

    for key, events in file_events.items():
        for event in events:
            if event.touched_at < cutoff:
                continue
            pr_ids_by_file[key].add(event.churn_key)
            contributors_by_file[key].add(event.employee_id)
            touches_by_file[key].append(
                DoaFileTouch(employee_id=event.employee_id, touched_at=event.touched_at)
            )

    records: list[FileRiskRecord] = []
    for key, churn_keys in pr_ids_by_file.items():
        component_id, file_path = key
        churn_score = len(churn_keys)
        if churn_score < min_touches:
            continue

        contributor_count = len(contributors_by_file[key])
        doa_by_employee = {
            score.employee_id: score.doa_score
            for score in compute_doa_for_file(touches_by_file[key])
        }
        bus_factor = _file_bus_factor(doa_by_employee)

        primary_owner_id: str | None = None
        primary_doa: float | None = None
        if doa_by_employee:
            primary_owner_id = max(doa_by_employee, key=doa_by_employee.get)
            primary_doa = round(doa_by_employee[primary_owner_id] * 100, 1)

        quadrant = classify_quadrant(
            churn_score=churn_score,
            contributor_count=contributor_count,
            team_size=team_size,
            bus_factor=bus_factor,
            primary_owner_doa_pct=primary_doa,
        )
        records.append(
            FileRiskRecord(
                component_id=component_id,
                repo_path=repo_path,
                file_path=file_path,
                churn_score=churn_score,
                contributor_count=contributor_count,
                bus_factor=bus_factor,
                quadrant=quadrant,
                primary_owner_employee_id=primary_owner_id,
                primary_owner_doa_pct=primary_doa,
                computed_at=now,
            )
        )

    return records


def persist_file_risk_snapshots(
    db: Session,
    tenant_id: uuid.UUID,
    activities: list[GitHubPullRequestActivity],
    commit_activities: list[GitHubCommitActivity] | None = None,
    *,
    repo_path: str = "",
    computed_at: datetime | None = None,
) -> list[FileRiskSnapshot]:
    records = compute_file_risk_from_activities(
        db,
        tenant_id,
        activities,
        commit_activities,
        repo_path=repo_path,
        computed_at=computed_at,
    )
    valid_components = {
        row[0]
        for row in db.query(Component.id).filter(Component.tenant_id == tenant_id).all()
    }

    db.query(FileRiskSnapshot).filter(FileRiskSnapshot.tenant_id == tenant_id).delete(
        synchronize_session=False
    )

    snapshots: list[FileRiskSnapshot] = []
    for record in records:
        if record.component_id not in valid_components:
            continue
        row = FileRiskSnapshot(
            tenant_id=tenant_id,
            component_id=record.component_id,
            repo_path=record.repo_path,
            file_path=record.file_path,
            churn_score=record.churn_score,
            contributor_count=record.contributor_count,
            bus_factor=record.bus_factor,
            quadrant=record.quadrant,
            primary_owner_employee_id=record.primary_owner_employee_id,
            primary_owner_doa_pct=record.primary_owner_doa_pct,
            computed_at=record.computed_at,
        )
        db.add(row)
        snapshots.append(row)

    db.flush()
    return snapshots


def _configured_github_branch_fallback(config) -> str:
    branches = config.resolved_branch_targets()
    if branches:
        return branches[0]
    return (config.branch_target or "main").strip() or "main"


def _repository_url_for_repo_path(config, repo_path: str) -> str | None:
    from app.services.github_client import GitHubClientError, parse_repository_url

    normalized = (repo_path or "").strip().lower()
    if not normalized:
        return None

    for url in config.resolved_repository_urls():
        try:
            owner, repo = parse_repository_url(url)
        except GitHubClientError:
            continue
        if f"{owner}/{repo}".lower() == normalized:
            return url

    urls = config.resolved_repository_urls()
    return urls[0] if len(urls) == 1 else None


def _resolve_github_branch(
    db: Session,
    tenant_id: uuid.UUID,
    repo_path: str = "",
    *,
    branch_cache: dict[str, str] | None = None,
) -> str:
    from app.services.integration_config_store import get_github_config
    from app.services.github_client import GitHubClientError, list_repository_branches

    cache_key = (repo_path or "").strip().lower()
    if branch_cache is not None and cache_key and cache_key in branch_cache:
        return branch_cache[cache_key]

    config = get_github_config(db, tenant_id)
    fallback = _configured_github_branch_fallback(config) if config else "main"

    if config and cache_key:
        repository_url = _repository_url_for_repo_path(config, repo_path)
        token = (config.personal_access_token or "").strip()
        if repository_url and token:
            try:
                default_branch, _ = list_repository_branches(token, repository_url)
                branch = (default_branch or fallback).strip() or fallback
                if branch_cache is not None:
                    branch_cache[cache_key] = branch
                return branch
            except GitHubClientError:
                logger.warning(
                    "Could not resolve default branch for %s; using %s",
                    repo_path,
                    fallback,
                )
            except Exception:
                logger.warning(
                    "Unexpected error resolving default branch for %s; using %s",
                    repo_path,
                    fallback,
                    exc_info=True,
                )

    if branch_cache is not None and cache_key:
        branch_cache[cache_key] = fallback
    return fallback


def _github_blob_url(repo_path: str, file_path: str, branch: str) -> str | None:
    if not repo_path or "/" not in repo_path:
        return None
    return f"https://github.com/{repo_path}/blob/{branch}/{file_path.lstrip('/')}"


def _snapshot_to_dict(
    row: FileRiskSnapshot,
    *,
    component_name: str,
    owner_name: str | None,
    branch: str = "main",
) -> dict:
    return {
        "component_id": row.component_id,
        "component_name": component_name,
        "repo_path": row.repo_path,
        "file_path": row.file_path,
        "churn_score": row.churn_score,
        "contributor_count": row.contributor_count,
        "bus_factor": row.bus_factor,
        "quadrant": row.quadrant,
        "primary_owner_employee_id": row.primary_owner_employee_id,
        "primary_owner_name": owner_name,
        "primary_owner_doa_pct": row.primary_owner_doa_pct,
        "github_url": _github_blob_url(row.repo_path, row.file_path, branch),
        "computed_at": row.computed_at,
    }


def get_kra_file_risk(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    component_id: str | None = None,
) -> dict:
    query = db.query(FileRiskSnapshot).filter(FileRiskSnapshot.tenant_id == tenant_id)
    if component_id:
        query = query.filter(FileRiskSnapshot.component_id == component_id)

    rows = query.order_by(
        FileRiskSnapshot.quadrant,
        FileRiskSnapshot.churn_score.desc(),
    ).all()

    components = {
        row.id: row.name
        for row in db.query(Component).filter(Component.tenant_id == tenant_id).all()
    }
    employees = {
        row.id: row.name
        for row in db.query(Employee).filter(Employee.tenant_id == tenant_id).all()
    }

    branch_cache: dict[str, str] = {}
    files = [
        _snapshot_to_dict(
            row,
            component_name=components.get(row.component_id, row.component_id),
            owner_name=(
                employees.get(row.primary_owner_employee_id)
                if row.primary_owner_employee_id
                else None
            ),
            branch=_resolve_github_branch(
                db, tenant_id, row.repo_path, branch_cache=branch_cache
            ),
        )
        for row in rows
    ]

    quadrant_counts: dict[str, int] = defaultdict(int)
    for item in files:
        quadrant_counts[item["quadrant"]] += 1

    critical_sorted = sorted(
        [item for item in files if item["quadrant"] == "critical"],
        key=lambda item: (-item["churn_score"], item["bus_factor"]),
    )

    component_name = components.get(component_id) if component_id else None
    team_size = _active_engineering_team_size(db, tenant_id)

    return {
        "component_id": component_id,
        "component_name": component_name,
        "team_size": team_size,
        "files": files,
        "quadrant_counts": dict(quadrant_counts),
        "cross_training_priority": critical_sorted,
    }


def get_employee_hotspots(
    db: Session,
    tenant_id: uuid.UUID,
    employee_id: str,
) -> dict:
    rows = (
        db.query(FileRiskSnapshot)
        .filter(
            FileRiskSnapshot.tenant_id == tenant_id,
            FileRiskSnapshot.primary_owner_employee_id == employee_id,
            FileRiskSnapshot.quadrant == "critical",
        )
        .order_by(FileRiskSnapshot.churn_score.desc())
        .all()
    )

    components = {
        row.id: row.name
        for row in db.query(Component).filter(Component.tenant_id == tenant_id).all()
    }
    employee = (
        db.query(Employee)
        .filter(Employee.tenant_id == tenant_id, Employee.id == employee_id)
        .one_or_none()
    )
    owner_name = employee.name if employee else None

    branch_cache: dict[str, str] = {}
    files = [
        _snapshot_to_dict(
            row,
            component_name=components.get(row.component_id, row.component_id),
            owner_name=owner_name,
            branch=_resolve_github_branch(
                db, tenant_id, row.repo_path, branch_cache=branch_cache
            ),
        )
        for row in rows
    ]

    return {
        "employee_id": employee_id,
        "critical_count": len(files),
        "files": files,
    }


def build_file_risk_evidence_items(
    db: Session,
    tenant_id: uuid.UUID,
    employee_id: str,
    employee_name: str,
) -> list[dict]:
    hotspots = get_employee_hotspots(db, tenant_id, employee_id)
    items: list[dict] = []
    for index, file_row in enumerate(hotspots["files"][:5]):
        doa_note = (
            f", you are primary owner (DOA {file_row['primary_owner_doa_pct']:.0f}%)"
            if file_row.get("primary_owner_doa_pct") is not None
            else ""
        )
        items.append(
            {
                "id": f"{employee_id}-file-risk-{index}-{file_row['file_path']}",
                "dimension": "knowledge",
                "severity": "high",
                "title": f"Critical file — {file_row['file_path']}",
                "description": (
                    f"High churn ({file_row['churn_score']} changes/90d), "
                    f"bus factor {file_row['bus_factor']}{doa_note}."
                ),
                "impact_points": min(100.0, 22.0 + file_row["churn_score"] * 2.5),
                "sources": [
                    {
                        "provider": "github",
                        "label": file_row["file_path"].split("/")[-1],
                        "url": file_row.get("github_url"),
                    }
                ],
                "synthetic": False,
            }
        )
    return items


def count_critical_files(db: Session, tenant_id: uuid.UUID) -> int:
    return (
        db.query(FileRiskSnapshot)
        .filter(
            FileRiskSnapshot.tenant_id == tenant_id,
            FileRiskSnapshot.quadrant == "critical",
        )
        .count()
    )
