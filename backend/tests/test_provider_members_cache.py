from unittest.mock import patch

from app.services.provider_members import (
    cache_provider_members,
    fetch_live_provider_members,
    get_cached_provider_members,
    invalidate_provider_members_cache,
)
from app.services.integration_config_store import save_slack_config
from app.schemas.integrations import SlackConfigRequest


def test_fetch_live_provider_members_uses_slack_cache(db, tenant):
    save_slack_config(
        db,
        tenant.id,
        SlackConfigRequest(
            workspace_url="https://acme.slack.com",
            bot_token="xoxb-test",
        ),
    )
    db.commit()
    invalidate_provider_members_cache()

    with patch(
        "app.services.provider_members._fetch_slack_users_live",
        return_value=[],
    ) as mock_fetch:
        first = fetch_live_provider_members(db, tenant.id, "slack")
        second = fetch_live_provider_members(db, tenant.id, "slack")

    assert first == []
    assert second == []
    mock_fetch.assert_called_once()


def test_cache_provider_members_round_trip(tenant):
    invalidate_provider_members_cache()
    cache_provider_members(
        tenant.id,
        "slack",
        [],
    )
    assert get_cached_provider_members(tenant.id, "slack") == []
