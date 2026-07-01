"""Shared GitHub telemetry types (Step 04)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GitHubFileChange:
    path: str
    loc_added: int
    loc_removed: int
    component_id: str | None = None


@dataclass
class GitHubPullRequestActivity:
    pr_number: int
    commit_sha: str
    merge_commit_sha: str | None
    branch: str
    author_provider_user_id: str
    author_login: str
    author_type: str
    pr_url: str
    merged_at: str | None
    is_fork: bool = False
    reviewer_logins: list[str] = field(default_factory=list)
    files: list[GitHubFileChange] = field(default_factory=list)

    @property
    def dedupe_key(self) -> str:
        return self.merge_commit_sha or f"pr-{self.pr_number}"
