"""Reset a tenant's Cognee dataset (graph + vectors) via cognee.forget."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.integration_sync_record import IntegrationSyncRecord
from app.services.integration_disconnect import purge_integration_postgres_data
from app.services.integration_telemetry import clear_integration_telemetry
from app.services.tenant_cognee import _tenant_cognee_lock, tenant_cognee_context
from app.tenancy import tenant_dataset_name

logger = logging.getLogger(__name__)

_INTEGRATION_SOURCES = ("github", "jira", "notion", "slack")


def clear_tenant_sync_ledger(db: Session, tenant_id: uuid.UUID) -> int:
    deleted = (
        db.query(IntegrationSyncRecord)
        .filter(IntegrationSyncRecord.tenant_id == tenant_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def clear_tenant_integration_telemetry(db: Session, tenant_id: uuid.UUID) -> None:
    """Drop Postgres integration snapshots and in-memory telemetry caches."""
    for source in _INTEGRATION_SOURCES:
        purge_integration_postgres_data(db, tenant_id, source)
        clear_integration_telemetry(source)


async def reset_tenant_cognee_dataset(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    memory_only: bool = False,
    clear_ledger: bool = True,
    clear_telemetry: bool = False,
) -> dict[str, Any]:
    """
    Wipe the tenant Cognee dataset using cognee.forget.

    - memory_only=False: remove dataset data, graph nodes, and vector embeddings.
    - memory_only=True: remove graph + vectors only; raw dataset files remain for re-cognify.
    - clear_ledger: delete integration_sync_records so the next sync re-ingests everything.
    - clear_telemetry: also clear DOA/ownership snapshots and in-memory telemetry caches.
    """
    dataset = tenant_dataset_name(tenant_id)
    forget_summary: dict[str, Any] = {}

    async with _tenant_cognee_lock(tenant_id):
        async with tenant_cognee_context(tenant_id):
            import cognee

            try:
                forget_summary = await cognee.forget(
                    dataset=dataset,
                    memory_only=memory_only,
                )
            except Exception as exc:
                logger.exception(
                    "Cognee forget failed for tenant %s dataset %s",
                    tenant_id,
                    dataset,
                )
                raise RuntimeError(
                    f"Cognee dataset reset failed for '{dataset}': {exc}"
                ) from exc

    from app.services.tenant_graph_purge import purge_tenant_graph_residuals

    graph_purge = await purge_tenant_graph_residuals(
        tenant_id,
        dataset_name=dataset,
    )

    ledger_rows_removed = 0
    if clear_ledger:
        ledger_rows_removed = clear_tenant_sync_ledger(db, tenant_id)

    if clear_telemetry:
        clear_tenant_integration_telemetry(db, tenant_id)

    mode = "memory_only" if memory_only else "full_dataset"
    return {
        "dataset": dataset,
        "mode": mode,
        "memory_only": memory_only,
        "forget_summary": forget_summary if isinstance(forget_summary, dict) else {},
        "graph_purge": graph_purge,
        "ledger_rows_removed": ledger_rows_removed,
        "telemetry_cleared": clear_telemetry,
        "message": (
            f"Cognee dataset '{dataset}' reset ({mode}). "
            f"Ledger rows removed: {ledger_rows_removed}."
        ),
    }
