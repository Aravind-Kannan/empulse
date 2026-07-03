"""Tests for component dedupe, CRUD helpers, and scoped provisioning IDs."""

from __future__ import annotations

from app.models.operational import Assignment, Component
from app.schemas.integrations import GitHubConfigRequest
from app.services.component_management import consolidate_duplicate_components
from app.services.component_provisioning import provision_github_components_for_repo
from app.services.employee_ids import scope_component_id
from app.services.integration_config_store import get_github_config, save_github_config


def test_consolidate_duplicate_components_merges_unscoped_rows(db, tenant):
    scoped_id = scope_component_id("comp-gh-acme-service", tenant.id)
    db.add(
        Component(
            id=scoped_id,
            tenant_id=tenant.id,
            name="acme/service",
            description="AUTO:github:acme/service",
        )
    )
    db.add(
        Component(
            id="comp-gh-acme-service",
            tenant_id=tenant.id,
            name="acme/service",
            description="AUTO:github:acme/service",
        )
    )
    db.commit()

    removed = consolidate_duplicate_components(db, tenant.id)

    assert removed == 1
    remaining = (
        db.query(Component).filter(Component.tenant_id == tenant.id).all()
    )
    assert len(remaining) == 1
    assert remaining[0].id == scoped_id


def test_provision_github_uses_scoped_component_ids(db, tenant):
    save_github_config(
        db,
        tenant.id,
        GitHubConfigRequest(
            repository_url="https://github.com/acme/empulse",
            repository_urls=["https://github.com/acme/empulse"],
            branch_target="main",
            personal_access_token="fixture",
            path_component_map={},
        ),
    )
    config = get_github_config(db, tenant.id)
    assert config is not None

    provision_github_components_for_repo(
        db,
        tenant.id,
        config,
        "https://github.com/acme/empulse",
        use_fixture=True,
    )

    components = db.query(Component).filter(Component.tenant_id == tenant.id).all()
    assert components
    prefix = f"comp-{tenant.id.hex[:8]}-"
    assert all(component.id.startswith(prefix) for component in components)


def test_sync_assignments_from_github_ownership(db, tenant):
    from app.models.operational import Employee, GitHubOwnershipSnapshot
    from app.services.component_management import sync_assignments_from_github_ownership
    from app.services.employee_ids import scope_employee_id

    employee_id = scope_employee_id("emp-a", tenant.id)
    component_id = scope_component_id("comp-gh-backend", tenant.id)
    db.add(
        Employee(
            id=employee_id,
            tenant_id=tenant.id,
            name="Alex",
            role="Engineer",
            email="alex@example.com",
            tenure_years=1.0,
        )
    )
    db.add(
        Component(
            id=component_id,
            tenant_id=tenant.id,
            name="Backend",
            description="AUTO:github:backend",
        )
    )
    db.add(
        GitHubOwnershipSnapshot(
            tenant_id=tenant.id,
            component_id=component_id,
            employee_id=employee_id,
            ownership_pct=72.5,
        )
    )
    db.commit()

    created = sync_assignments_from_github_ownership(db, tenant.id)

    assert created == 1
    assignment = (
        db.query(Assignment)
        .filter(
            Assignment.tenant_id == tenant.id,
            Assignment.component_id == component_id,
        )
        .one()
    )
    assert assignment.employee_id == employee_id
