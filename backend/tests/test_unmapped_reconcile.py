"""Tests for unmapped activity reconciliation and alert suppression."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.operational import EmployeeIdentity, EraAlert, UnmappedActivity
from app.schemas.identity import EmployeeIdentityMapping
from app.schemas.integrations import GitHubConfigRequest
from app.services.era.metadata import build_warnings
from app.services.era_alerts import evaluate_alert_candidates, list_era_alerts
from app.services.identity_mapping import save_identity_mappings
from app.services.integration_config_store import save_github_config
from app.services.unmapped_activity import (
    get_total_unmapped_count,
    is_employee_identity_grid_complete,
    reconcile_and_prune_unmapped_activity,
)

from tests.conftest import add_employee


def _configure_github(db, tenant_id) -> None:
    save_github_config(
        db,
        tenant_id,
        GitHubConfigRequest(
            personal_access_token="test-token",
            repository_urls=["https://github.com/acme/repo"],
        ),
    )


def _seed_complete_github_mapping(db, tenant_id, employee_id: str, github_id: str) -> None:
    db.add(
        EmployeeIdentity(
            tenant_id=tenant_id,
            employee_id=employee_id,
            provider="github",
            provider_username_or_id=github_id,
            confidence="confirmed",
        )
    )


def test_reconcile_clears_resolvable_quarantine(db, tenant):
    _configure_github(db, tenant.id)
    add_employee(
        db,
        tenant.id,
        employee_id="emp-eng-001",
        name="Ben Rivera",
        email="ben.rivera@acme.com",
    )
    _seed_complete_github_mapping(db, tenant.id, "emp-eng-001", "gh-benrivera")
    db.add(
        UnmappedActivity(
            tenant_id=tenant.id,
            provider="github",
            provider_user_id="gh-benrivera",
            event_type="github_pr",
            occurrence_count=40,
            payload_json={},
        )
    )
    db.commit()

    removed = reconcile_and_prune_unmapped_activity(db, tenant.id)
    assert removed == 1
    assert get_total_unmapped_count(db, tenant.id) == 0


def test_stale_quarantine_purged_when_identity_grid_complete(db, tenant):
    _configure_github(db, tenant.id)
    add_employee(
        db,
        tenant.id,
        employee_id="emp-eng-001",
        name="Ben Rivera",
        email="ben.rivera@acme.com",
    )
    _seed_complete_github_mapping(db, tenant.id, "emp-eng-001", "gh-benrivera")
    db.add(
        UnmappedActivity(
            tenant_id=tenant.id,
            provider="github",
            provider_user_id="gh-external-bot",
            event_type="github_blame",
            occurrence_count=155,
            payload_json={},
        )
    )
    db.commit()

    assert is_employee_identity_grid_complete(db, tenant.id) is True
    removed = reconcile_and_prune_unmapped_activity(db, tenant.id)
    assert removed == 1
    assert get_total_unmapped_count(db, tenant.id) == 0


def test_partial_identity_warning_suppressed_after_reconcile(db, tenant):
    _configure_github(db, tenant.id)
    add_employee(
        db,
        tenant.id,
        employee_id="emp-eng-001",
        name="Ben Rivera",
        email="ben.rivera@acme.com",
    )
    _seed_complete_github_mapping(db, tenant.id, "emp-eng-001", "gh-benrivera")
    db.add(
        UnmappedActivity(
            tenant_id=tenant.id,
            provider="github",
            provider_user_id="gh-old-contractor",
            event_type="github_pr",
            occurrence_count=20,
            payload_json={},
        )
    )
    db.commit()

    warnings = build_warnings(db, tenant.id, demo_mode=False)
    assert "partial_identity" not in warnings


def test_identity_gap_alert_dismissed_when_grid_complete(db, tenant):
    _configure_github(db, tenant.id)
    add_employee(
        db,
        tenant.id,
        employee_id="emp-eng-001",
        name="Ben Rivera",
        email="ben.rivera@acme.com",
    )
    _seed_complete_github_mapping(db, tenant.id, "emp-eng-001", "gh-benrivera")
    db.add(
        UnmappedActivity(
            tenant_id=tenant.id,
            provider="github",
            provider_user_id="gh-bot",
            event_type="github_pr",
            occurrence_count=6,
            payload_json={},
        )
    )
    db.add(
        EraAlert(
            tenant_id=tenant.id,
            rule_id="identity_gap",
            severity="medium",
            title="Identity mapping gaps detected",
            description="stale",
            dedupe_key="identity_gap:tenant",
            created_at=datetime.now(UTC),
        )
    )
    db.commit()

    listed = list_era_alerts(db, tenant.id, unacknowledged=True)
    assert listed.unacknowledged_count == 0
    assert get_total_unmapped_count(db, tenant.id) == 0


def test_save_mappings_triggers_reconcile(db, tenant):
    _configure_github(db, tenant.id)
    add_employee(
        db,
        tenant.id,
        employee_id="emp-contractor",
        name="External Worker",
        email="contractor@external.com",
    )
    db.add(
        UnmappedActivity(
            tenant_id=tenant.id,
            provider="github",
            provider_user_id="gh-ext-001",
            event_type="github_pr",
            occurrence_count=10,
            payload_json={},
        )
    )
    db.commit()

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

    assert get_total_unmapped_count(db, tenant.id) == 0


def test_identity_gap_still_fires_when_grid_incomplete(db, tenant):
    _configure_github(db, tenant.id)
    add_employee(
        db,
        tenant.id,
        employee_id="emp-eng-001",
        name="Ben Rivera",
        email="ben.rivera@acme.com",
    )
    for index in range(6):
        db.add(
            UnmappedActivity(
                tenant_id=tenant.id,
                provider="github",
                provider_user_id=f"unknown-{index}",
                event_type="github_pr",
                payload_json={},
            )
        )
    db.commit()

    candidates = evaluate_alert_candidates(db, tenant.id)
    assert any(item.rule_id == "identity_gap" for item in candidates)
