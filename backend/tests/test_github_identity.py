"""Tests for GitHub contributor identity mapping."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.models.operational import EmployeeIdentity
from app.schemas.integrations import GitHubConfigRequest
from app.services.github_identity import (
    fetch_github_provider_members,
    github_provider_user_id,
    prepare_github_identity_context,
    sync_github_contributor_identities,
)
from app.services.identity_resolver import resolve_employee

from tests.conftest import add_employee


def test_github_provider_user_id_prefixes_login():
    assert github_provider_user_id("alicechen") == "gh-alicechen"


def test_fetch_github_provider_members_merges_repo_contributors():
    config = GitHubConfigRequest(
        repository_url="https://github.com/acme/api",
        personal_access_token="token",
    )

    def fake_paginate(session, token, path, **kwargs):
        if path.endswith("/contributors"):
            return [{"login": "alicechen", "type": "User"}]
        if path.endswith("/collaborators"):
            return [{"login": "bobdev", "type": "User"}]
        if path.endswith("/members"):
            return [{"login": "carapatel"}]
        return []

    profiles = {
        "alicechen": {"login": "alicechen", "name": "Alice Chen", "email": "alice@acme.com", "type": "User"},
        "bobdev": {"login": "bobdev", "name": "Bob Dev", "email": None, "type": "User"},
        "carapatel": {"login": "carapatel", "name": "Cara Patel", "email": "cara@acme.com", "type": "User"},
    }

    with patch("app.services.github_identity._paginate_github", side_effect=fake_paginate):
        with patch(
            "app.services.github_identity._resolve_org_for_repo",
            return_value="acme",
        ):
            with patch("app.services.github_identity._fetch_user_profile") as mock_profile:
                mock_profile.side_effect = lambda session, token, login: profiles[login]
                members = fetch_github_provider_members(config)

    ids = {member.id for member in members}
    assert ids == {"gh-alicechen", "gh-bobdev", "gh-carapatel"}
    assert next(member for member in members if member.id == "gh-alicechen").email == "alice@acme.com"


def test_fetch_github_provider_members_uses_contributors_for_personal_repo():
    config = GitHubConfigRequest(
        repository_url="https://github.com/personal-dev/my-repo",
        personal_access_token="token",
    )

    def fake_paginate(session, token, path, **kwargs):
        if path.endswith("/contributors"):
            return [{"login": "personal-dev", "type": "User"}]
        if path.endswith("/collaborators"):
            return []
        return []

    profiles = {
        "personal-dev": {
            "login": "personal-dev",
            "name": "Personal Dev",
            "email": None,
            "type": "User",
        },
    }

    with patch("app.services.github_identity._paginate_github", side_effect=fake_paginate):
        with patch(
            "app.services.github_identity._resolve_org_for_repo",
            return_value=None,
        ):
            with patch("app.services.github_identity._fetch_user_profile") as mock_profile:
                mock_profile.side_effect = lambda session, token, login: profiles[login]
                members = fetch_github_provider_members(config)

    assert len(members) == 1
    assert members[0].id == "gh-personal-dev"
    assert members[0].email is None


def test_sync_github_contributor_identities_creates_high_confidence_rows(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-alice",
        name="Alice Chen",
        email="alice@acme.com",
    )
    members = [
        __import__("app.schemas.identity", fromlist=["ProviderMember"]).ProviderMember(
            id="gh-alicechen",
            label="Alice Chen",
            email="alice@acme.com",
        )
    ]

    created = sync_github_contributor_identities(db, tenant.id, members)
    assert created == 1

    row = (
        db.query(EmployeeIdentity)
        .filter(
            EmployeeIdentity.tenant_id == tenant.id,
            EmployeeIdentity.provider == "github",
            EmployeeIdentity.provider_username_or_id == "gh-alicechen",
        )
        .one()
    )
    assert row.employee_id == "emp-alice"
    assert row.confidence == "high"


def test_prepare_github_identity_context_enables_resolver(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-alice",
        name="Alice Chen",
        email="alice@acme.com",
    )
    config = GitHubConfigRequest(
        repository_url="https://github.com/acme/api",
        personal_access_token="token",
    )
    members = [
        __import__("app.schemas.identity", fromlist=["ProviderMember"]).ProviderMember(
            id="gh-alicechen",
            label="Alice Chen",
            email="alice@acme.com",
        )
    ]

    with patch(
        "app.services.github_identity.fetch_github_provider_members",
        return_value=members,
    ):
        prepare_github_identity_context(db, tenant.id, config)

    result = resolve_employee(db, tenant.id, "github", "gh-alicechen")
    assert result.employee_id == "emp-alice"
    assert result.confidence in {"high", "confirmed"}
