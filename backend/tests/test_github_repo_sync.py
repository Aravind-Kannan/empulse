"""Tests for full GitHub repository sync."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from app.schemas.integrations import GitHubConfigRequest
from app.services.github_repo_sync import (
    collect_branch_snapshots,
    fetch_branch_diff_files,
    fetch_repo_tree_files,
    order_branches_with_default_first,
    process_github_repo_sync,
    resolve_sync_branches,
)
from app.services.integration_config_store import save_github_config
from app.services.integration_sync_jobs import (
    _execute_integration_sync_job,
    cancel_integration_sync_job,
    create_github_repo_sync_job,
)
from app.services.sync_job_errors import SyncJobCancelled


def test_fetch_fixture_repo_tree():
    files = fetch_repo_tree_files(
        "",
        "acme",
        "repo",
        "deadbeef",
        use_fixture=True,
    )
    assert len(files) >= 3
    assert any(item.path.endswith("main.py") for item in files)


def test_collect_fixture_repo_snapshots():
    config = GitHubConfigRequest(
        repository_url="https://github.com/acme/repo",
        personal_access_token="",
        branch_target="main",
        path_component_map={"backend/": "comp-api"},
    )
    tree_files = fetch_repo_tree_files("", "acme", "repo", "deadbeef", use_fixture=True)
    snapshots, _ = collect_branch_snapshots(
        config,
        "https://github.com/acme/repo",
        tree_files,
        {},
        branch="main",
        ref_sha="deadbeef",
        branches_total=1,
        branches_completed=0,
        files_total=len(tree_files),
        files_completed_offset=0,
        use_fixture=True,
    )
    assert len(snapshots) == len(tree_files)
    assert all(snap.content_preview for snap in snapshots)
    assert all(snap.blame_ranges for snap in snapshots)


def test_order_branches_with_default_first():
    assert order_branches_with_default_first(
        ["develop", "main", "feature/x"],
        "main",
    ) == ["main", "develop", "feature/x"]


def test_fetch_fixture_branch_diff_files():
    diff_files = fetch_branch_diff_files(
        "",
        "acme",
        "repo",
        "fixture-main",
        "fixture-develop",
        head_branch="develop",
        use_fixture=True,
    )
    assert len(diff_files) == 1
    assert diff_files[0].path.endswith("integrations.ts")
    assert diff_files[0].patch_preview


def test_process_github_repo_sync_multi_branch_fixture(db, tenant):
    save_github_config(
        db,
        tenant.id,
        GitHubConfigRequest(
            repository_url="https://github.com/acme/repo",
            repository_urls=["https://github.com/acme/repo"],
            branch_targets=["main", "develop"],
            branch_target="main",
            personal_access_token="test-token",
        ),
    )

    branches = resolve_sync_branches(
        GitHubConfigRequest(
            repository_url="https://github.com/acme/repo",
            branch_targets=["main", "develop"],
            personal_access_token="test-token",
        ),
        "https://github.com/acme/repo",
        token="test-token",
        use_fixture=True,
    )
    assert branches == ["main", "develop"]

    with patch(
        "app.services.github_repo_sync.tenant_add_data_points",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.ontology.enrichment.run_post_structured_cognify_enrichment",
        new=AsyncMock(return_value=None),
    ):
        result = asyncio.run(
            process_github_repo_sync(
                db,
                tenant.id,
                "https://github.com/acme/repo",
                use_fixture=True,
            )
        )

    assert result["branches_total"] == 2
    assert result["branches_synced"] == ["main", "develop"]
    # main full tree (4) + develop diff-only (1)
    assert result["files_discovered"] == 5


def test_process_github_repo_sync_fixture(db, tenant):
    save_github_config(
        db,
        tenant.id,
        GitHubConfigRequest(
            repository_url="https://github.com/acme/repo",
            repository_urls=["https://github.com/acme/repo"],
            branch_target="main",
            personal_access_token="test-token",
            path_component_map={"backend/": "comp-api"},
        ),
    )

    with patch(
        "app.services.github_repo_sync.tenant_add_data_points",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.ontology.enrichment.run_post_structured_cognify_enrichment",
        new=AsyncMock(return_value=None),
    ):
        result = asyncio.run(
            process_github_repo_sync(
                db,
                tenant.id,
                "https://github.com/acme/repo",
                use_fixture=True,
            )
        )

    assert result["source"] == "github_repo"
    assert result["files_discovered"] >= 3
    assert result["graph_nodes_created"] >= 1


def test_github_repo_sync_job_executes(db, tenant):
    save_github_config(
        db,
        tenant.id,
        GitHubConfigRequest(
            repository_url="https://github.com/acme/repo",
            repository_urls=["https://github.com/acme/repo"],
            branch_target="main",
            personal_access_token="test-token",
        ),
    )
    job = create_github_repo_sync_job(
        db,
        tenant_id=tenant.id,
        repository_url="https://github.com/acme/repo",
    )

    fake_result = {
        "source": "github_repo",
        "repository_url": "https://github.com/acme/repo",
        "graph_nodes_created": 4,
        "graph_edges_created": 2,
        "items_skipped": 0,
    }

    with patch(
        "app.services.integration_sync_jobs.SessionLocal",
        return_value=db,
    ), patch.object(db, "close"), patch(
        "app.services.integration_sync_jobs.process_github_repo_sync",
        new=AsyncMock(return_value=fake_result),
    ), patch(
        "app.services.era_snapshots.refresh_era_after_integration_sync",
    ):
        asyncio.run(_execute_integration_sync_job(job.id, tenant.id))

    db.refresh(job)
    assert job.status == "completed"
    assert job.job_kind == "github_repo"
    assert job.repository_url == "https://github.com/acme/repo"


def test_cancel_sync_job_marks_cancelled(db, tenant):
    job = create_github_repo_sync_job(
        db,
        tenant_id=tenant.id,
        repository_url="https://github.com/acme/repo",
    )
    cancelled = cancel_integration_sync_job(db, job.id, tenant.id)
    assert cancelled.status == "cancelled"
    assert cancelled.completed_at is not None


def test_cancelled_repo_sync_raises(db, tenant):
    save_github_config(
        db,
        tenant.id,
        GitHubConfigRequest(
            repository_url="https://github.com/acme/repo",
            repository_urls=["https://github.com/acme/repo"],
            branch_target="main",
            personal_access_token="test-token",
        ),
    )
    job = create_github_repo_sync_job(
        db,
        tenant_id=tenant.id,
        repository_url="https://github.com/acme/repo",
    )
    cancel_integration_sync_job(db, job.id, tenant.id)

    with patch(
        "app.services.integration_sync_jobs.SessionLocal",
        return_value=db,
    ), patch.object(db, "close"), patch(
        "app.services.integration_sync_jobs.process_github_repo_sync",
        new=AsyncMock(side_effect=SyncJobCancelled()),
    ), patch(
        "app.services.era_snapshots.refresh_era_after_integration_sync",
    ):
        asyncio.run(_execute_integration_sync_job(job.id, tenant.id))

    db.refresh(job)
    assert job.status == "cancelled"
