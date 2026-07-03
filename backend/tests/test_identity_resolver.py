"""Unit tests for identity resolution and quarantine attribution gating."""

from __future__ import annotations

import uuid

from app.models.operational import EmployeeIdentity, UnmappedActivity
from app.schemas.identity import EmployeeIdentityMapping
from app.services.identity_mapping import get_reconciliation, save_identity_mappings
from app.services.identity_resolver import (
    resolve_author_employee_id,
    resolve_employee,
    should_attribute,
)
from app.services.github_client import load_fixture_activities
from app.services.integration_telemetry import apply_github_telemetry
from app.services.unmapped_activity import get_total_unmapped_count

from tests.conftest import add_employee


def test_confirmed_mapping_attributes(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-eng-001",
        name="Ben Rivera",
        email="ben.rivera@acme.com",
    )
    db.add(
        EmployeeIdentity(
            tenant_id=tenant.id,
            employee_id="emp-eng-001",
            provider="github",
            provider_username_or_id="gh-benrivera",
            confidence="confirmed",
        )
    )
    db.commit()

    result = resolve_employee(db, tenant.id, "github", "gh-benrivera")
    assert result.employee_id == "emp-eng-001"
    assert result.confidence == "confirmed"
    assert should_attribute(result)


def test_unmapped_provider_user_is_quarantined_not_attributed(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-eng-001",
        name="Ben Rivera",
        email="ben.rivera@acme.com",
    )

    employee_id = resolve_author_employee_id(
        db,
        tenant.id,
        "github",
        "gh-ext-001",
        demo_fallback_employee_id="emp-eng-001",
        quarantine_event_type="github_pr",
        quarantine_payload={"pr_number": 510},
    )
    db.commit()

    assert employee_id is None
    row = (
        db.query(UnmappedActivity)
        .filter(
            UnmappedActivity.tenant_id == tenant.id,
            UnmappedActivity.provider_user_id == "gh-ext-001",
        )
        .one()
    )
    assert row.event_type == "github_pr"
    assert row.occurrence_count == 1


def test_email_match_is_high_confidence(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-eng-002",
        name="Cara Patel",
        email="cara.patel@acme.com",
    )

    result = resolve_employee(db, tenant.id, "github", "gh-carapatel")
    assert result.employee_id == "emp-eng-002"
    assert result.confidence == "high"
    assert result.identity_warning is False


def test_fuzzy_name_match_is_medium_with_warning(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-eng-001",
        name="Ben Rivera",
        email="other.user@acme.com",
    )

    result = resolve_employee(db, tenant.id, "github", "gh-benrivera")
    assert result.employee_id == "emp-eng-001"
    assert result.confidence == "medium"
    assert result.identity_warning is True


def test_ambiguous_fuzzy_name_does_not_auto_attribute(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-a",
        name="Alice Chen",
        email="alice.a@acme.com",
    )
    add_employee(
        db,
        tenant.id,
        employee_id="emp-b",
        name="Alice C",
        email="alice.b@acme.com",
    )

    result = resolve_employee(db, tenant.id, "notion", "notion-alice")
    assert result.employee_id is None
    assert result.confidence == "none"
    assert result.match_method == "ambiguous_fuzzy_name"


def test_unmapped_count_decreases_after_mapping_saved(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-contractor",
        name="External Worker",
        email="contractor@external.com",
    )

    resolve_author_employee_id(
        db,
        tenant.id,
        "github",
        "gh-ext-001",
        quarantine_event_type="github_pr",
    )
    db.commit()
    assert get_total_unmapped_count(db, tenant.id) == 1

    save_identity_mappings(
        db,
        tenant,
        [
            EmployeeIdentityMapping(
                employee_id="emp-contractor",
                provider="github",
                provider_username_or_id="gh-ext-001",
            )
        ],
    )

    employee_id = resolve_author_employee_id(
        db,
        tenant.id,
        "github",
        "gh-ext-001",
        quarantine_event_type="github_pr",
    )
    db.commit()

    assert employee_id == "emp-contractor"
    reconciliation = get_reconciliation(db, tenant)
    assert reconciliation.total_unmapped_count == 0


def test_github_telemetry_skips_unmapped_contractor(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-eng-001",
        name="Ben Rivera",
        email="ben.rivera@acme.com",
    )
    add_employee(
        db,
        tenant.id,
        employee_id="emp-eng-002",
        name="Cara Patel",
        email="cara.patel@acme.com",
    )
    add_employee(
        db,
        tenant.id,
        employee_id="emp-eng-004",
        name="Elena Kowalski",
        email="elena.kowalski@acme.com",
    )
    for employee_id, provider_user_id in (
        ("emp-eng-001", "gh-benrivera"),
        ("emp-eng-002", "gh-carapatel"),
        ("emp-eng-004", "gh-elena-k"),
    ):
        db.add(
            EmployeeIdentity(
                tenant_id=tenant.id,
                employee_id=employee_id,
                provider="github",
                provider_username_or_id=provider_user_id,
                confidence="confirmed",
            )
        )
    db.commit()

    activities = load_fixture_activities()
    ownership = apply_github_telemetry(db, tenant.id, activities)
    db.commit()

    all_contributors = {
        employee_id
        for contributors in ownership.values()
        for employee_id in contributors
    }
    assert get_total_unmapped_count(db, tenant.id) >= 1
    assert "gh-ext-001" not in all_contributors


def test_demo_mode_uses_fallback_when_no_employees(db, tenant_id: uuid.UUID):
    employee_id = resolve_author_employee_id(
        db,
        tenant_id,
        "github",
        "gh-ext-001",
        demo_fallback_employee_id="emp-eng-001",
    )
    assert employee_id == "emp-eng-001"
    assert get_total_unmapped_count(db, tenant_id) == 0
