"""GitHub PR review network and risky-change detection (ERA Step 15)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from statistics import quantiles

from sqlalchemy.orm import Session

from app.models.operational import Component
from app.services.github_types import GitHubPullRequestActivity
from app.services.identity_resolver import resolve_author_employee_id


@dataclass(frozen=True)
class ReviewNetworkEdge:
    reviewer_employee_id: str
    author_employee_id: str
    review_count: int
    reviewer_login: str
    author_login: str


@dataclass
class EmployeeReviewMetrics:
    employee_id: str
    review_concentration_pct: float = 0.0
    reviews_given_count: int = 0
    reviews_received_count: int = 0
    sole_reviewer_count: int = 0
    unique_reviewers_on_prs: int = 0
    isolation_score: float = 0.0
    backup_review_score: float = 50.0
    recent_pr_count: int = 0
    no_backup_pr_urls: list[str] = field(default_factory=list)
    top_reviewer_employee_id: str | None = None
    top_reviewer_login: str | None = None


@dataclass(frozen=True)
class RiskyChange:
    pr_number: int
    pr_url: str
    author_employee_id: str | None
    author_login: str
    severity: str
    rule: str
    title: str
    description: str
    merged_at: str | None
    impact_points: float = 25.0


@dataclass
class ReviewNetworkResult:
    edges: list[ReviewNetworkEdge]
    metrics_by_employee: dict[str, EmployeeReviewMetrics]
    risky_changes: list[RiskyChange]
    login_to_employee: dict[str, str]
    window_days: int = 90


def _parse_merged_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _filter_activities_in_window(
    activities: list[GitHubPullRequestActivity],
    *,
    since_days: int,
) -> list[GitHubPullRequestActivity]:
    cutoff = datetime.now(UTC) - timedelta(days=since_days)
    filtered: list[GitHubPullRequestActivity] = []
    for activity in activities:
        if activity.author_type == "Bot":
            continue
        if not activity.merged_at:
            continue
        merged_at = _parse_merged_at(activity.merged_at)
        if merged_at is None or merged_at < cutoff:
            continue
        filtered.append(activity)
    return filtered


def _resolve_github_login(
    db: Session,
    tenant_id: uuid.UUID,
    login: str,
) -> str | None:
    normalized = login.strip().lower()
    if not normalized:
        return None
    for provider_user_id in (f"gh-{normalized}", normalized):
        employee_id = resolve_author_employee_id(
            db,
            tenant_id,
            "github",
            provider_user_id,
            quarantine_event_type="github_review",
            quarantine_payload={"login": normalized},
        )
        if employee_id:
            return employee_id
    return None


def _pr_total_loc(activity: GitHubPullRequestActivity) -> int:
    return sum(file_change.loc_added + file_change.loc_removed for file_change in activity.files)


def _touched_component_ids(activity: GitHubPullRequestActivity) -> set[str]:
    return {
        file_change.component_id
        for file_change in activity.files
        if file_change.component_id
    }


def compute_backup_review_score(
    *,
    unique_reviewers: int,
    review_concentration_pct: float,
    sole_reviewer_count: int,
    recent_pr_count: int,
) -> float:
    """
    0–100 where higher means healthier review backup coverage on the author's PRs.
    """
    if recent_pr_count == 0:
        return 50.0

    diversity = min(100.0, unique_reviewers * 20.0)
    spread = max(0.0, 100.0 - review_concentration_pct)
    sole_penalty = min(35.0, sole_reviewer_count * 12.0)
    score = diversity * 0.55 + spread * 0.45 - sole_penalty
    return round(max(0.0, min(100.0, score)), 1)


def compute_isolation_score(
    *,
    reviews_given: int,
    reviews_received: int,
    unique_reviewers: int,
    recent_pr_count: int,
) -> float:
    if recent_pr_count == 0 and reviews_given == 0:
        return 0.0
    received_factor = 0.0 if recent_pr_count == 0 else max(0.0, 100.0 - unique_reviewers * 25.0)
    given_factor = max(0.0, 50.0 - reviews_given * 8.0)
    return round(min(100.0, received_factor * 0.7 + given_factor * 0.3), 1)


def build_review_network(
    db: Session,
    tenant_id: uuid.UUID,
    activities: list[GitHubPullRequestActivity],
    *,
    since_days: int = 90,
    component_by_id: dict[str, Component] | None = None,
    bus_factor_by_component: dict[str, int] | None = None,
) -> ReviewNetworkResult:
    """Build reviewer→author graph, per-employee metrics, and risky merged PRs."""
    component_by_id = component_by_id or {}
    bus_factor_by_component = bus_factor_by_component or {}
    windowed = _filter_activities_in_window(activities, since_days=since_days)

    edge_counts: dict[tuple[str, str], int] = defaultdict(int)
    edge_logins: dict[tuple[str, str], tuple[str, str]] = {}
    reviews_given: dict[str, int] = defaultdict(int)
    reviews_received: dict[str, int] = defaultdict(int)
    sole_reviewer_count: dict[str, int] = defaultdict(int)
    unique_reviewers_by_author: dict[str, set[str]] = defaultdict(set)
    reviewer_counts_by_author: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    pr_count_by_author: dict[str, int] = defaultdict(int)
    no_backup_urls: dict[str, list[str]] = defaultdict(list)
    login_to_employee: dict[str, str] = {}

    loc_values = [_pr_total_loc(activity) for activity in windowed]
    loc_p95 = quantiles(loc_values, n=20)[-1] if len(loc_values) >= 5 else None

    for activity in windowed:
        author_login = activity.author_login.lower()
        author_id = _resolve_github_login(db, tenant_id, author_login)
        if author_id:
            login_to_employee[author_login] = author_id

        human_reviewers = [
            reviewer.lower()
            for reviewer in activity.reviewer_logins
            if reviewer.lower() != author_login
        ]

        if author_id:
            pr_count_by_author[author_id] += 1
            reviews_received[author_id] += len(human_reviewers)
            for reviewer_login in human_reviewers:
                unique_reviewers_by_author[author_id].add(reviewer_login)
                reviewer_counts_by_author[author_id][reviewer_login] += 1

            if len(human_reviewers) <= 1:
                sole_reviewer_count[author_id] += 1
                no_backup_urls[author_id].append(activity.pr_url)

        for reviewer_login in human_reviewers:
            reviewer_id = _resolve_github_login(db, tenant_id, reviewer_login)
            if reviewer_id:
                login_to_employee[reviewer_login] = reviewer_id
                reviews_given[reviewer_id] += 1
                if author_id:
                    key = (reviewer_id, author_id)
                    edge_counts[key] += 1
                    edge_logins[key] = (reviewer_login, author_login)

    edges: list[ReviewNetworkEdge] = []
    for (reviewer_id, author_id), count in edge_counts.items():
        reviewer_login, author_login = edge_logins[(reviewer_id, author_id)]
        edges.append(
            ReviewNetworkEdge(
                reviewer_employee_id=reviewer_id,
                author_employee_id=author_id,
                review_count=count,
                reviewer_login=reviewer_login,
                author_login=author_login,
            )
        )

    employee_ids = set(pr_count_by_author) | set(reviews_given)
    metrics_by_employee: dict[str, EmployeeReviewMetrics] = {}

    for employee_id in employee_ids:
        recent_pr_count = pr_count_by_author.get(employee_id, 0)
        unique_reviewers = len(unique_reviewers_by_author.get(employee_id, set()))
        reviewer_counts = reviewer_counts_by_author.get(employee_id, {})
        top_reviewer_login: str | None = None
        top_count = 0
        for login, count in reviewer_counts.items():
            if count > top_count:
                top_count = count
                top_reviewer_login = login

        concentration = 0.0
        top_reviewer_employee_id: str | None = None
        if recent_pr_count > 0 and top_count > 0:
            concentration = round((top_count / recent_pr_count) * 100.0, 1)
            if top_reviewer_login:
                top_reviewer_employee_id = login_to_employee.get(top_reviewer_login)

        backup_score = compute_backup_review_score(
            unique_reviewers=unique_reviewers,
            review_concentration_pct=concentration,
            sole_reviewer_count=sole_reviewer_count.get(employee_id, 0),
            recent_pr_count=recent_pr_count,
        )
        isolation = compute_isolation_score(
            reviews_given=reviews_given.get(employee_id, 0),
            reviews_received=reviews_received.get(employee_id, 0),
            unique_reviewers=unique_reviewers,
            recent_pr_count=recent_pr_count,
        )
        metrics_by_employee[employee_id] = EmployeeReviewMetrics(
            employee_id=employee_id,
            review_concentration_pct=concentration,
            reviews_given_count=reviews_given.get(employee_id, 0),
            reviews_received_count=reviews_received.get(employee_id, 0),
            sole_reviewer_count=sole_reviewer_count.get(employee_id, 0),
            unique_reviewers_on_prs=unique_reviewers,
            isolation_score=isolation,
            backup_review_score=backup_score,
            recent_pr_count=recent_pr_count,
            no_backup_pr_urls=no_backup_urls.get(employee_id, [])[:10],
            top_reviewer_employee_id=top_reviewer_employee_id,
            top_reviewer_login=top_reviewer_login,
        )

    risky_changes = detect_risky_changes(
        db,
        tenant_id,
        windowed,
        component_by_id=component_by_id,
        bus_factor_by_component=bus_factor_by_component,
        loc_p95=loc_p95,
        login_to_employee=login_to_employee,
    )

    return ReviewNetworkResult(
        edges=edges,
        metrics_by_employee=metrics_by_employee,
        risky_changes=risky_changes,
        login_to_employee=login_to_employee,
        window_days=since_days,
    )


def detect_risky_changes(
    db: Session,
    tenant_id: uuid.UUID,
    activities: list[GitHubPullRequestActivity],
    *,
    component_by_id: dict[str, Component],
    bus_factor_by_component: dict[str, int],
    loc_p95: float | None,
    login_to_employee: dict[str, str] | None = None,
) -> list[RiskyChange]:
    login_to_employee = login_to_employee or {}
    risky: list[RiskyChange] = []

    for activity in activities:
        author_login = activity.author_login.lower()
        author_id = login_to_employee.get(author_login)
        if author_id is None:
            author_id = _resolve_github_login(db, tenant_id, author_login)
            if author_id:
                login_to_employee[author_login] = author_id

        human_reviewers = [
            reviewer
            for reviewer in activity.reviewer_logins
            if reviewer.lower() != author_login
        ]
        component_ids = _touched_component_ids(activity)
        total_loc = _pr_total_loc(activity)
        touches_spof = any(
            bus_factor_by_component.get(component_id, 99) <= 1
            for component_id in component_ids
        )
        touches_tier1 = any(
            getattr(component_by_id.get(component_id), "criticality", "tier2_core")
            == "tier1_revenue"
            for component_id in component_ids
        )

        if not human_reviewers:
            risky.append(
                RiskyChange(
                    pr_number=activity.pr_number,
                    pr_url=activity.pr_url,
                    author_employee_id=author_id,
                    author_login=activity.author_login,
                    severity="high",
                    rule="merged_without_approval",
                    title=f"PR #{activity.pr_number} merged without review",
                    description=(
                        f"{activity.author_login}'s pull request was merged with no "
                        "human reviewer in the analysis window."
                    ),
                    merged_at=activity.merged_at,
                    impact_points=35.0,
                )
            )
            continue

        if len(human_reviewers) == 1 and touches_tier1:
            risky.append(
                RiskyChange(
                    pr_number=activity.pr_number,
                    pr_url=activity.pr_url,
                    author_employee_id=author_id,
                    author_login=activity.author_login,
                    severity="high",
                    rule="tier1_sole_reviewer",
                    title=f"Tier-1 change with sole reviewer on PR #{activity.pr_number}",
                    description=(
                        "Pull request touched tier-1 revenue components with only one reviewer."
                    ),
                    merged_at=activity.merged_at,
                    impact_points=30.0,
                )
            )

        if touches_spof and len(human_reviewers) <= 1:
            risky.append(
                RiskyChange(
                    pr_number=activity.pr_number,
                    pr_url=activity.pr_url,
                    author_employee_id=author_id,
                    author_login=activity.author_login,
                    severity="high",
                    rule="spof_single_reviewer",
                    title=f"SPOF file change with limited review on PR #{activity.pr_number}",
                    description=(
                        "Changes touch bus-factor-1 paths with at most one reviewer."
                    ),
                    merged_at=activity.merged_at,
                    impact_points=32.0,
                )
            )

        if loc_p95 is not None and total_loc > loc_p95:
            risky.append(
                RiskyChange(
                    pr_number=activity.pr_number,
                    pr_url=activity.pr_url,
                    author_employee_id=author_id,
                    author_login=activity.author_login,
                    severity="medium",
                    rule="large_loc_outlier",
                    title=f"Large change ({total_loc} LOC) on PR #{activity.pr_number}",
                    description=(
                        f"Pull request LOC ({total_loc}) exceeds the team 95th percentile "
                        f"({int(loc_p95)}) in the analysis window."
                    ),
                    merged_at=activity.merged_at,
                    impact_points=22.0,
                )
            )

    risky.sort(key=lambda row: (-row.impact_points, row.pr_number))
    return risky


def employee_review_subgraph(
    result: ReviewNetworkResult,
    employee_id: str,
) -> dict:
    """Incoming reviewers for an employee's PRs (author-centric subgraph)."""
    metrics = result.metrics_by_employee.get(employee_id)
    incoming = [
        edge
        for edge in result.edges
        if edge.author_employee_id == employee_id
    ]
    incoming.sort(key=lambda edge: -edge.review_count)
    return {
        "employee_id": employee_id,
        "metrics": metrics,
        "incoming_reviewers": incoming,
        "window_days": result.window_days,
    }
