"""Live GitHub REST client for ERA telemetry (Step 04)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.schemas.integrations import GitHubConfigRequest, GitHubRepoInfo
from app.services.github_types import GitHubFileChange, GitHubPullRequestActivity

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
SYNC_WINDOW_MONTHS = 6
MAX_PATCH_CHARS = 3_000
FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "github_merged_prs.json"
)


class GitHubClientError(ValueError):
    """GitHub API or configuration error."""


def parse_repository_url(repository_url: str) -> tuple[str, str]:
    parsed = urlparse(repository_url.strip())
    path = parsed.path.strip("/")
    parts = path.split("/")
    if len(parts) < 2:
        raise GitHubClientError(
            f"Invalid repository URL '{repository_url}'. Expected https://github.com/owner/repo"
        )
    return parts[0], parts[1]


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token.strip()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _github_request(
    session: requests.Session,
    token: str,
    method: str,
    path: str,
    *,
    params: dict | None = None,
) -> requests.Response:
    url = f"{GITHUB_API}{path}"
    response = session.request(
        method,
        url,
        headers=_headers(token),
        timeout=30,
        params=params,
    )
    if response.status_code == 403 and "rate limit" in response.text.lower():
        raise GitHubClientError("GitHub API rate limit exceeded; retry later.")
    if response.status_code == 401:
        raise GitHubClientError(
            "GitHub rejected this token (401). Re-save a valid personal access token "
            "with repository read access under Settings → Integrations."
        )
    if response.status_code >= 400:
        raise GitHubClientError(
            f"GitHub API {method} {path} failed ({response.status_code}): {response.text[:200]}"
        )
    return response


def list_accessible_repositories(token: str) -> list[GitHubRepoInfo]:
    """List repositories accessible to the PAT (user repos + org memberships)."""
    session = requests.Session()
    repositories: list[GitHubRepoInfo] = []
    seen: set[str] = set()
    page = 1

    while page <= 20:
        response = _github_request(
            session,
            token,
            "GET",
            "/user/repos",
            params={
                "per_page": 100,
                "page": page,
                "affiliation": "owner,collaborator,organization_member",
                "sort": "updated",
                "direction": "desc",
            },
        )
        rows = response.json()
        if not rows:
            break

        for row in rows:
            full_name = row.get("full_name") or ""
            if not full_name or full_name in seen:
                continue
            seen.add(full_name)
            repositories.append(
                GitHubRepoInfo(
                    full_name=full_name,
                    html_url=row.get("html_url") or f"https://github.com/{full_name}",
                    default_branch=(row.get("default_branch") or "main").strip(),
                    private=bool(row.get("private")),
                    description=row.get("description"),
                )
            )

        if len(rows) < 100:
            break
        page += 1

    return repositories


def list_repository_branches(token: str, repository_url: str) -> tuple[str, list[str]]:
    owner, repo = parse_repository_url(repository_url)
    session = requests.Session()
    repo_response = _github_request(
        session,
        token,
        "GET",
        f"/repos/{owner}/{repo}",
    )
    repo_payload = repo_response.json()
    default_branch = (repo_payload.get("default_branch") or "main").strip()

    branches: list[str] = []
    page = 1
    while page <= 10:
        response = _github_request(
            session,
            token,
            "GET",
            f"/repos/{owner}/{repo}/branches",
            params={"per_page": 100, "page": page},
        )
        rows = response.json()
        if not rows:
            break
        for row in rows:
            name = (row.get("name") or "").strip()
            if name:
                branches.append(name)
        if len(rows) < 100:
            break
        page += 1

    return default_branch, branches


def load_fixture_activities() -> list[GitHubPullRequestActivity]:
    if not FIXTURE_PATH.is_file():
        raise GitHubClientError(f"GitHub fixture not found: {FIXTURE_PATH}")
    payload = json.loads(FIXTURE_PATH.read_text())
    return [_activity_from_dict(item) for item in payload]


def activities_from_mock_feed() -> list[GitHubPullRequestActivity]:
    """Convert legacy MOCK_GITHUB_ACTIVITY into typed activities (tests / fallback)."""
    from app.services.integration_feeds import MOCK_GITHUB_ACTIVITY

    activities: list[GitHubPullRequestActivity] = []
    for row in MOCK_GITHUB_ACTIVITY:
        activities.append(
            GitHubPullRequestActivity(
                pr_number=row["pr_number"],
                commit_sha=row["commit_sha"],
                merge_commit_sha=row.get("merge_commit_sha", row["commit_sha"]),
                branch=row.get("branch", "main"),
                author_provider_user_id=row["author_provider_user_id"],
                author_login=row["author_provider_user_id"].removeprefix("gh-"),
                author_type="User",
                pr_url=f"https://github.com/acme/example/pull/{row['pr_number']}",
                merged_at=datetime.now(UTC).isoformat(),
                files=[
                    GitHubFileChange(
                        path=file_row["path"],
                        loc_added=file_row["loc_added"],
                        loc_removed=file_row["loc_removed"],
                        component_id=file_row.get("component_id"),
                    )
                    for file_row in row["files"]
                ],
            )
        )
    return activities


def _activity_from_dict(item: dict) -> GitHubPullRequestActivity:
    return GitHubPullRequestActivity(
        pr_number=item["pr_number"],
        commit_sha=item["commit_sha"],
        merge_commit_sha=item.get("merge_commit_sha"),
        branch=item.get("branch", "main"),
        author_provider_user_id=item["author_provider_user_id"],
        author_login=item.get("author_login", item["author_provider_user_id"]),
        author_type=item.get("author_type", "User"),
        pr_url=item["pr_url"],
        merged_at=item.get("merged_at"),
        is_fork=item.get("is_fork", False),
        reviewer_logins=item.get("reviewer_logins", []),
        files=[
            GitHubFileChange(
                path=file_row["path"],
                loc_added=file_row["loc_added"],
                loc_removed=file_row["loc_removed"],
                component_id=file_row.get("component_id"),
                status=file_row.get("status", "modified"),
                patch_preview=file_row.get("patch_preview", ""),
                blob_sha=file_row.get("blob_sha", ""),
                previous_path=file_row.get("previous_path", ""),
            )
            for file_row in item.get("files", [])
        ],
    )


class GitHubClient:
    def __init__(self, config: GitHubConfigRequest, *, use_fixture: bool = False) -> None:
        self.config = config
        self.use_fixture = use_fixture
        repository_urls = config.resolved_repository_urls()
        if not repository_urls:
            raise GitHubClientError("At least one GitHub repository URL is required.")
        self.repository_url = repository_urls[0]
        self.owner, self.repo = parse_repository_url(self.repository_url)
        self._session = requests.Session()

    def fetch_pull_request_activity(
        self,
        *,
        since: datetime | None = None,
    ) -> tuple[list[GitHubPullRequestActivity], dict[str, int]]:
        if self.use_fixture:
            return load_fixture_activities(), {}
        if not self.config.personal_access_token and not self.config.oauth_connected:
            logger.warning("No GitHub token configured; using embedded mock activity feed")
            return activities_from_mock_feed(), {}

        since_dt = since or (datetime.now(UTC) - timedelta(days=30 * SYNC_WINDOW_MONTHS))
        branch_targets = self.config.resolved_branch_targets()
        merged = self._fetch_merged_pull_requests(since_dt, branch_targets)
        open_by_author = self._fetch_open_pr_counts(branch_targets)

        seen_keys: set[str] = set()
        activities: list[GitHubPullRequestActivity] = []
        for pr in merged:
            dedupe_key = pr.dedupe_key
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            activities.append(pr)

        return activities, open_by_author

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        response = self._session.request(
            method,
            f"{GITHUB_API}{path}",
            headers=_headers(self.config.personal_access_token),
            timeout=30,
            **kwargs,
        )
        if response.status_code == 403 and "rate limit" in response.text.lower():
            raise GitHubClientError("GitHub API rate limit exceeded; retry later.")
        if response.status_code == 401:
            raise GitHubClientError(
                "GitHub rejected this token (401). Re-save a valid personal access token "
                "with repository read access under Settings → Integrations."
            )
        if response.status_code == 404 and path.startswith(
            f"/repos/{self.owner}/{self.repo}"
        ):
            raise GitHubClientError(
                f"Repository '{self.owner}/{self.repo}' was not found or this token cannot access it. "
                "Confirm the repository URL and that your PAT is authorized for this repo."
            )
        if response.status_code >= 400:
            raise GitHubClientError(
                f"GitHub API {method} {path} failed ({response.status_code}): {response.text[:200]}"
            )
        return response

    def _fetch_merged_pull_requests(
        self,
        since: datetime,
        branch_targets: list[str] | None,
    ) -> list[GitHubPullRequestActivity]:
        if branch_targets is None:
            return self._fetch_merged_pull_requests_for_base(since, base=None)

        activities: list[GitHubPullRequestActivity] = []
        seen_keys: set[str] = set()
        for branch in branch_targets:
            for activity in self._fetch_merged_pull_requests_for_base(since, base=branch):
                if activity.dedupe_key in seen_keys:
                    continue
                seen_keys.add(activity.dedupe_key)
                activities.append(activity)
        return activities

    def _fetch_merged_pull_requests_for_base(
        self,
        since: datetime,
        *,
        base: str | None,
    ) -> list[GitHubPullRequestActivity]:
        activities: list[GitHubPullRequestActivity] = []
        page = 1
        while page <= 10:
            params: dict[str, str | int] = {
                "state": "closed",
                "sort": "updated",
                "direction": "desc",
                "per_page": 100,
                "page": page,
            }
            if base:
                params["base"] = base

            response = self._request(
                "GET",
                f"/repos/{self.owner}/{self.repo}/pulls",
                params=params,
            )
            pulls = response.json()
            if not pulls:
                break

            stop_paging = False
            for pull in pulls:
                if not pull.get("merged_at"):
                    continue
                merged_at = datetime.fromisoformat(
                    pull["merged_at"].replace("Z", "+00:00")
                )
                if merged_at < since:
                    stop_paging = True
                    continue

                user = pull.get("user") or {}
                if user.get("type") == "Bot":
                    continue
                if pull.get("head", {}).get("repo", {}).get("fork") and not self._is_org_member(
                    user.get("login")
                ):
                    continue

                pr_number = pull["number"]
                files = self._fetch_pr_files(pr_number)
                reviews = self._fetch_pr_reviewers(pr_number)
                login = user.get("login") or "ghost"
                activities.append(
                    GitHubPullRequestActivity(
                        pr_number=pr_number,
                        commit_sha=(pull.get("merge_commit_sha") or pull["head"]["sha"])[:40],
                        merge_commit_sha=pull.get("merge_commit_sha"),
                        branch=pull.get("base", {}).get("ref", base or self.config.branch_target),
                        author_provider_user_id=f"gh-{login}",
                        author_login=login,
                        author_type=user.get("type", "User"),
                        pr_url=pull["html_url"],
                        merged_at=pull.get("merged_at"),
                        is_fork=bool(pull.get("head", {}).get("repo", {}).get("fork")),
                        reviewer_logins=reviews,
                        files=files,
                    )
                )

            if stop_paging or len(pulls) < 100:
                break
            page += 1

        return activities

    def _is_org_member(self, login: str | None) -> bool:
        if not login:
            return False
        try:
            response = self._request(
                "GET",
                f"/orgs/{self.owner}/members/{login}",
            )
            return response.status_code == 204
        except GitHubClientError:
            return self.owner.lower() == login.lower()

    def _fetch_pr_files(self, pr_number: int) -> list[GitHubFileChange]:
        response = self._request(
            "GET",
            f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/files",
            params={"per_page": 100},
        )
        files: list[GitHubFileChange] = []
        for row in response.json():
            patch = row.get("patch") or ""
            if len(patch) > MAX_PATCH_CHARS:
                patch = patch[: MAX_PATCH_CHARS - 3] + "..."
            files.append(
                GitHubFileChange(
                    path=row["filename"],
                    loc_added=row.get("additions", 0),
                    loc_removed=row.get("deletions", 0),
                    status=row.get("status") or "modified",
                    patch_preview=patch,
                    blob_sha=row.get("sha") or "",
                    previous_path=row.get("previous_filename") or "",
                )
            )
        return files

    def _fetch_pr_reviewers(self, pr_number: int) -> list[str]:
        response = self._request(
            "GET",
            f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/reviews",
            params={"per_page": 100},
        )
        reviewers: set[str] = set()
        for review in response.json():
            user = review.get("user") or {}
            if user.get("type") == "Bot":
                continue
            login = user.get("login")
            if login:
                reviewers.add(login)
        return sorted(reviewers)

    def _fetch_open_pr_counts(self, branch_targets: list[str] | None) -> dict[str, int]:
        if branch_targets is None:
            return self._fetch_open_pr_counts_for_base(base=None)

        counts: dict[str, int] = {}
        for branch in branch_targets:
            branch_counts = self._fetch_open_pr_counts_for_base(base=branch)
            for login, count in branch_counts.items():
                counts[login] = counts.get(login, 0) + count
        return counts

    def _fetch_open_pr_counts_for_base(self, *, base: str | None) -> dict[str, int]:
        counts: dict[str, int] = {}
        page = 1
        while page <= 5:
            params: dict[str, str | int] = {
                "state": "open",
                "per_page": 100,
                "page": page,
            }
            if base:
                params["base"] = base

            response = self._request(
                "GET",
                f"/repos/{self.owner}/{self.repo}/pulls",
                params=params,
            )
            pulls = response.json()
            if not pulls:
                break
            for pull in pulls:
                user = pull.get("user") or {}
                if user.get("type") == "Bot":
                    continue
                login = (user.get("login") or "").lower()
                if login:
                    counts[login] = counts.get(login, 0) + 1
            if len(pulls) < 100:
                break
            page += 1
        return counts


def fetch_github_pull_request_activity(
    config: GitHubConfigRequest,
    *,
    use_fixture: bool = False,
) -> tuple[list[GitHubPullRequestActivity], dict[str, int]]:
    if use_fixture:
        return GitHubClient(config, use_fixture=True).fetch_pull_request_activity()

    repository_urls = config.resolved_repository_urls()
    if not repository_urls:
        raise GitHubClientError("At least one GitHub repository URL is required.")

    all_activities: list[GitHubPullRequestActivity] = []
    combined_open_prs: dict[str, int] = {}
    seen_keys: set[str] = set()

    for repository_url in repository_urls:
        repo_config = config.with_repository(repository_url)
        activities, open_prs = GitHubClient(repo_config, use_fixture=False).fetch_pull_request_activity()
        for activity in activities:
            if activity.dedupe_key in seen_keys:
                continue
            seen_keys.add(activity.dedupe_key)
            all_activities.append(activity)
        for login, count in open_prs.items():
            combined_open_prs[login] = combined_open_prs.get(login, 0) + count

    return all_activities, combined_open_prs
