"""Link repo `notion-docs/` markdown pack to GitHub components when Notion API is empty."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from app.services.github_client import GITHUB_API, _headers, parse_repository_url
from app.services.notion_client import match_component_for_document

logger = logging.getLogger(__name__)

NOTION_DOCS_ROOT = "notion-docs"
REPO_ROOT = Path(__file__).resolve().parents[2]
TITLE_FROM_FILENAME = {
    "00-platform-overview": "Platform overview",
    "01-era": "ERA — Employee Risk Assessment",
    "02-kra": "KRA — Knowledge Risk Assessment",
    "03-incident-investigation": "Incident Investigation",
    "04-employee-exit": "Employee Exit",
    "05-dashboard": "Manager Dashboard",
    "06-integrations-platform": "Integrations & platform",
    "07-onboarding-auth": "Onboarding & auth",
    "01-local-development": "Local development",
    "02-integration-sync": "Integration sync",
    "03-cognee-graph-operations": "Cognee & graph operations",
    "04-tenant-neo4j-inspection": "Tenant & Neo4j inspection",
    "05-troubleshooting": "Troubleshooting",
    "06-era-review-cadence": "ERA review cadence",
}


def _title_from_markdown(content: str, fallback: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped.removeprefix("# ").strip()
    return fallback


def _title_from_path(path: str) -> str:
    stem = path.rsplit("/", 1)[-1].removesuffix(".md")
    if stem in TITLE_FROM_FILENAME:
        return TITLE_FROM_FILENAME[stem]
    cleaned = re.sub(r"^\d+-", "", stem)
    return cleaned.replace("-", " ").strip().title() or stem


def _list_repo_paths(
    token: str,
    owner: str,
    repo: str,
    *,
    prefix: str,
    ref: str = "HEAD",
) -> list[str]:
    """Return file paths under prefix using the git trees API (single request)."""
    session = requests.Session()
    ref_resp = session.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{ref}",
        headers=_headers(token),
        timeout=30,
    )
    if ref_resp.status_code == 404:
        ref_resp = session.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/commits/HEAD",
            headers=_headers(token),
            timeout=30,
        )
        if ref_resp.status_code >= 400:
            return []
        sha = ref_resp.json().get("sha")
    else:
        sha = ref_resp.json().get("object", {}).get("sha")
    if not sha:
        return []

    tree_resp = session.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{sha}",
        headers=_headers(token),
        params={"recursive": "1"},
        timeout=60,
    )
    if tree_resp.status_code >= 400:
        logger.warning("GitHub tree fetch failed for %s/%s: %s", owner, repo, tree_resp.status_code)
        return []

    norm_prefix = prefix.strip("/") + "/"
    paths: list[str] = []
    for item in tree_resp.json().get("tree") or []:
        path = str(item.get("path") or "")
        if item.get("type") != "blob":
            continue
        if not path.startswith(norm_prefix):
            continue
        if not path.endswith(".md"):
            continue
        if path.endswith("README.md"):
            continue
        paths.append(path)
    return sorted(paths)


def _fetch_file_at_ref(
    token: str,
    owner: str,
    repo: str,
    path: str,
    *,
    ref: str,
) -> tuple[str, str | None]:
    session = requests.Session()
    response = session.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
        headers=_headers(token),
        params={"ref": ref},
        timeout=30,
    )
    if response.status_code >= 400:
        return "", None
    payload = response.json()
    import base64

    raw = payload.get("content") or ""
    if payload.get("encoding") != "base64" or not raw:
        return "", payload.get("sha")
    try:
        text = base64.b64decode(raw).decode("utf-8", errors="replace")
    except Exception:
        return "", payload.get("sha")
    return text, payload.get("sha")


def fetch_github_notion_doc_pack(
    github_token: str,
    repository_url: str,
    *,
    component_names: dict[str, str],
    path_component_map: dict[str, str] | None = None,
    branch: str = "main",
) -> list[dict[str, Any]]:
    """
    Build Notion-style doc inventory rows from `notion-docs/**/*.md` in GitHub.

    Used when the Notion integration token cannot see workspace pages (common until
    pages are explicitly shared with the integration).
    """
    token = github_token.strip()
    if not token or not repository_url.strip():
        return []

    try:
        owner, repo = parse_repository_url(repository_url)
    except ValueError:
        return []

    paths = _list_repo_paths(token, owner, repo, prefix=NOTION_DOCS_ROOT, ref=branch)
    if not paths:
        paths = _list_repo_paths(token, owner, repo, prefix=NOTION_DOCS_ROOT, ref="HEAD")
    if not paths:
        logger.info("No notion-docs markdown files found in %s/%s", owner, repo)
        return []

    now = datetime.now(UTC).isoformat()
    docs: list[dict[str, Any]] = []
    for path in paths:
        content, blob_sha = _fetch_file_at_ref(token, owner, repo, path, ref=branch)
        fallback_title = _title_from_path(path)
        title = _title_from_markdown(content, fallback_title) if content else fallback_title
        component_id = match_component_for_document(
            title,
            path_hint=path,
            component_names=component_names,
            path_component_map=path_component_map,
        )
        page_id = hashlib.sha256(f"github:{owner}/{repo}:{path}".encode()).hexdigest()[:32]
        docs.append(
            {
                "page_id": page_id,
                "title": title,
                "page_url": f"https://github.com/{owner}/{repo}/blob/{branch}/{path}",
                "last_edited_at": now,
                "component_id": component_id,
                "owner_emails": [],
                "page_kind": "runbook" if "/runbooks/" in path else "architecture",
                "last_verified_at": None,
                "is_archived": False,
                "source": "github_notion_docs_pack",
                "repo_path": path,
                "blob_sha": blob_sha,
            }
        )
    return docs


def fetch_local_notion_doc_pack(
    *,
    component_names: dict[str, str],
    path_component_map: dict[str, str] | None = None,
    root: Path | None = None,
) -> list[dict[str, Any]]:
    """Read `notion-docs/**/*.md` from the Empulse repo checkout (dev fallback)."""
    pack_root = (root or REPO_ROOT.parent) / NOTION_DOCS_ROOT
    if not pack_root.is_dir():
        return []

    now = datetime.now(UTC).isoformat()
    docs: list[dict[str, Any]] = []
    for path in sorted(pack_root.rglob("*.md")):
        rel = path.relative_to(pack_root.parent).as_posix()
        if path.name == "README.md":
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        fallback_title = _title_from_path(rel)
        title = _title_from_markdown(content, fallback_title)
        component_id = match_component_for_document(
            title,
            path_hint=rel,
            component_names=component_names,
            path_component_map=path_component_map,
        )
        page_id = hashlib.sha256(f"local:{rel}".encode()).hexdigest()[:32]
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
        docs.append(
            {
                "page_id": page_id,
                "title": title,
                "page_url": f"file://{path.resolve()}",
                "last_edited_at": mtime,
                "component_id": component_id,
                "owner_emails": [],
                "page_kind": "runbook" if "/runbooks/" in rel else "architecture",
                "last_verified_at": None,
                "is_archived": False,
                "source": "local_notion_docs_pack",
                "repo_path": rel,
            }
        )
    return docs
