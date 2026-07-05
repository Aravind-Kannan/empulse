"""Tests for identity auto-mapping heuristics."""

from __future__ import annotations

from app.models.operational import Employee
from app.schemas.identity import ProviderMember
from app.services.identity_auto_map import auto_map_provider_member_identities
from app.services.identity_mapping import guess_provider_member_id

from tests.conftest import add_employee


def test_guess_provider_member_id_matches_email():
    employee = Employee(
        id="emp-1",
        tenant_id="00000000-0000-4000-8000-000000000001",
        name="Alice Chen",
        email="alice@acme.com",
        role="Engineer",
    )
    members = [
        ProviderMember(id="gh-alicechen", label="alicechen", email=None),
        ProviderMember(id="acc-1", label="Alice Chen", email="alice@acme.com"),
    ]
    assert guess_provider_member_id(employee, members) == "acc-1"


def test_guess_provider_member_id_matches_github_login_without_email():
    employee = Employee(
        id="emp-1",
        tenant_id="00000000-0000-4000-8000-000000000001",
        name="Alice Chen",
        email="alice@acme.com",
        role="Engineer",
    )
    members = [
        ProviderMember(id="gh-alicechen", label="Alice Chen", email=None),
    ]
    assert guess_provider_member_id(employee, members) == "gh-alicechen"


def test_auto_map_github_member_without_public_email(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-alice",
        name="Alice Chen",
        email="alice@acme.com",
    )
    members = [
        ProviderMember(id="gh-alicechen", label="Alice Chen", email=None, username="alicechen"),
    ]
    created = auto_map_provider_member_identities(db, tenant.id, "github", members)
    assert created == 1


def test_auto_map_does_not_create_duplicate_employees(db, tenant):
    from app.models.operational import Employee

    add_employee(
        db,
        tenant.id,
        employee_id="emp-alice",
        name="Alice Chen",
        email="alice@acme.com",
    )
    before = (
        db.query(Employee)
        .filter(Employee.tenant_id == tenant.id)
        .count()
    )
    members = [
        ProviderMember(
            id="acc-1",
            label="Alice Chen",
            email="alice@acme.com",
            username="alice@acme.com",
        ),
        ProviderMember(
            id="gh-alicechen",
            label="Alice Chen",
            email=None,
            username="alicechen",
        ),
    ]
    auto_map_provider_member_identities(db, tenant.id, "jira", members)
    auto_map_provider_member_identities(db, tenant.id, "github", members)
    after = (
        db.query(Employee)
        .filter(Employee.tenant_id == tenant.id)
        .count()
    )
    assert before == after == 1
