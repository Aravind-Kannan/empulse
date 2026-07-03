"""Reset a tenant's Cognee dataset (graph + vectors) via cognee.forget."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.integration_sync_record import IntegrationSyncRecord
from app.services.integration_disconnect import purge_integration_postgres_data
from app.services.integration_telemetry import clear_integration_telemetry
from app.services.tenant_cognee import _tenant_cognee_lock, tenant_cognee_context
from app.tenancy import tenant_dataset_name

logger = logging.getLogger(__name__)

_INTEGRATION_SOURCES = ("github", "jira", "notion", "slack")

# Cognee SQLite tables with UUID-typed columns that must not hold REAL/INTEGER.
_METADATA_UUID_COLUMNS: dict[str, tuple[str, ...]] = {
    "nodes": ("id", "slug", "user_id", "data_id", "dataset_id", "pipeline_run_id"),
    "edges": (
        "id",
        "slug",
        "user_id",
        "data_id",
        "dataset_id",
        "pipeline_run_id",
        "source_node_id",
        "destination_node_id",
    ),
    "pipeline_runs": ("id", "pipeline_run_id", "pipeline_id", "dataset_id"),
    "graph_relationship_ledger": ("id", "source_node_id", "destination_node_id", "user_id"),
    "data": ("id", "owner_id", "tenant_id"),
    "dataset_data": ("dataset_id", "data_id"),
    "datasets": ("id", "owner_id", "tenant_id"),
}


def cognee_metadata_db_path() -> Path:
    return Path(get_settings().cognee_system_root) / "databases" / "cognee_db"


def repair_cognee_metadata_invalid_uuid_rows(db_path: Path | None = None) -> int:
    """
    Remove Cognee metadata rows whose UUID columns were stored as REAL/INTEGER.

    Ollama/cognify glitches can write values like ``Inf`` into node slug/id columns.
    SQLAlchemy then crashes on ``cognee.forget()`` with:
    ``'float' object has no attribute 'replace'``.
    """
    path = db_path or cognee_metadata_db_path()
    if not path.is_file():
        return 0

    removed = 0
    with sqlite3.connect(path) as conn:
        for table, columns in _METADATA_UUID_COLUMNS.items():
            table_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if not table_exists:
                continue
            for column in columns:
                try:
                    cursor = conn.execute(
                        f'DELETE FROM "{table}" WHERE typeof("{column}") IN ("real", "integer")'
                    )
                    removed += cursor.rowcount or 0
                except sqlite3.Error:
                    logger.debug(
                        "Skipped Cognee metadata repair for %s.%s",
                        table,
                        column,
                        exc_info=True,
                    )
        conn.commit()
    if removed:
        logger.warning(
            "Removed %d Cognee metadata row(s) with invalid UUID column values",
            removed,
        )
    return removed


def sql_forget_cognee_dataset(
    dataset_name: str,
    *,
    memory_only: bool = False,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """
    Delete a dataset from Cognee's SQLite metadata without the ORM.

    Used when ``cognee.forget`` cannot load corrupt ledger rows.
    Neo4j/LanceDB cleanup is handled separately via ``purge_tenant_graph_residuals``.
    """
    path = db_path or cognee_metadata_db_path()
    if not path.is_file():
        return {"status": "skipped", "reason": "metadata_db_missing"}

    with sqlite3.connect(path) as conn:
        dataset_row = conn.execute(
            "SELECT id FROM datasets WHERE name = ?",
            (dataset_name,),
        ).fetchone()
        if not dataset_row:
            return {"status": "not_found", "dataset": dataset_name}

        dataset_id = dataset_row[0]
        data_ids = [
            row[0]
            for row in conn.execute(
                "SELECT data_id FROM dataset_data WHERE dataset_id = ?",
                (dataset_id,),
            )
        ]

        conn.execute("DELETE FROM nodes WHERE dataset_id = ?", (dataset_id,))
        conn.execute("DELETE FROM edges WHERE dataset_id = ?", (dataset_id,))
        conn.execute(
            "DELETE FROM pipeline_runs WHERE dataset_id = ?",
            (dataset_id,),
        )

        if memory_only:
            if data_ids:
                placeholders = ",".join("?" for _ in data_ids)
                conn.execute(
                    f"UPDATE data SET pipeline_status = NULL WHERE id IN ({placeholders})",
                    data_ids,
                )
            conn.commit()
            return {
                "status": "success",
                "mode": "memory_only_sql_fallback",
                "dataset_id": dataset_id,
                "data_records_reset": len(data_ids),
            }

        conn.execute("DELETE FROM dataset_data WHERE dataset_id = ?", (dataset_id,))
        for data_id in data_ids:
            remaining = conn.execute(
                "SELECT COUNT(*) FROM dataset_data WHERE data_id = ?",
                (data_id,),
            ).fetchone()[0]
            if remaining == 0:
                conn.execute("DELETE FROM data WHERE id = ?", (data_id,))

        conn.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
        conn.commit()

    return {
        "status": "success",
        "mode": "full_dataset_sql_fallback",
        "dataset_id": dataset_id,
        "data_items_removed": len(data_ids),
    }


async def _run_cognee_forget(dataset: str, *, memory_only: bool) -> dict[str, Any]:
    import cognee

    return await cognee.forget(dataset=dataset, memory_only=memory_only)


async def _forget_with_repair(dataset: str, *, memory_only: bool) -> dict[str, Any]:
    repair_cognee_metadata_invalid_uuid_rows()
    try:
        return await _run_cognee_forget(dataset, memory_only=memory_only)
    except Exception as first_exc:
        logger.warning(
            "cognee.forget failed for %s (%s); repairing metadata and retrying",
            dataset,
            first_exc,
        )
        repaired = repair_cognee_metadata_invalid_uuid_rows()
        try:
            return await _run_cognee_forget(dataset, memory_only=memory_only)
        except Exception as second_exc:
            logger.warning(
                "cognee.forget still failed for %s after repairing %d row(s); "
                "using SQL metadata fallback (%s)",
                dataset,
                repaired,
                second_exc,
            )
            fallback = sql_forget_cognee_dataset(
                dataset,
                memory_only=memory_only,
            )
            fallback["forget_error"] = str(second_exc)
            return fallback


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
            try:
                forget_summary = await _forget_with_repair(
                    dataset,
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
