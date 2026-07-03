"""Tests for post-onboarding identity refresh."""

from __future__ import annotations

from unittest.mock import patch

from app.models.operational import EmployeeIdentity
from app.schemas.identity import ProviderMember
from app.services.identity_auto_map import auto_map_provider_member_identities
from app.services.identity_sync import sync_provider_identity_members

from tests.conftest import add_employee


def test_auto_map_provider_member_identities_skips_confirmed(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-1",
        name="Alice Chen",
        email="alice@acme.com",
    )
    db.add(
        EmployeeIdentity(
            tenant_id=tenant.id,
            employee_id="emp-1",
            provider="slack",
            provider_username_or_id="U01ALICE",
            confidence="confirmed",
        )
    )
    db.commit()

    members = [
        ProviderMember(id="U02NEW", label="Alice Chen", email="alice@acme.com"),
    ]
    created = auto_map_provider_member_identities(db, tenant.id, "slack", members)
    assert created == 0


def test_sync_provider_identity_members_uses_live_fetch(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-jira",
        name="Ops User",
        email="ops@acme.com",
    )
    live_members = [
        ProviderMember(id="acc-ops", label="Ops User", email="ops@acme.com"),
    ]

    with patch(
        "app.services.identity_sync.fetch_live_provider_members",
        return_value=live_members,
    ):
        result = sync_provider_identity_members(db, tenant.id, "jira")

    assert result["members_fetched"] == 1
    assert result["mappings_created"] == 1
    row = (
        db.query(EmployeeIdentity)
        .filter(
            EmployeeIdentity.tenant_id == tenant.id,
            EmployeeIdentity.provider == "jira",
            EmployeeIdentity.provider_username_or_id == "acc-ops",
        )
        .one()
    )
    assert row.employee_id == "emp-jira"
