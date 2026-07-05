"""GitHub roster import must not create employees from noreply emails."""

from __future__ import annotations

from unittest.mock import patch

from app.schemas.identity import ProviderMember
from app.services.employee_master_fetch import _fetch_github_org_members_live
from app.services.identity_auto_map import is_usable_roster_email


def test_is_usable_roster_email_rejects_github_noreply():
    assert is_usable_roster_email("aravind@company.com") is True
    assert is_usable_roster_email("Aravind-Kannan@users.noreply.github.com") is False
    assert is_usable_roster_email(None) is False
    assert is_usable_roster_email("") is False


def test_fetch_github_roster_imports_contributors_with_public_email():
    members = [
        ProviderMember(
            id="gh-alice",
            label="Alice Chen",
            email="alice@acme.com",
        ),
        ProviderMember(
            id="gh-bob",
            label="Bob Dev",
            email=None,
        ),
    ]

    with patch(
        "app.services.github_identity.fetch_github_provider_members",
        return_value=members,
    ):
        records, note = _fetch_github_org_members_live(
            "https://github.com/acme/api",
            "token",
        )

    assert note is None
    assert len(records) == 1
    assert records[0].email == "alice@acme.com"
    assert records[0].name == "Alice Chen"
    assert records[0].external_id == "gh-alice"


def test_fetch_github_roster_reports_when_all_contributors_hide_email():
    members = [
        ProviderMember(id="gh-bob", label="Bob Dev", email=None),
        ProviderMember(
            id="gh-noreply",
            label="Noreply User",
            email="noreply@users.noreply.github.com",
        ),
    ]

    with patch(
        "app.services.github_identity.fetch_github_provider_members",
        return_value=members,
    ):
        records, note = _fetch_github_org_members_live(
            "https://github.com/personal-owner/repo",
            "token",
        )

    assert records == []
    assert note is not None
    assert "identity mapping" in note


def test_fetch_github_roster_empty_when_no_contributors():
    with patch(
        "app.services.github_identity.fetch_github_provider_members",
        return_value=[],
    ):
        records, note = _fetch_github_org_members_live(
            "https://github.com/acme/api",
            "token",
        )

    assert records == []
    assert note is not None
    assert "No GitHub contributors found" in note


def test_fetch_employee_master_data_allows_empty_github_roster_with_skip():
    from app.schemas.employee_master import FetchUsersRequest
    from app.services.employee_master_fetch import fetch_employee_master_data

    with patch(
        "app.services.employee_master_fetch._fetch_github_org_members_live",
        return_value=(
            [],
            "2 contributors found but none have a public profile email",
        ),
    ):
        result = fetch_employee_master_data(
            ["github"],
            company="Acme",
            credentials=FetchUsersRequest(
                sources=["github"],
                company="Acme",
                github_repository_url="https://github.com/acme/api",
                github_personal_access_token="token",
            ),
            skip_failed_sources=True,
        )

    assert result.employees == []
    assert any("public profile email" in err for err in result.source_errors)
