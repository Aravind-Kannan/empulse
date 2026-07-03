"""Merge PR and direct-commit activity into per-file touch indexes for DOA / file risk."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.services.github_types import GitHubCommitActivity, GitHubPullRequestActivity
from app.services.identity_resolver import resolve_author_employee_id


@dataclass
class FileTouch:
    employee_id: str
    touched_at: datetime


@dataclass
class FileTouchEvent:
    employee_id: str
    touched_at: datetime
    churn_key: str


def _parse_touch_at(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def pr_merge_shas(activities: list[GitHubPullRequestActivity]) -> set[str]:
    shas: set[str] = set()
    for activity in activities:
        if activity.merge_commit_sha:
            shas.add(activity.merge_commit_sha)
        if activity.commit_sha:
            shas.add(activity.commit_sha)
    return shas


def build_file_touch_indexes(
    db: Session,
    tenant_id: uuid.UUID,
    pr_activities: list[GitHubPullRequestActivity],
    commit_activities: list[GitHubCommitActivity] | None = None,
    *,
    exclude_commit_shas: set[str] | None = None,
    exclude_path: Callable[[str], bool] | None = None,
) -> tuple[
    dict[tuple[str, str], list[FileTouchEvent]],
    dict[tuple[str, str], set[str]],
]:
    """
    Build per-file touch timelines from PRs plus direct branch commits.

    PR merge commits are skipped in commit_activities when their SHA is in exclude_commit_shas
    (typically PR merge_commit_sha values) to avoid double-counting file changes.
    """
    if exclude_path is None:
        from app.services.github_doa import _should_exclude_path

        exclude_path = _should_exclude_path
    file_events: dict[tuple[str, str], list[FileTouchEvent]] = defaultdict(list)
    contributors_by_file: dict[tuple[str, str], set[str]] = defaultdict(set)
    skip_shas = exclude_commit_shas or pr_merge_shas(pr_activities)

    for activity in sorted(pr_activities, key=lambda row: _parse_touch_at(row.merged_at)):
        if activity.author_type == "Bot":
            continue
        author_id = resolve_author_employee_id(
            db,
            tenant_id,
            "github",
            activity.author_provider_user_id,
            demo_fallback_employee_id=None,
            quarantine_event_type="github_pr",
            quarantine_payload={
                "pr_number": activity.pr_number,
                "commit_sha": activity.commit_sha,
            },
        )
        if not author_id:
            continue
        touched_at = _parse_touch_at(activity.merged_at)
        churn_key = activity.dedupe_key
        for file_change in activity.files:
            if not file_change.component_id or exclude_path(file_change.path):
                continue
            key = (file_change.component_id, file_change.path)
            file_events[key].append(
                FileTouchEvent(
                    employee_id=author_id,
                    touched_at=touched_at,
                    churn_key=churn_key,
                )
            )
            contributors_by_file[key].add(author_id)

    for activity in sorted(
        commit_activities or [],
        key=lambda row: _parse_touch_at(row.committed_at),
    ):
        if activity.commit_sha in skip_shas:
            continue
        if activity.author_type == "Bot":
            continue
        author_id = resolve_author_employee_id(
            db,
            tenant_id,
            "github",
            activity.author_provider_user_id,
            demo_fallback_employee_id=None,
            quarantine_event_type="github_commit",
            quarantine_payload={"commit_sha": activity.commit_sha},
        )
        if not author_id:
            continue
        touched_at = _parse_touch_at(activity.committed_at)
        churn_key = activity.dedupe_key
        for file_change in activity.files:
            if not file_change.component_id or exclude_path(file_change.path):
                continue
            key = (file_change.component_id, file_change.path)
            file_events[key].append(
                FileTouchEvent(
                    employee_id=author_id,
                    touched_at=touched_at,
                    churn_key=churn_key,
                )
            )
            contributors_by_file[key].add(author_id)

    return file_events, contributors_by_file


def events_to_doa_touches(
    events: dict[tuple[str, str], list[FileTouchEvent]],
) -> dict[tuple[str, str], list[FileTouch]]:
    return {
        key: [
            FileTouch(employee_id=event.employee_id, touched_at=event.touched_at)
            for event in rows
        ]
        for key, rows in events.items()
    }
