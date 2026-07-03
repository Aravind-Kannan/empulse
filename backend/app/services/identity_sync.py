"""Refresh provider member lists and auto-populate identity mappings post-onboarding."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.schemas.employee_master import FetchUsersRequest
from app.schemas.identity import ProviderMember
from app.services.identity_auto_map import auto_map_provider_member_identities
from app.services.identity_mapping import PROVIDERS
from app.services.integration_config_store import get_github_config
from app.services.provider_members import (
    build_fetch_users_request,
    build_fetch_users_request_for_sources,
    fetch_live_provider_members,
)

logger = logging.getLogger(__name__)


def _fetch_provider_members_for_sync(
    db: Session,
    tenant_id: uuid.UUID,
    provider: str,
) -> tuple[list[ProviderMember], str | None]:
    if provider == "github":
        from app.services.github_identity import (
            cache_github_provider_members,
            fetch_github_provider_members,
        )

        config = get_github_config(db, tenant_id)
        if not config:
            return [], "GitHub integration is not configured."
        members = fetch_github_provider_members(config)
        cache_github_provider_members(tenant_id, members)
        return members, None

    live = fetch_live_provider_members(db, tenant_id, provider)
    if live is None:
        return [], f"{provider} integration is not configured."
    return live, None


def sync_provider_identity_members(
    db: Session,
    tenant_id: uuid.UUID,
    provider: str,
) -> dict[str, int | str | None]:
    """Pull live provider members and auto-map identities for one provider."""
    normalized = provider.lower().strip()
    if normalized not in PROVIDERS:
        return {
            "provider": normalized,
            "members_fetched": 0,
            "mappings_created": 0,
            "warning": f"Unknown provider '{provider}'.",
        }

    members, warning = _fetch_provider_members_for_sync(db, tenant_id, normalized)
    if warning:
        return {
            "provider": normalized,
            "members_fetched": 0,
            "mappings_created": 0,
            "warning": warning,
        }

    if not members:
        return {
            "provider": normalized,
            "members_fetched": 0,
            "mappings_created": 0,
            "warning": (
                f"No {normalized} members returned. Verify credentials under "
                "Settings → Integrations."
            ),
        }

    created = auto_map_provider_member_identities(db, tenant_id, normalized, members)
    return {
        "provider": normalized,
        "members_fetched": len(members),
        "mappings_created": created,
        "warning": None,
    }


async def refresh_identity_mappings(
    db: Session,
    tenant: Tenant,
    *,
    providers: list[str] | None = None,
    import_roster: bool = False,
    credentials: FetchUsersRequest | None = None,
) -> dict[str, object]:
    """
    Pull provider member directories and auto-map identities by email.

    Optionally merge imported employees into the tenant roster first.
    """
    from app.services.member_roster_sync import sync_member_roster

    active_providers = [
        provider.lower().strip()
        for provider in (providers or list(PROVIDERS))
        if provider.lower().strip() in PROVIDERS
    ]
    if not active_providers:
        raise ValueError("Provide at least one provider: github, jira, slack, or notion.")

    roster_result: dict[str, object] | None = None
    if import_roster:
        roster_credentials = credentials
        if roster_credentials is None:
            roster_credentials = build_fetch_users_request_for_sources(
                db,
                tenant.id,
                active_providers,
            )
        roster_sources = [
            source
            for source in roster_credentials.sources or active_providers
            if source in PROVIDERS
        ]
        if not roster_sources:
            roster_sources = active_providers
        roster_result = await sync_member_roster(
            db,
            tenant,
            roster_credentials.model_copy(update={"sources": roster_sources}),
        )

    provider_results: list[dict[str, int | str | None]] = []
    total_created = 0
    for provider in active_providers:
        result = sync_provider_identity_members(db, tenant.id, provider)
        provider_results.append(result)
        total_created += int(result.get("mappings_created") or 0)

    from app.services.unmapped_activity import reconcile_and_prune_unmapped_activity

    reconcile_and_prune_unmapped_activity(db, tenant.id, commit=True)

    return {
        "providers": provider_results,
        "total_mappings_created": total_created,
        "roster": roster_result,
    }
