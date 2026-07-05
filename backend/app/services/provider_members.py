"""Load live provider member lists for identity mapping."""

from __future__ import annotations

import logging
import time
import uuid

import requests
from sqlalchemy.orm import Session

from app.schemas.employee_master import FetchUsersRequest, MasterDataRecord
from app.schemas.identity import ProviderMember
from app.services.employee_master_fetch import _fetch_slack_users_live
from app.services.github_identity import fetch_github_provider_members
from app.services.integration_config_store import (
    get_all_configs,
    get_github_config,
    get_jira_config,
    is_source_configured,
)
from app.services.jira_client import fetch_jira_provider_members
from app.services.notion_client import fetch_notion_member_records

logger = logging.getLogger(__name__)

_PROVIDER_MEMBERS_CACHE_TTL_SECONDS = 900.0
_provider_members_cache: dict[tuple[str, str], tuple[float, list[ProviderMember]]] = {}


def invalidate_provider_members_cache(
    tenant_id: uuid.UUID | None = None,
    provider: str | None = None,
) -> None:
    """Drop cached provider member lists (e.g. after integration sync)."""
    if tenant_id is None and provider is None:
        _provider_members_cache.clear()
        return
    tenant_key = str(tenant_id) if tenant_id is not None else None
    keys_to_drop = [
        key
        for key in _provider_members_cache
        if (tenant_key is None or key[0] == tenant_key)
        and (provider is None or key[1] == provider)
    ]
    for key in keys_to_drop:
        _provider_members_cache.pop(key, None)


def cache_provider_members(
    tenant_id: uuid.UUID,
    provider: str,
    members: list[ProviderMember],
) -> None:
    _provider_members_cache[(str(tenant_id), provider)] = (time.time(), list(members))


def get_cached_provider_members(
    tenant_id: uuid.UUID,
    provider: str,
) -> list[ProviderMember] | None:
    cached = _provider_members_cache.get((str(tenant_id), provider))
    if not cached:
        return None
    cached_at, members = cached
    if (time.time() - cached_at) >= _PROVIDER_MEMBERS_CACHE_TTL_SECONDS:
        _provider_members_cache.pop((str(tenant_id), provider), None)
        return None
    return list(members)


def _records_to_members(records: list[MasterDataRecord]) -> list[ProviderMember]:
    members: list[ProviderMember] = []
    for record in records:
        email = str(record.email).strip() or None
        username = None
        if email and "@" in email:
            username = email.split("@", 1)[0]
        members.append(
            ProviderMember(
                id=record.external_id,
                label=record.name,
                email=email,
                username=username,
            )
        )
    return members


