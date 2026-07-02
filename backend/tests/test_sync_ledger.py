"""Tests for incremental sync ledger."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.models.integration_sync_record import IntegrationSyncRecord
from app.services.sync_ledger import plan_sync_ingest, record_synced_items, LedgerItem


def _github_node(
    *,
    pr: int = 1,
    path: str = "src/a.py",
    loc_added: int = 10,
    loc_removed: int = 2,
):
    return SimpleNamespace(
        repository_url="https://github.com/acme/repo",
        pr_number=pr,
        commit_sha="abc123",
        file_path=path,
        loc_added=loc_added,
        loc_removed=loc_removed,
        branch="main",
    )


def test_plan_skips_unchanged_items(db, tenant):
    node = _github_node()
    record_synced_items(
        db,
        tenant.id,
        "github",
        [
            LedgerItem(
                external_key="https://github.com/acme/repo|1|abc123|src/a.py",
                content_version="10|2|main",
                display_label="PR #1 src/a.py",
                node=node,
            )
        ],
    )
    db.commit()

    plan = plan_sync_ingest(db, tenant.id, "github", [node])
    assert plan.skipped_count == 1
    assert plan.new_count == 0
    assert len(plan.to_ingest) == 0
    assert "already in Cognee" in plan.progress_message()


def test_plan_detects_updated_items(db, tenant):
    node = _github_node(loc_added=99)
    db.add(
        IntegrationSyncRecord(
            tenant_id=tenant.id,
            source="github",
            external_key="https://github.com/acme/repo|1|abc123|src/a.py",
            content_version="10|2|main",
            display_label="PR #1 src/a.py",
        )
    )
    db.commit()

    plan = plan_sync_ingest(db, tenant.id, "github", [node])
    assert plan.updated_count == 1
    assert plan.skipped_count == 0
    assert len(plan.to_ingest) == 1


def test_plan_mixed_github_pr_and_code_nodes(db, tenant):
    pr_node = _github_node()
    content = "print('hi')"
    code_node = SimpleNamespace(
        repository_url="https://github.com/acme/repo",
        file_path="src/a.py",
        ref="abc123",
        content_preview=content,
        patch_preview="@@",
        blame_summary="L1-2: dev (abc1234)",
        blob_sha="blobsha1",
    )
    record_synced_items(
        db,
        tenant.id,
        "github",
        [
            LedgerItem(
                external_key="code|https://github.com/acme/repo|src/a.py|abc123",
                content_version=f"blobsha1|L1-2: dev (abc1234)|{len(content)}",
                display_label="src/a.py @ abc123",
                node=code_node,
            )
        ],
    )
    db.commit()

    plan = plan_sync_ingest(db, tenant.id, "github", [pr_node, code_node])
    assert plan.new_count == 1
    assert plan.skipped_count == 1
    assert len(plan.to_ingest) == 1
    assert plan.to_ingest[0] is pr_node

