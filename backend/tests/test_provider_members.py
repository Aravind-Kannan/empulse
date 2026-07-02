"""Tests for live provider member loading."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.schemas.integrations import JiraConfigRequest
from app.services.integration_config_store import save_jira_config
from app.services.identity_mapping import get_provider_members, get_reconciliation
from app.services.jira_client import fetch_jira_provider_members

from tests.conftest import add_employee


def test_fetch_jira_provider_members_maps_account_ids():
    config = JiraConfigRequest(
        site_url="https://acme.atlassian.net",
        project_keys="SCRUM",
        api_token="token",
        account_email="ops@acme.com",
    )
    assignable = [
        {
            "accountId": "acc-001",
            "displayName": "Alice Chen",
            "emailAddress": "alice@acme.com",
        }
    ]

    with patch("app.services.jira_client.requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: assignable)
        with patch("app.services.jira_client.JiraClient.fetch_open_issues", return_value=[]):
            members = fetch_jira_provider_members(config)

    assert len(members) == 1
    assert members[0].id == "acc-001"
    assert members[0].email == "alice@acme.com"
    assert "Alice Chen" in members[0].label


def test_reconciliation_uses_live_jira_members(db, tenant):
    save_jira_config(
        db,
        tenant.id,
        JiraConfigRequest(
            site_url="https://acme.atlassian.net",
            project_keys="SCRUM",
            api_token="token",
            account_email="ops@acme.com",
        ),
    )
    add_employee(
        db,
        tenant.id,
        employee_id="emp-001",
        name="Alice Chen",
        email="alice@acme.com",
    )

    live_members = [
        __import__("app.schemas.identity", fromlist=["ProviderMember"]).ProviderMember(
            id="acc-001",
            label="Alice Chen",
            email="alice@acme.com",
        )
    ]

    with patch(
        "app.services.provider_members.get_provider_members_for_tenant",
        return_value=(live_members, None),
    ):
        response = get_reconciliation(db, tenant, connected_providers=["jira"])

    assert response.provider_members["jira"][0].id == "acc-001"
    assert response.provider_members["jira"][0].label == "Alice Chen"
    assert response.employees[0].mappings["jira"] == "acc-001"


def test_get_provider_members_falls_back_to_mock_without_config(db, tenant):
    members = get_provider_members("jira", db, tenant.id)
    assert any(member.email == "alice.chen@acme.com" for member in members)