def _fetch_slack_provider_members(token: str) -> list[ProviderMember]:
    """Slack users for identity mapping — includes @handles for dropdown labels."""
    records = _fetch_slack_users_live(token)

    headers = {"Authorization": f"Bearer {token.strip()}"}
    handles_by_id: dict[str, str] = {}
    cursor: str | None = None
    while True:
        params: dict[str, str] = {"limit": "200"}
        if cursor:
            params["cursor"] = cursor
        response = requests.get(
            "https://slack.com/api/users.list",
            headers=headers,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            break
        for member in payload.get("members", []):
            if member.get("deleted") or member.get("is_bot"):
                continue
            member_id = str(member.get("id", "")).strip()
            login = str(member.get("name") or "").strip()
            if member_id and login:
                handles_by_id[member_id] = login if login.startswith("@") else f"@{login}"
        cursor = (payload.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break

    members: list[ProviderMember] = []
    for record in records:
        email = str(record.email).strip() or None
        handle = handles_by_id.get(record.external_id)
        members.append(
            ProviderMember(
                id=record.external_id,
                label=record.name,
                email=email,
                username=handle,
            )
        )
    return members


def _has_integration_credentials(
    db: Session,
    tenant_id: uuid.UUID,
    provider: str,
) -> bool:
    if is_source_configured(db, tenant_id, provider):
        return True
    stored = get_all_configs(db, tenant_id).get(provider, {})
    if provider == "jira":
        return bool(stored.get("site_url", "").strip() and stored.get("api_token", "").strip())
    if provider == "github":
        repository_urls = [
            url.strip()
            for url in (stored.get("repository_urls") or [])
            if str(url).strip()
        ]
        repository_url = (stored.get("repository_url") or "").strip()
        has_repo = bool(repository_urls or repository_url)
        return has_repo and bool(
            stored.get("personal_access_token", "").strip() or stored.get("oauth_connected")
        )
    if provider == "slack":
        return bool(stored.get("bot_token", "").strip())
    if provider == "notion":
        return bool(stored.get("integration_token", "").strip())
    return False


def fetch_live_provider_members(
    db: Session,
    tenant_id: uuid.UUID,
    provider: str,
) -> list[ProviderMember] | None:
    """
    Return live members when the tenant has a configured integration.
    Returns None when the provider is not configured (caller may use demo data).
    Returns [] when configured but the live API returned no users.
    """
    if not _has_integration_credentials(db, tenant_id, provider):
        return None

    cached = get_cached_provider_members(tenant_id, provider)
    if cached is not None:
        return cached

    try:
        if provider == "jira":
            config = get_jira_config(db, tenant_id)
            if not config:
                return _store_live_provider_members(tenant_id, provider, [])
            return _store_live_provider_members(
                tenant_id,
                provider,
                fetch_jira_provider_members(config),
            )

        if provider == "github":
            config = get_github_config(db, tenant_id)
            if not config:
                return _store_live_provider_members(tenant_id, provider, [])
            return _store_live_provider_members(
                tenant_id,
                provider,
                fetch_github_provider_members(config),
            )

        if provider == "slack":
            stored = get_all_configs(db, tenant_id)["slack"]
            token = (stored.get("bot_token") or "").strip()
            if not token:
                return _store_live_provider_members(tenant_id, provider, [])
            return _store_live_provider_members(
                tenant_id,
                provider,
                _fetch_slack_provider_members(token),
            )

        if provider == "notion":
            stored = get_all_configs(db, tenant_id)["notion"]
            token = (stored.get("integration_token") or "").strip()
            if not token:
                return _store_live_provider_members(tenant_id, provider, [])
            database_ids = (stored.get("database_ids") or "").strip() or None
            records = fetch_notion_member_records(token, database_ids)
            return _store_live_provider_members(
                tenant_id,
                provider,
                _records_to_members(records),
            )
    except Exception as exc:
        logger.warning("Live provider member fetch failed for %s: %s", provider, exc)
        cache_provider_members(tenant_id, provider, [])
        return []

    cache_provider_members(tenant_id, provider, [])
    return []


def _store_live_provider_members(
    tenant_id: uuid.UUID,
    provider: str,
    members: list[ProviderMember],
) -> list[ProviderMember]:
    cache_provider_members(tenant_id, provider, members)
    return members


def get_provider_members_for_tenant(
    db: Session,
    tenant_id: uuid.UUID,
    provider: str,
    *,
    fallback_members: list[ProviderMember] | None = None,
) -> tuple[list[ProviderMember], str | None]:
    configured = _has_integration_credentials(db, tenant_id, provider)
    live = fetch_live_provider_members(db, tenant_id, provider)

    if live is not None:
        if not live and configured:
            if provider == "jira":
                return [], (
                    "No Jira users found. Re-save a valid API token, account email, "
                    "and project key under Settings → Integrations."
                )
            return [], (
                f"No {provider} users found. Verify credentials under Settings → Integrations."
            )
        return live, None

    if configured:
        return [], (
            f"Could not load {provider} members. Verify credentials under Settings → Integrations."
        )

    return list(fallback_members or []), None


def find_provider_member(
    provider: str,
    provider_user_id: str,
    *,
    fallback_members: list[ProviderMember] | None = None,
) -> ProviderMember | None:
    provider_user_id = provider_user_id.strip()
    if not provider_user_id:
        return None
    for member in fallback_members or []:
        if member.id == provider_user_id:
            return member
    return None


def build_fetch_users_request(
    db: Session,
    tenant_id: uuid.UUID,
    source: str,
) -> FetchUsersRequest:
    """Build credentials payload for employee_master_fetch from stored integration config."""
    return build_fetch_users_request_for_sources(db, tenant_id, [source])


def build_fetch_users_request_for_sources(
    db: Session,
    tenant_id: uuid.UUID,
    sources: list[str],
) -> FetchUsersRequest:
    stored = get_all_configs(db, tenant_id)
    normalized = [source.lower().strip() for source in sources if source.strip()]
    slack = stored.get("slack", {})
    notion = stored.get("notion", {})
    github = stored.get("github", {})
    jira = stored.get("jira", {})
    repository_urls = [
        url.strip()
        for url in (github.get("repository_urls") or [])
        if str(url).strip()
    ]
    repository_url = (github.get("repository_url") or "").strip()
    if not repository_url and repository_urls:
        repository_url = repository_urls[0]

    return FetchUsersRequest(
        sources=normalized,
        slack_bot_token=slack.get("bot_token"),
        notion_integration_token=notion.get("integration_token"),
        notion_database_ids=notion.get("database_ids"),
        github_repository_url=repository_url or None,
        github_personal_access_token=github.get("personal_access_token"),
        jira_site_url=jira.get("site_url"),
        jira_api_token=jira.get("api_token"),
        jira_account_email=jira.get("account_email"),
        jira_project_keys=jira.get("project_keys"),
    )
