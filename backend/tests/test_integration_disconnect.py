"""Tests for integration disconnect helpers."""

from __future__ import annotations

from uuid import UUID

from app.services.integration_disconnect import external_key_to_node_id
from app.services.integration_sync import (
    GraphCodeFile,
    GraphJiraTicket,
    GraphNotionPage,
    GraphPullRequest,
    GraphSlackThread,
)


def test_github_pr_external_key_maps_to_node_id():
    external_key = "https://github.com/acme/api|42|abc123|src/main.py"
    node_id = external_key_to_node_id("github", external_key)
    assert node_id == GraphPullRequest.id_for(
        "https://github.com/acme/api",
        42,
        "abc123",
        "src/main.py",
    )


def test_github_code_external_key_maps_to_node_id():
    external_key = "code|https://github.com/acme/api|src/main.py|deadbeef"
    node_id = external_key_to_node_id("github", external_key)
    assert node_id == GraphCodeFile.id_for(
        "https://github.com/acme/api",
        "src/main.py",
        "deadbeef",
    )


def test_jira_external_key_maps_to_node_id():
    assert external_key_to_node_id("jira", "ENG-123") == GraphJiraTicket.id_for("ENG-123")


def test_notion_external_key_maps_to_node_id():
    page_id = "page-abc"
    assert external_key_to_node_id("notion", page_id) == GraphNotionPage.id_for(page_id)


def test_slack_external_key_maps_to_node_id():
    thread_id = "C123.1234567890.123456"
    assert external_key_to_node_id("slack", thread_id) == GraphSlackThread.id_for(thread_id)


def test_external_key_to_node_id_returns_uuid():
    node_id = external_key_to_node_id("jira", "OPS-1")
    assert isinstance(node_id, UUID)
