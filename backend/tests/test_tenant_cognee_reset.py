"""Tests for tenant Cognee dataset reset."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from app.models.integration_sync_record import IntegrationSyncRecord
from app.services.tenant_cognee_reset import reset_tenant_cognee_dataset


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
        "cognee.forget",
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
        "cognee.forget",
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
