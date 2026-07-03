"""GitHub contributor discovery and identity mapping for sync + reconciliation."""

from __future__ import annotations

import logging
import uuid

import requests
from sqlalchemy.orm import Session

from app.services.identity_auto_map import auto_map_provider_member_identities
from app.schemas.identity import ProviderMember
from app.schemas.integrations import GitHubConfigRequest
from app.services.github_client import (
    GITHUB_API,
    GitHubClientError,
    _headers,
    parse_repository_url,
)

logger = logging.getLogger(__name__)

_NOREPLY_SUFFIX = "@users.noreply.github.com"


def github_provider_user_id(login: str) -> str:
    """Canonical provider id used by PR/blame ingest (`gh-{login}`)."""
    return f"gh-{login.strip()}"


def _is_usable_email(email: str | None) -> bool:
    if not email or not str(email).strip():
        return False
    normalized = str(email).strip().lower()
    return not normalized.endswith(_NOREPLY_SUFFIX)


def _github_get(
    session: requests.Session,
    token: str,
    path: str,
    *,
    params: dict | None = None,
) -> requests.Response:
    response = session.get(
        f"{GITHUB_API}{path}",
        headers=_headers(token),
        params=params,
        timeout=30,
    )
    if response.status_code == 403 and "rate limit" in response.text.lower():
        raise GitHubClientError("GitHub API rate limit exceeded; retry later.")
    if response.status_code == 401:
        raise GitHubClientError("GitHub token rejected (401).")
    if response.status_code >= 400:
        raise GitHubClientError(
            f"GitHub API GET {path} failed ({response.status_code}): {response.text[:200]}"
        )
    return response


def _paginate_github(
    session: requests.Session,
    token: str,
    path: str,
    *,
    params: dict | None = None,
    max_pages: int = 10,
) -> list[dict]:
    rows: list[dict] = []
    page = 1
    base_params = dict(params or {})
    while page <= max_pages:
        response = _github_get(
            session,
            token,
            path,
            params={**base_params, "per_page": 100, "page": page},
        )
        batch = response.json()
        if not batch:
            break
        if isinstance(batch, dict):
            return [batch]
        rows.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return rows


def _fetch_user_profile(
    session: requests.Session,
    token: str,
    login: str,
) -> dict:
    response = _github_get(session, token, f"/users/{login}")
    return response.json()


def _collect_repo_people(
    session: requests.Session,
    token: str,
    owner: str,
    repo: str,
) -> set[str]:
    logins: set[str] = set()
    for path in (
        f"/repos/{owner}/{repo}/contributors",
        f"/repos/{owner}/{repo}/collaborators",
    ):
        try:
            for row in _paginate_github(session, token, path):
                login = (row.get("login") or "").strip()
                if login and row.get("type", "User") != "Bot":
                    logins.add(login)
        except GitHubClientError as exc:
            logger.debug("Skipping %s for %s/%s: %s", path, owner, repo, exc)
    return logins


def _collect_org_people(
    session: requests.Session,
    token: str,
    org: str,
) -> set[str]:
    logins: set[str] = set()
    try:
        for row in _paginate_github(session, token, f"/orgs/{org}/members"):
            login = (row.get("login") or "").strip()
            if login:
                logins.add(login)
    except GitHubClientError as exc:
        logger.debug("Org members unavailable for %s: %s", org, exc)
    return logins


def fetch_github_provider_members(config: GitHubConfigRequest) -> list[ProviderMember]:
    """
    Load GitHub people for identity mapping from configured repositories.

    Merges repo contributors, collaborators, and org members (when available).
    Provider ids use `gh-{login}` to match PR/blame ingest.
    """
    token = (config.personal_access_token or "").strip()
    if not token and not config.oauth_connected:
        return []

    repository_urls = config.resolved_repository_urls()
    if not repository_urls:
        return []

    session = requests.Session()
    logins: set[str] = set()
    orgs_seen: set[str] = set()

    for repository_url in repository_urls:
        owner, repo = parse_repository_url(repository_url)
        logins.update(_collect_repo_people(session, token, owner, repo))
        org_key = owner.lower()
        if org_key not in orgs_seen:
            orgs_seen.add(org_key)
            logins.update(_collect_org_people(session, token, owner))

    members: list[ProviderMember] = []
    for login in sorted(logins, key=str.lower):
        try:
            profile = _fetch_user_profile(session, token, login)
        except GitHubClientError as exc:
            logger.debug("Profile fetch failed for %s: %s", login, exc)
            members.append(
                ProviderMember(
                    id=github_provider_user_id(login),
                    label=login,
                    email=None,
                )
            )
            continue

        if profile.get("type") == "Bot":
            continue

        email = profile.get("email")
        if not _is_usable_email(email):
            email = None

        members.append(
            ProviderMember(
                id=github_provider_user_id(login),
                label=(profile.get("name") or login).strip() or login,
                email=email,
            )
        )

    return members


_provider_member_cache: dict[tuple[uuid.UUID, str], list[ProviderMember]] = {}


def cache_github_provider_members(
    tenant_id: uuid.UUID,
    members: list[ProviderMember],
) -> None:
    """Seed resolver cache for the current sync request."""
    _provider_member_cache[(tenant_id, "github")] = members


def clear_provider_member_cache() -> None:
    _provider_member_cache.clear()


def get_cached_github_provider_members(
    tenant_id: uuid.UUID,
) -> list[ProviderMember] | None:
    return _provider_member_cache.get((tenant_id, "github"))


def sync_github_contributor_identities(
    db: Session,
    tenant_id: uuid.UUID,
    members: list[ProviderMember],
) -> int:
    """Persist high-confidence GitHub → employee mappings from contributor emails."""
    return auto_map_provider_member_identities(db, tenant_id, "github", members)


def prepare_github_identity_context(
    db: Session,
    tenant_id: uuid.UUID,
    config: GitHubConfigRequest,
) -> list[ProviderMember]:
    """Fetch contributors, cache for resolver, and persist email-based mappings."""
    members = fetch_github_provider_members(config)
    cache_github_provider_members(tenant_id, members)
    sync_github_contributor_identities(db, tenant_id, members)
    return members
