"""Tests for Jira user email resolution."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.jira_user_email import (
    bulk_resolve_jira_user_emails,
    enrich_jira_users_with_emails,
    is_synthetic_jira_email,
    resolve_jira_user_email,
)


def test_is_synthetic_jira_email():
    assert is_synthetic_jira_email("alice+abc@jira.import")
    assert not is_synthetic_jira_email("alice@acme.com")


def test_resolve_jira_user_email_from_email_endpoint():
    with patch("app.services.jira_user_email.requests.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"accountId": "acc-1", "email": "alice@acme.com"},
        )
        email = resolve_jira_user_email(
            "https://acme.atlassian.net",
            "acc-1",
            auth=("ops@acme.com", "token"),
        )
    assert email == "alice@acme.com"


def test_bulk_resolve_jira_user_emails():
    with patch("app.services.jira_user_email.requests.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {"accountId": "acc-1", "email": "alice@acme.com"},
                {"accountId": "acc-2", "email": "ben@acme.com"},
            ],
        )
        emails = bulk_resolve_jira_user_emails(
            "https://acme.atlassian.net",
            ["acc-1", "acc-2"],
            auth=("ops@acme.com", "token"),
        )
    assert emails == {
        "acc-1": "alice@acme.com",
        "acc-2": "ben@acme.com",
    }


def test_enrich_jira_users_with_emails_uses_inline_and_bulk():
    users = [
        {"accountId": "acc-1", "emailAddress": "inline@acme.com"},
        {"accountId": "acc-2", "displayName": "Ben Rivera"},
    ]
    with patch(
        "app.services.jira_user_email.bulk_resolve_jira_user_emails",
        return_value={"acc-2": "ben@acme.com"},
    ):
        emails = enrich_jira_users_with_emails(
            "https://acme.atlassian.net",
            users,
            auth=("ops@acme.com", "token"),
        )
    assert emails["acc-1"] == "inline@acme.com"
    assert emails["acc-2"] == "ben@acme.com"
