"""KRA Metric 2 — documentation coverage tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.operational import Assignment, Component, NotionDocSnapshot
from app.services.integration_telemetry import reset_telemetry_for_tests
from app.services.kra_metrics import (
    compute_documentation_coverage,
    invalidate_kra_summary_cache,
)
from app.services.github_types import GitHubFileChange, GitHubPullRequestActivity

from tests.conftest import add_employee


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_telemetry():
    reset_telemetry_for_tests()
    invalidate_kra_summary_cache()
    yield
    reset_telemetry_for_tests()
    invalidate_kra_summary_cache()


def _seed_component(
    db,
    tenant_id: uuid.UUID,
    *,
    component_id: str,
    name: str,
) -> None:
    db.add(
        Component(
            id=component_id,
            tenant_id=tenant_id,
            name=name,
            description="",
            criticality="tier2_core",
        )
    )
    db.commit()


def _seed_notion_doc(
    db,
    tenant_id: uuid.UUID,
    *,
    component_id: str,
    title: str,
    last_edited_at: datetime,
    page_id: str,
) -> None:
    db.add(
        NotionDocSnapshot(
            tenant_id=tenant_id,
            page_id=page_id,
            title=title,
            page_url=f"https://notion.so/{page_id}",
            component_id=component_id,
            page_kind="runbook",
            last_edited_at=last_edited_at,
            is_stale=last_edited_at < datetime.now(UTC) - timedelta(days=180),
            is_archived=False,
            computed_at=datetime.now(UTC),
        )
    )
    db.commit()


def _github_activity(
    component_id: str,
    *,
    merged_at: str | None = None,
) -> GitHubPullRequestActivity:
    return GitHubPullRequestActivity(
        pr_number=1,
        commit_sha="abc",
        merge_commit_sha="abc",
        branch="main",
        author_provider_user_id="gh-1",
        author_login="dev",
        author_type="User",
        pr_url="https://github.com/org/repo/pull/1",
        merged_at=merged_at,
        files=[GitHubFileChange(path="src/main.py", loc_added=10, loc_removed=0, component_id=component_id)],
    )


@contextmanager
def notion_ready():
    with (
        patch("app.services.kra_metrics.get_notion_config", return_value=object()),
        patch("app.services.kra_metrics.has_notion_sync", return_value=True),
    ):
        yield


def test_three_active_two_covered_returns_sixty_seven_percent(db, tenant):
    now = datetime.now(UTC)
    for index, component_id in enumerate(("comp-a", "comp-b", "comp-c"), start=1):
        _seed_component(db, tenant.id, component_id=component_id, name=f"System {index}")

    with notion_ready(), patch(
        "app.services.kra_metrics.has_github_sync",
        return_value=True,
    ), patch(
        "app.services.kra_metrics.get_github_ownership",
        return_value={
            "comp-a": {"emp-1": 100.0},
            "comp-b": {"emp-1": 100.0},
            "comp-c": {"emp-1": 100.0},
        },
    ), patch(
        "app.services.kra_metrics.get_notion_component_sources",
        side_effect=lambda component_id: (
            ["Notion: Runbook"]
            if component_id in {"comp-a", "comp-b"}
            else []
        ),
    ), patch(
        "app.services.kra_metrics.get_github_activities",
        return_value=[],
    ):
        for component_id, page_id in (("comp-a", "page-a"), ("comp-b", "page-b")):
            _seed_notion_doc(
                db,
                tenant.id,
                component_id=component_id,
                title="Runbook",
                last_edited_at=now - timedelta(days=30),
                page_id=page_id,
            )
        result = compute_documentation_coverage(db, tenant.id)

    assert result.coverage_pct == 67
    assert result.active_component_count == 3
    assert result.covered_count == 2
    assert len(result.covered_components) == 2
    assert {row.component_id for row in result.covered_components} == {
        "comp-a",
        "comp-b",
    }
    assert result.covered_components[0].notion_page_urls
    assert len(result.gap_components) == 1
    assert result.gap_components[0].component_id == "comp-c"
    assert result.gap_components[0].gap_reason == "missing"


def test_stale_doc_marked_as_stale_gap(db, tenant):
    _seed_component(db, tenant.id, component_id="comp-auth", name="Auth Service")
    stale_edit = datetime.now(UTC) - timedelta(days=240)
    _seed_notion_doc(
        db,
        tenant.id,
        component_id="comp-auth",
        title="Auth Runbook",
        last_edited_at=stale_edit,
        page_id="page-auth",
    )

    with notion_ready(), patch(
        "app.services.kra_metrics.has_github_sync",
        return_value=True,
    ), patch(
        "app.services.kra_metrics.get_github_ownership",
        return_value={"comp-auth": {"emp-1": 100.0}},
    ), patch(
        "app.services.kra_metrics.get_notion_component_sources",
        return_value=["Notion: Auth Runbook"],
    ), patch(
        "app.services.kra_metrics.get_github_activities",
        return_value=[],
    ):
        result = compute_documentation_coverage(db, tenant.id)

    assert result.coverage_pct == 0
    assert result.gap_components[0].gap_reason == "stale"


def test_no_notion_returns_none_coverage(db, tenant):
    _seed_component(db, tenant.id, component_id="comp-a", name="System A")

    with patch("app.services.kra_metrics.get_notion_config", return_value=None), patch(
        "app.services.kra_metrics.has_notion_sync",
        return_value=False,
    ), patch(
        "app.services.kra_metrics.has_github_sync",
        return_value=True,
    ):
        result = compute_documentation_coverage(db, tenant.id)

    assert result.coverage_pct is None
    assert result.data_completeness.notion == "missing"


def test_notion_configured_not_synced_returns_partial(db, tenant):
    _seed_component(db, tenant.id, component_id="comp-a", name="System A")

    with patch("app.services.kra_metrics.get_notion_config", return_value=object()), patch(
        "app.services.kra_metrics.has_notion_sync",
        return_value=False,
    ), patch(
        "app.services.kra_metrics.has_github_sync",
        return_value=False,
    ):
        result = compute_documentation_coverage(db, tenant.id)

    assert result.coverage_pct is None
    assert result.data_completeness.notion == "partial"


def test_notion_synced_with_zero_pages_counts_as_confirmed(db, tenant):
    from app.services.integration_config_store import save_notion_config, upsert_source_config
    from app.schemas.integrations import NotionConfigRequest

    save_notion_config(
        db,
        tenant.id,
        NotionConfigRequest(integration_token="secret", database_ids=""),
    )
    upsert_source_config(
        db,
        tenant.id,
        "notion",
        {"last_synced_at": datetime.now(UTC).isoformat()},
        merge_secrets=True,
    )
    db.commit()

    with patch("app.services.kra_metrics.has_github_sync", return_value=False):
        result = compute_documentation_coverage(db, tenant.id)

    assert result.data_completeness.notion == "confirmed"


def test_no_active_components_returns_none_coverage(db, tenant):
    _seed_component(db, tenant.id, component_id="comp-idle", name="Idle System")

    with notion_ready(), patch(
        "app.services.kra_metrics.has_github_sync",
        return_value=True,
    ), patch(
        "app.services.kra_metrics.get_github_ownership",
        return_value={},
    ), patch(
        "app.services.kra_metrics.get_github_activities",
        return_value=[],
    ):
        result = compute_documentation_coverage(db, tenant.id)

    assert result.coverage_pct is None
    assert result.active_component_count == 0


def test_fresh_notion_source_counts_as_covered(db, tenant):
    _seed_component(db, tenant.id, component_id="comp-pay", name="Payments API")
    _seed_notion_doc(
        db,
        tenant.id,
        component_id="comp-pay",
        title="Payments Runbook",
        last_edited_at=datetime.now(UTC) - timedelta(days=10),
        page_id="page-pay",
    )

    with notion_ready(), patch(
        "app.services.kra_metrics.has_github_sync",
        return_value=True,
    ), patch(
        "app.services.kra_metrics.get_github_ownership",
        return_value={"comp-pay": {"emp-1": 100.0}},
    ), patch(
        "app.services.kra_metrics.get_notion_component_sources",
        return_value=["Notion: Payments Runbook"],
    ), patch(
        "app.services.kra_metrics.get_github_activities",
        return_value=[],
    ):
        result = compute_documentation_coverage(db, tenant.id)

    assert result.coverage_pct == 100
    assert result.covered_count == 1
    assert len(result.covered_components) == 1
    assert result.covered_components[0].notion_page_urls == [
        "https://notion.so/page-pay"
    ]
    assert result.covered_components[0].notion_sources == ["Payments Runbook"]
    assert result.gap_components == []


def test_github_doc_pack_url_used_for_coverage_link(db, tenant):
    _seed_component(db, tenant.id, component_id="comp-notion", name="empulse / notion-docs")
    github_url = (
        "https://github.com/org/empulse/blob/main/notion-docs/design/02-kra.md"
    )
    db.add(
        NotionDocSnapshot(
            tenant_id=tenant.id,
            page_id="abc123",
            title="KRA — Knowledge Risk Assessment",
            page_url=github_url,
            component_id="comp-notion",
            page_kind="architecture",
            last_edited_at=datetime.now(UTC) - timedelta(days=10),
            is_stale=False,
            is_archived=False,
            computed_at=datetime.now(UTC),
        )
    )
    db.commit()

    with notion_ready(), patch(
        "app.services.kra_metrics.has_github_sync",
        return_value=True,
    ), patch(
        "app.services.kra_metrics.get_github_ownership",
        return_value={"comp-notion": {"emp-1": 100.0}},
    ), patch(
        "app.services.kra_metrics.get_notion_component_sources",
        return_value=["Notion: KRA — Knowledge Risk Assessment"],
    ), patch(
        "app.services.kra_metrics.get_github_activities",
        return_value=[],
    ):
        result = compute_documentation_coverage(db, tenant.id)

    covered = result.covered_components[0]
    assert covered.notion_page_urls == [github_url]
    assert covered.notion_sources == ["KRA — Knowledge Risk Assessment"]


def test_recent_pr_makes_component_active(db, tenant):
    _seed_component(db, tenant.id, component_id="comp-api", name="API Gateway")
    merged_at = (datetime.now(UTC) - timedelta(days=14)).isoformat()

    with notion_ready(), patch(
        "app.services.kra_metrics.has_github_sync",
        return_value=True,
    ), patch(
        "app.services.kra_metrics.get_github_ownership",
        return_value={},
    ), patch(
        "app.services.kra_metrics.get_notion_component_sources",
        return_value=[],
    ), patch(
        "app.services.kra_metrics.get_github_activities",
        return_value=[_github_activity("comp-api", merged_at=merged_at)],
    ):
        result = compute_documentation_coverage(db, tenant.id)

    assert result.active_component_count == 1
    assert result.gap_components[0].gap_reason == "missing"


def test_summary_endpoint_includes_documentation_coverage(client):
    response = client.get("/api/analytics/kra/summary")
    assert response.status_code == 200
    payload = response.json()
    assert "documentation_coverage" in payload
    doc = payload["documentation_coverage"]
    assert "coverage_pct" in doc
    assert "covered_components" in doc
    assert "gap_components" in doc
    assert doc["data_completeness"]["notion"] in {"confirmed", "partial", "missing"}
