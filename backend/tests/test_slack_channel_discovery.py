"""Slack auto channel discovery tests (Prompt 28)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.schemas.integrations import SlackConfigRequest
from app.services.slack_client import (
    discover_channel_ids,
    fetch_slack_incident_threads,
    list_accessible_channels,
    resolve_sync_channels,
)


def _conversations_list_payload(
    channels: list[dict],
    *,
    next_cursor: str = "",
) -> dict:
    return {
        "ok": True,
        "channels": channels,
        "response_metadata": {"next_cursor": next_cursor},
    }


def test_discover_channel_ids_paginates_and_filters_non_members():
    page_one = _conversations_list_payload(
        [
            {
                "id": "C_PUBLIC",
                "name": "general",
                "is_private": False,
                "is_member": True,
                "num_members": 42,
            },
            {
                "id": "C_OTHER",
                "name": "other-team",
                "is_private": False,
                "is_member": False,
                "num_members": 10,
            },
        ],
        next_cursor="cursor-2",
    )
    page_two = _conversations_list_payload(
        [
            {
                "id": "C_PRIVATE",
                "name": "incidents",
                "is_private": True,
                "is_member": True,
                "num_members": 5,
            },
        ],
    )

    mock_response_one = MagicMock()
    mock_response_one.raise_for_status = MagicMock()
    mock_response_one.json.return_value = page_one
    mock_response_two = MagicMock()
    mock_response_two.raise_for_status = MagicMock()
    mock_response_two.json.return_value = page_two

    with patch(
        "app.services.slack_client.requests.get",
        side_effect=[mock_response_one, mock_response_two],
    ) as mock_get:
        ids = discover_channel_ids("xoxb-test-token")

    assert ids == ["C_PUBLIC", "C_PRIVATE"]
    assert mock_get.call_count == 2
    first_params = mock_get.call_args_list[0].kwargs["params"]
    second_params = mock_get.call_args_list[1].kwargs["params"]
    assert first_params["types"] == "public_channel,private_channel"
    assert first_params["exclude_archived"] == "true"
    assert second_params["cursor"] == "cursor-2"


def test_list_accessible_channels_raises_on_missing_scope():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"ok": False, "error": "missing_scope"}

    with patch("app.services.slack_client.requests.get", return_value=mock_response):
        with pytest.raises(ValueError, match="missing required channel scopes"):
            list_accessible_channels("xoxb-test-token")


def test_resolve_sync_channels_auto_discovers_when_allowlist_empty():
    channels = [
        {"id": "C1", "name": "general", "is_private": False, "is_member": True},
        {"id": "C2", "name": "eng", "is_private": False, "is_member": True},
        {"id": "C3", "name": "secret", "is_private": True, "is_member": False},
    ]
    with patch(
        "app.services.slack_client.list_accessible_channels",
        return_value=channels,
    ):
        configured, incident, on_call, id_to_name, discovered = resolve_sync_channels(
            "xoxb-test",
            SlackConfigRequest(),
        )

    assert discovered == 2
    assert configured == {"C1", "C2"}
    assert incident == {"C1", "C2"}
    assert on_call == {"C1", "C2"}
    assert id_to_name == {"C1": "general", "C2": "eng"}


def test_resolve_sync_channels_allowlist_overrides_discovery():
    channels = [
        {"id": "C1", "name": "general", "is_private": False, "is_member": True},
        {"id": "C2", "name": "eng", "is_private": False, "is_member": True},
    ]
    with patch(
        "app.services.slack_client.list_accessible_channels",
        return_value=channels,
    ):
        configured, incident, on_call, _, discovered = resolve_sync_channels(
            "xoxb-test",
            SlackConfigRequest(channel_ids="C2"),
        )

    assert discovered == 2
    assert configured == {"C2"}
    assert incident == {"C2"}
    assert on_call == {"C2"}


def test_fetch_slack_incident_threads_empty_channel_ids_discovers_all():
    config = SlackConfigRequest(
        workspace_url="https://acme.slack.com",
        bot_token="xoxb-test",
    )
    history = [
        {
            "ts": "1717200000.000100",
            "user": "U_ALICE",
            "text": "#incident payments latency",
            "thread_ts": "1717200000.000100",
        },
        {
            "ts": "1717200060.000200",
            "user": "U_BEN",
            "text": "checking metrics",
        },
        {
            "ts": "1717203600.000400",
            "user": "U_BEN",
            "text": "resolved — mitigated",
            "reactions": ["white_check_mark"],
        },
    ]

    with (
        patch(
            "app.services.slack_client.resolve_sync_channels",
            return_value=(
                {"C_INC"},
                {"C_INC"},
                {"C_INC"},
                {"C_INC": "incidents"},
                3,
            ),
        ),
        patch(
            "app.services.slack_client.fetch_channel_history",
            return_value=history,
        ) as mock_history,
        patch(
            "app.services.slack_client._fetch_thread_replies",
            return_value=history,
        ),
    ):
        threads, _, warnings, stats = fetch_slack_incident_threads(config)

    assert not warnings
    assert stats["channels_discovered"] == 3
    assert stats["channels_synced"] == 1
    assert stats["messages_ingested"] >= len(history)
    assert threads
    assert threads[0].channel_name == "incidents"
    mock_history.assert_called_once()


def test_fetch_slack_incident_threads_allowlist_limits_sync():
    config = SlackConfigRequest(
        workspace_url="https://acme.slack.com",
        bot_token="xoxb-test",
        channel_ids="C_ALLOW",
    )

    with (
        patch(
            "app.services.slack_client.resolve_sync_channels",
            return_value=(
                {"C_ALLOW"},
                {"C_ALLOW"},
                set(),
                {"C_ALLOW": "allowed"},
                5,
            ),
        ) as mock_resolve,
        patch(
            "app.services.slack_client.fetch_channel_history",
            return_value=[],
        ),
    ):
        _, _, _, stats = fetch_slack_incident_threads(config)

    mock_resolve.assert_called_once_with("xoxb-test", config)
    assert stats["channels_discovered"] == 5
    assert stats["channels_synced"] == 1
