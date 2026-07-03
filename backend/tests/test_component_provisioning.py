"""Tests for auto-provisioning org-chart components from integrations."""

from __future__ import annotations

import uuid

import pytest

from app.models.operational import Component
from app.schemas.integrations import GitHubConfigRequest, JiraConfigRequest
from app.services.component_provisioning import (
    discover_repo_partitions,
    parse_mapped_source_paths,
    provision_github_components_for_repo,
    provision_jira_components,
)
from app.services.integration_config_store import (
    get_github_config,
    get_jira_config,
    save_github_config,
    save_jira_config,
)


def test_discover_repo_partitions_splits_monorepo_top_level_dirs():
    paths = [
        "backend/app/main.py",
        "backend/app/services/auth.py",
        "backend/app/services/payments.py",
        "backend/app/api/routes.py",
        "backend/app/db/models.py",
        "frontend/src/App.tsx",
        "frontend/src/lib/api.ts",
        "frontend/src/components/Nav.tsx",
        "frontend/src/pages/Home.tsx",
        "frontend/src/hooks/useAuth.ts",
        "README.md",
    ]
    partitions = discover_repo_partitions(paths)
    assert len(partitions) == 2
    slugs = {partition.slug for partition in partitions}
    assert slugs == {"backend", "frontend"}
    prefixes = {partition.path_prefix for partition in partitions}
    assert prefixes == {"backend/", "frontend/"}


def test_parse_mapped_source_paths_from_feature_readme():
    markdown = """# Era

## Mapped source paths

- `backend/app/services/era/`
- `backend/app/services/era_analytics.py`
- `frontend/src/components/era/`

## Other section
- ignored
"""
    paths = parse_mapped_source_paths(markdown)
    assert paths == [
        "backend/app/services/era/",
        "backend/app/services/era_analytics.py",
        "frontend/src/components/era/",
    ]


def test_discover_repo_partitions_from_feature_docs():
    paths = [
        "docs/features/auth/login.md",
        "docs/features/auth/session.md",
        "docs/features/payments/checkout.md",
        "docs/features/payments/refunds.md",
        "README.md",
    ]
    partitions = discover_repo_partitions(paths)
    assert len(partitions) == 2
    assert {partition.slug for partition in partitions} == {"auth", "payments"}
    assert {partition.display_name for partition in partitions} == {"Auth", "Payments"}


def test_humanize_repo_name_prefers_architectural_suffix():
    from app.services.component_provisioning import _humanize_repo_name

    assert _humanize_repo_name("Empulse-Backend") == "Backend"
    assert _humanize_repo_name("empulse") == "Empulse"
    assert _humanize_repo_name("my-cool-app") == "My Cool App"


def test_discover_repo_partitions_single_repo_when_not_monorepo():
    paths = ["src/main.py", "src/util.py", "README.md"]
    assert discover_repo_partitions(paths) == []


def test_provision_github_components_for_repo_monorepo(db, tenant):
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

    result = provision_github_components_for_repo(
        db,
        tenant.id,
        config,
        "https://github.com/acme/empulse",
        use_fixture=True,
    )

    assert result.created == 2
    components = (
        db.query(Component).filter(Component.tenant_id == tenant.id).all()
    )
    assert len(components) == 2
    names = {component.name for component in components}
    assert names == {"empulse / backend", "empulse / frontend"}

    refreshed = get_github_config(db, tenant.id)
    assert refreshed is not None
    assert refreshed.path_component_map.get("backend/") is not None
    assert refreshed.path_component_map.get("frontend/") is not None


def test_provision_jira_components_from_fixture(db, tenant):
    save_jira_config(
        db,
        tenant.id,
        JiraConfigRequest(
            site_url="https://acme.atlassian.net",
            project_keys="ENG,OPS",
            api_token="fixture",
            component_field_map={},
            project_component_map={},
        ),
    )
    config = get_jira_config(db, tenant.id)
    assert config is not None

    result = provision_jira_components(db, tenant.id, config, use_fixture=True)

    assert result.created >= 4
    components = (
        db.query(Component).filter(Component.tenant_id == tenant.id).all()
    )
    assert len(components) >= 4
    assert any(component.name == "Authentication" for component in components)
    assert any(component.name == "Payments" for component in components)

    refreshed = get_jira_config(db, tenant.id)
    assert refreshed is not None
    assert refreshed.component_field_map.get("Authentication")
    assert refreshed.project_component_map.get("ENG")
    assert refreshed.project_component_map.get("OPS")


def test_provision_does_not_overwrite_manual_component(db, tenant):
    manual_id = "comp-manual-auth"
    db.add(
        Component(
            id=manual_id,
            tenant_id=tenant.id,
            name="Auth (manual)",
            description="Owned by platform team",
        )
    )
    db.commit()

    save_jira_config(
        db,
        tenant.id,
        JiraConfigRequest(
            site_url="https://acme.atlassian.net",
            project_keys="ENG",
            api_token="fixture",
            component_field_map={"Authentication": manual_id},
            project_component_map={},
        ),
    )
    config = get_jira_config(db, tenant.id)
    assert config is not None

    provision_jira_components(db, tenant.id, config, use_fixture=True)

    row = db.get(Component, manual_id)
    assert row is not None
    assert row.name == "Auth (manual)"
    assert row.description == "Owned by platform team"
