"""Slack external file upload helper tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.slack_client import upload_markdown_to_channel


def test_upload_markdown_to_channel_uses_external_upload_flow():
    with (
        patch(
            "app.services.slack_client._slack_api_post",
            return_value={
                "upload_url": "https://files.slack.com/upload/v1/ABC",
                "file_id": "F123",
            },
        ) as post_form,
        patch("app.services.slack_client.requests.post") as raw_post,
        patch(
            "app.services.slack_client._slack_api_post_json",
            return_value={"files": [{"id": "F123"}]},
        ) as post_json,
    ):
        raw_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

        file_id = upload_markdown_to_channel(
            "xoxb-test",
            channel_id="D999",
            filename="handover-alice.md",
            content="# Handover\n\nBody",
            title="Handover — Alice",
            initial_comment="Attached handover pack.",
        )

    assert file_id == "F123"
    post_form.assert_called_once()
    assert post_form.call_args.kwargs["context"] == "files.getUploadURLExternal"
    raw_post.assert_called_once()
    post_json.assert_called_once()
    assert post_json.call_args.kwargs["json_body"]["channel_id"] == "D999"
    assert post_json.call_args.kwargs["json_body"]["files"][0]["id"] == "F123"


def test_upload_markdown_to_channel_rejects_oversized_payload():
    with pytest.raises(ValueError, match="Slack upload limit"):
        upload_markdown_to_channel(
            "xoxb-test",
            channel_id="D999",
            filename="handover-huge.md",
            content="x" * 1_000_001,
            title="Huge",
            initial_comment="Too big",
        )
