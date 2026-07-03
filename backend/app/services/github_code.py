"""Fetch GitHub file contents and blame ranges for Cognee code ingestion."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from dataclasses import dataclass, field

import requests

from app.services.github_client import GITHUB_API, GitHubClientError, _headers, parse_repository_url
from app.services.github_types import GitHubFileChange, GitHubPullRequestActivity

logger = logging.getLogger(__name__)

MAX_CONTENT_CHARS = 12_000
MAX_PATCH_CHARS = 3_000
MAX_BLAME_RANGES = 60
MAX_CODE_FILES_PER_SYNC = 40
GRAPHQL_URL = "https://api.github.com/graphql"


@dataclass
class BlameRange:
    starting_line: int
    ending_line: int
    author_login: str
    commit_sha: str


@dataclass
class GitHubCodeFileSnapshot:
    repository_url: str
    file_path: str
    ref: str
    component_id: str | None
    content_preview: str = ""
    patch_preview: str = ""
    blame_ranges: list[BlameRange] = field(default_factory=list)
    primary_authors: list[str] = field(default_factory=list)
    content_sha: str = ""

    @property
    def ledger_version(self) -> str:
        payload = f"{self.content_sha}|{self.patch_preview}|{len(self.blame_ranges)}"
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    def blame_summary(self) -> str:
        if not self.blame_ranges:
            return ""
        parts: list[str] = []
        for row in self.blame_ranges[:12]:
            parts.append(
                f"L{row.starting_line}-{row.ending_line}: {row.author_login} ({row.commit_sha[:7]})"
            )
        if len(self.blame_ranges) > 12:
            parts.append(f"+{len(self.blame_ranges) - 12} more ranges")
        return "; ".join(parts)


def _truncate(text: str, limit: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def github_ingest_file_content_enabled(config) -> bool:
    """True when full file bodies and diff patches go on CodeArtifact nodes (default off)."""
    if getattr(config, "ingest_file_content", False):
        return True
    from app.config import get_settings

    return get_settings().github_ingest_file_content


def _fetch_file_content(
    session: requests.Session,
    token: str,
    owner: str,
    repo: str,
    path: str,
    ref: str,
    *,
    include_content: bool = True,
) -> tuple[str, str]:
    response = session.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
        headers=_headers(token),
        params={"ref": ref},
        timeout=30,
    )
    if response.status_code == 404:
        return "", ""
    if response.status_code >= 400:
        raise GitHubClientError(
            f"GitHub contents API failed ({response.status_code}) for {path}"
        )
    payload = response.json()
    if isinstance(payload, list):
        return "", ""
    encoding = payload.get("encoding")
    raw = payload.get("content") or ""
    sha = payload.get("sha") or ""
    if not include_content:
        return "", sha
    if encoding != "base64" or not raw:
        return "", sha
    try:
        decoded = base64.b64decode(raw).decode("utf-8", errors="replace")
    except Exception:
        return "", sha
    return _truncate(decoded, MAX_CONTENT_CHARS), sha


def fetch_blame_ranges(
    token: str,
    owner: str,
    repo: str,
    path: str,
    ref: str,
    *,
    max_ranges: int | None = MAX_BLAME_RANGES,
) -> list[BlameRange]:
    """Fetch git blame line ranges via Commit.blame(path) GraphQL (not Blob)."""
    query = """
    query ($owner: String!, $name: String!, $expression: String!, $path: String!) {
      repository(owner: $owner, name: $name) {
        object(expression: $expression) {
          ... on Commit {
            blame(path: $path) {
              ranges {
                startingLine
                endingLine
                commit {
                  oid
                  author {
                    user { login }
                    name
                    email
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    response = requests.post(
        GRAPHQL_URL,
        headers={**_headers(token), "Content-Type": "application/json"},
        json={
            "query": query,
            "variables": {
                "owner": owner,
                "name": repo,
                "expression": ref,
                "path": path,
            },
        },
        timeout=45,
    )
    if response.status_code >= 400:
        logger.warning(
            "GitHub GraphQL blame failed for %s: %s", path, response.text[:200]
        )
        return _fetch_blame_commits_fallback(token, owner, repo, path, ref)

    data = response.json()
    if data.get("errors"):
        logger.warning("GitHub GraphQL blame errors for %s: %s", path, data["errors"])
        return _fetch_blame_commits_fallback(token, owner, repo, path, ref)

    commit = (
        data.get("data", {})
        .get("repository", {})
        .get("object")
    )
    if not commit:
        return _fetch_blame_commits_fallback(token, owner, repo, path, ref)

    ranges: list[BlameRange] = []
    for row in (commit.get("blame") or {}).get("ranges", []):
        commit_payload = row.get("commit") or {}
        author = commit_payload.get("author") or {}
        user = author.get("user") or {}
        login = (
            user.get("login")
            or author.get("name")
            or author.get("email")
            or "unknown"
        )
        oid = commit_payload.get("oid") or ""
        ranges.append(
            BlameRange(
                starting_line=int(row.get("startingLine") or 0),
                ending_line=int(row.get("endingLine") or 0),
                author_login=str(login),
                commit_sha=oid,
            )
        )
        if max_ranges is not None and len(ranges) >= max_ranges:
            break

    if ranges:
        return ranges
    return _fetch_blame_commits_fallback(token, owner, repo, path, ref)


def _fetch_blame_commits_fallback(
    token: str,
    owner: str,
    repo: str,
    path: str,
    ref: str,
) -> list[BlameRange]:
    """Approximate file authorship from recent commits when GraphQL blame is unavailable."""
    session = requests.Session()
    try:
        response = session.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/commits",
            headers=_headers(token),
            params={"path": path, "sha": ref, "per_page": 20},
            timeout=30,
        )
        if response.status_code >= 400:
            return []
        rows = response.json()
        if not isinstance(rows, list):
            return []
    except Exception as exc:
        logger.warning("GitHub commits fallback failed for %s: %s", path, exc)
        return []

    ranges: list[BlameRange] = []
    line_cursor = 1
    for row in rows:
        commit = row.get("commit") or {}
        author = row.get("author") or {}
        login = author.get("login") or (commit.get("author") or {}).get("name") or "unknown"
        oid = row.get("sha") or ""
        ranges.append(
            BlameRange(
                starting_line=line_cursor,
                ending_line=line_cursor,
                author_login=str(login),
                commit_sha=oid,
            )
        )
        line_cursor += 1
    return ranges


def _fetch_blame_graphql(
    token: str,
    owner: str,
    repo: str,
    path: str,
    ref: str,
) -> list[BlameRange]:
    return fetch_blame_ranges(
        token,
        owner,
        repo,
        path,
        ref,
        max_ranges=MAX_BLAME_RANGES,
    )


def _fixture_code_snapshot(
    repository_url: str,
    path: str,
    ref: str,
    component_id: str | None,
    patch_preview: str,
) -> GitHubCodeFileSnapshot:
    content = (
        f"# Fixture content for {path}\n"
        f"def handler():\n"
        f"    return 'synced-from-{ref}'\n"
    )
    blame = [
        BlameRange(1, 2, "benrivera", ref[:7] or "fixture"),
        BlameRange(3, 4, "carapatel", ref[:7] or "fixture"),
    ]
    return GitHubCodeFileSnapshot(
        repository_url=repository_url,
        file_path=path,
        ref=ref,
        component_id=component_id,
        content_preview=content,
        patch_preview=patch_preview,
        blame_ranges=blame,
        primary_authors=["benrivera", "carapatel"],
        content_sha=hashlib.sha256(content.encode()).hexdigest()[:16],
    )


def collect_github_code_snapshots(
    config,
    activities: list[GitHubPullRequestActivity],
    *,
    use_fixture: bool = False,
) -> list[GitHubCodeFileSnapshot]:
    """Build unique file snapshots (content + blame) from merged PR file changes."""
    repository_urls = config.resolved_repository_urls()
    if not repository_urls:
        return []

    repository_url = repository_urls[0]
    owner, repo = parse_repository_url(repository_url)
    token = (config.personal_access_token or "").strip()
    ingest_content = github_ingest_file_content_enabled(config)

    seen: set[str] = set()
    candidates: list[tuple[str, str, str | None, str]] = []

    for activity in activities:
        ref = activity.merge_commit_sha or activity.commit_sha
        for file_change in activity.files:
            if not file_change.component_id:
                continue
            key = f"{ref}|{file_change.path}"
            if key in seen:
                continue
            seen.add(key)
            patch_preview = (
                file_change.patch_preview if ingest_content else ""
            )
            candidates.append(
                (ref, file_change.path, file_change.component_id, patch_preview)
            )
            if len(candidates) >= MAX_CODE_FILES_PER_SYNC:
                break
        if len(candidates) >= MAX_CODE_FILES_PER_SYNC:
            break

    snapshots: list[GitHubCodeFileSnapshot] = []
    session = requests.Session()

    for ref, path, component_id, patch_preview in candidates:
        if use_fixture or not token:
            snap = _fixture_code_snapshot(
                repository_url, path, ref, component_id, patch_preview
            )
            if not ingest_content:
                snap.content_preview = ""
                snap.patch_preview = ""
            snapshots.append(snap)
            continue

        try:
            content, content_sha = _fetch_file_content(
                session,
                token,
                owner,
                repo,
                path,
                ref,
                include_content=ingest_content,
            )
            blame = _fetch_blame_graphql(token, owner, repo, path, ref)
            authors = sorted({row.author_login for row in blame if row.author_login})
            stored_patch = (
                _truncate(patch_preview, MAX_PATCH_CHARS) if ingest_content else ""
            )
            snapshots.append(
                GitHubCodeFileSnapshot(
                    repository_url=repository_url,
                    file_path=path,
                    ref=ref,
                    component_id=component_id,
                    content_preview=content,
                    patch_preview=stored_patch,
                    blame_ranges=blame,
                    primary_authors=authors,
                    content_sha=content_sha,
                )
            )
        except Exception as exc:
            logger.warning("Skipping code snapshot for %s@%s: %s", path, ref, exc)
            stored_patch = (
                _truncate(patch_preview, MAX_PATCH_CHARS) if ingest_content else ""
            )
            snapshots.append(
                GitHubCodeFileSnapshot(
                    repository_url=repository_url,
                    file_path=path,
                    ref=ref,
                    component_id=component_id,
                    patch_preview=stored_patch,
                    primary_authors=[],
                    content_sha="",
                )
            )

    return snapshots
