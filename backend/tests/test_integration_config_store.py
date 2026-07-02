"""Tests for tenant-scoped integration config persistence."""

from __future__ import annotations

from app.schemas.integrations import JiraConfigRequest
from app.services.integration_config_store import (
    delete_source_config,
    get_all_configs,
    get_jira_config,
    save_jira_config,
    upsert_source_config,
)


def test_jira_config_persists_per_tenant(db, tenant):
    save_jira_config(
        db,
        tenant.id,
        JiraConfigRequest(
            site_url="https://acme.atlassian.net",
            project_keys="ENG",
            api_token="secret-token",
            account_email="ops@acme.com",
        ),
    )

    loaded = get_jira_config(db, tenant.id)
    assert loaded is not None
    assert loaded.site_url == "https://acme.atlassian.net"
    assert loaded.api_token == "secret-token"
    assert loaded.account_email == "ops@acme.com"


def test_secret_merge_keeps_existing_token_on_partial_update(db, tenant):
    save_jira_config(
        db,
        tenant.id,
        JiraConfigRequest(
            site_url="https://acme.atlassian.net",
            project_keys="ENG",
            api_token="secret-token",
        ),
    )

    upsert_source_config(
        db,
        tenant.id,
        "jira",
        {
            "site_url": "https://acme.atlassian.net",
            "project_keys": "ENG,OPS",
            "api_token": "",
        },
    )

    loaded = get_jira_config(db, tenant.id)
    assert loaded is not None
    assert loaded.project_keys == "ENG,OPS"
    assert loaded.api_token == "secret-token"


def test_delete_source_config_clears_integration(db, tenant):
    save_jira_config(
        db,
        tenant.id,
        JiraConfigRequest(
            site_url="https://acme.atlassian.net",
            api_token="secret-token",
        ),
    )
    delete_source_config(db, tenant.id, "jira")
    assert get_jira_config(db, tenant.id) is None
    assert get_all_configs(db, tenant.id)["jira"]["api_token"] == ""
