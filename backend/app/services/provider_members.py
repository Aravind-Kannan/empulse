"""Load live provider member lists for identity mapping."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.schemas.employee_master import FetchUsersRequest, MasterDataRecord
from app.schemas.identity import ProviderMember
from app.services.employee_master_fetch import (
    _fetch_github_org_members_live,
    _fetch_slack_users_live,
)
from app.services.integration_config_store import (
    get_all_configs,
    get_github_config,
    get_jira_config,
    is_source_configured,
)
from app.services.jira_client import fetch_jira_provider_members
from app.services.notion_client import fetch_notion_member_records

logger = logging.getLogger(__name__)


def _records_to_members(records: list[MasterDataRecord]) -> list[ProviderMember]:
    members: list[ProviderMember] = []
    for record in records:
        email = str(record.email).strip() or None
        members.append(
            ProviderMember(
                id=record.external_id,
                label=record.name,
                email=email,
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
        return bool(stored.get("repository_url", "").strip()) and bool(
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

    try:
        if provider == "jira":
            config = get_jira_config(db, tenant_id)
            if not config:
                return []
            return fetch_jira_provider_members(config)

        if provider == "github":
            config = get_github_config(db, tenant_id)
            if not config:
                return []
            records = _fetch_github_org_members_live(
                config.repository_url,
                config.personal_access_token,
            )
            return _records_to_members(records)

        if provider == "slack":
            stored = get_all_configs(db, tenant_id)["slack"]
            token = (stored.get("bot_token") or "").strip()
            if not token:
                return []
            records = _fetch_slack_users_live(token)
            return _records_to_members(records)

        if provider == "notion":
            stored = get_all_configs(db, tenant_id)["notion"]
            token = (stored.get("integration_token") or "").strip()
            if not token:
                return []
            database_ids = (stored.get("database_ids") or "").strip() or None
            records = fetch_notion_member_records(token, database_ids)
            return _records_to_members(records)
    except Exception as exc:
        logger.warning("Live provider member fetch failed for %s: %s", provider, exc)
        return []

    return []


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
    stored = get_all_configs(db, tenant_id)
    row = stored.get(source, {})
    return FetchUsersRequest(
        sources=[source],
        slack_bot_token=row.get("bot_token") if source == "slack" else None,
        notion_integration_token=row.get("integration_token") if source == "notion" else None,
        notion_database_ids=row.get("database_ids") if source == "notion" else None,
        github_repository_url=row.get("repository_url") if source == "github" else None,
        github_personal_access_token=(
            row.get("personal_access_token") if source == "github" else None
        ),
        jira_site_url=row.get("site_url") if source == "jira" else None,
        jira_api_token=row.get("api_token") if source == "jira" else None,
        jira_account_email=row.get("account_email") if source == "jira" else None,
        jira_project_keys=row.get("project_keys") if source == "jira" else None,
    )
