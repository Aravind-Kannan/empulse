"""Tests for tenant Cognee dataset reset."""

from __future__ import annotations

import asyncio
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.models.integration_sync_record import IntegrationSyncRecord
from app.services.tenant_cognee_reset import (
    repair_cognee_metadata_invalid_uuid_rows,
    reset_tenant_cognee_dataset,
    sql_forget_cognee_dataset,
)


def _create_minimal_cognee_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE datasets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner_id TEXT,
                tenant_id TEXT
            );
            CREATE TABLE data (
                id TEXT PRIMARY KEY,
                owner_id TEXT,
                tenant_id TEXT,
                pipeline_status TEXT
            );
            CREATE TABLE dataset_data (
                dataset_id TEXT NOT NULL,
                data_id TEXT NOT NULL,
                PRIMARY KEY (dataset_id, data_id)
            );
            CREATE TABLE nodes (
                id TEXT,
                slug REAL,
                user_id TEXT,
                data_id TEXT,
                dataset_id TEXT,
                pipeline_run_id TEXT
            );
            CREATE TABLE edges (
                id TEXT,
                slug TEXT,
                user_id TEXT,
                data_id TEXT,
                dataset_id TEXT,
                pipeline_run_id TEXT,
                source_node_id TEXT,
                destination_node_id TEXT
            );
            CREATE TABLE pipeline_runs (
                id TEXT PRIMARY KEY,
                pipeline_run_id TEXT,
                pipeline_id TEXT,
                dataset_id TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO datasets (id, name) VALUES (?, ?)",
            ("dataset-uuid", "empulse_tenant_test"),
        )
        conn.execute(
            "INSERT INTO data (id, pipeline_status) VALUES (?, ?)",
            ("data-uuid", "{}"),
        )
        conn.execute(
            "INSERT INTO dataset_data (dataset_id, data_id) VALUES (?, ?)",
            ("dataset-uuid", "data-uuid"),
        )
        conn.execute(
            "INSERT INTO nodes (id, slug, dataset_id) VALUES ('node-id', 1e309, 'dataset-uuid')"
        )
        conn.commit()


def test_repair_cognee_metadata_invalid_uuid_rows_removes_float_ids(tmp_path):
    db_path = tmp_path / "cognee_db"
    _create_minimal_cognee_db(db_path)

    removed = repair_cognee_metadata_invalid_uuid_rows(db_path)

    assert removed >= 1
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    assert count == 0


def test_sql_forget_cognee_dataset_full(tmp_path):
    db_path = tmp_path / "cognee_db"
    _create_minimal_cognee_db(db_path)

    result = sql_forget_cognee_dataset("empulse_tenant_test", db_path=db_path)

    assert result["status"] == "success"
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM data").fetchone()[0] == 0


def test_reset_cognee_clears_ledger(db, tenant):
    db.add(
        IntegrationSyncRecord(
            tenant_id=tenant.id,
            source="github",
            external_key="code|https://github.com/acme/r|src/a.py|main",
            content_version="abc",
            display_label="src/a.py",
        )
    )
    db.commit()

    forget_result = {"datasets_removed": 1, "items_removed": 42}

    with patch(
        "app.services.tenant_cognee_reset._forget_with_repair",
        new=AsyncMock(return_value=forget_result),
    ), patch(
        "app.services.tenant_cognee_reset.tenant_cognee_context",
    ) as mock_ctx, patch(
        "app.services.tenant_graph_purge.purge_tenant_graph_residuals",
        new=AsyncMock(
            return_value={
                "tagged_deleted": 3,
                "org_deleted": 2,
                "neighbor_deleted": 1,
                "total_deleted": 6,
            }
        ),
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value="empulse_tenant_test")
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

        result = asyncio.run(
            reset_tenant_cognee_dataset(
                db,
                tenant.id,
                memory_only=False,
                clear_ledger=True,
                clear_telemetry=False,
            )
        )

    assert result["ledger_rows_removed"] == 1
    assert result["mode"] == "full_dataset"
    assert result["forget_summary"] == forget_result
    assert result["graph_purge"]["total_deleted"] == 6
    remaining = (
        db.query(IntegrationSyncRecord)
        .filter(IntegrationSyncRecord.tenant_id == tenant.id)
        .count()
    )
    assert remaining == 0


def test_reset_cognee_memory_only_mode(db, tenant):
    with patch(
        "app.services.tenant_cognee_reset._forget_with_repair",
        new=AsyncMock(return_value={"items_removed": 10}),
    ) as forget_mock, patch(
        "app.services.tenant_cognee_reset.tenant_cognee_context",
    ) as mock_ctx, patch(
        "app.services.tenant_graph_purge.purge_tenant_graph_residuals",
        new=AsyncMock(return_value={"total_deleted": 0}),
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value="empulse_tenant_test")
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

        result = asyncio.run(
            reset_tenant_cognee_dataset(
                db,
                tenant.id,
                memory_only=True,
                clear_ledger=False,
            )
        )

    forget_mock.assert_awaited_once()
    assert forget_mock.await_args.kwargs["memory_only"] is True
    assert result["mode"] == "memory_only"
