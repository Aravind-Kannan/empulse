"""Cognee Cloud connection via cognee.serve() and structured-ingest helpers."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Literal
from unittest.mock import patch

logger = logging.getLogger(__name__)

_TENANT_DATASET_BOOTSTRAP = (
    "Empulse tenant knowledge graph initialized. "
    "Structured ontology sync will populate Person, Component, CodeArtifact, "
    "ChangeEvent, WorkItem, Document, and Discussion nodes with relations "
    "(owns, reportsTo, authored, documents, blocks, touches, resolves, etc.)."
)

_CLOUD_INGEST_HEADER = (
    "Structured ontology records for knowledge graph ingestion. "
    "Each JSON block is a typed entity (employee, component, PR, issue, thread, etc.). "
    "Preserve entity types, external IDs, and relationship fields when building the graph."
)


def use_cognee_cloud_backend() -> bool:
    """True when COGNEE_BACKEND=cloud (enrichment + remote ingest enabled)."""
    from app.config import get_settings

    return get_settings().cognee_backend == "cloud"


def is_cognee_cloud_mode() -> bool:
    """True when COGNEE_BACKEND=cloud and cognee.serve() connected."""
    if not use_cognee_cloud_backend():
        return False

    from cognee.api.v1.serve.state import get_remote_client

    return get_remote_client() is not None


async def _noop_index_data_points(data_points: list[Any], vector_engine=None) -> list[Any]:
    """Skip LanceDB embedding during cloud staging; COGX push carries graph only."""
    return data_points


async def _noop_index_graph_edges(edges: list[Any], vector_engine=None) -> None:
    return None


@asynccontextmanager
async def skip_local_vector_indexing_for_cloud() -> AsyncIterator[None]:
    """
    When COGNEE_BACKEND=cloud, structured ingest only needs the Kuzu graph for push.

    Cognee Cloud builds its own vectors on remember/recall; local LanceDB embeds are
    wasted work and require embedding API keys on Railway.
    """
    if not use_cognee_cloud_backend():
        yield
        return

    with (
        patch(
            "cognee.tasks.storage.add_data_points.index_data_points",
            new=_noop_index_data_points,
        ),
        patch(
            "cognee.tasks.storage.add_data_points.index_graph_edges",
            new=_noop_index_graph_edges,
        ),
    ):
        logger.debug("Cloud staging: skipping local vector indexing (graph-only)")
        yield


def _edge_summary(value: Any) -> dict[str, Any] | str | None:
    if value is None:
        return None
    if isinstance(value, tuple) and len(value) == 2:
        edge, target = value
        rel = getattr(edge, "relationship_type", None) or getattr(edge, "relationship_name", None)
        summary: dict[str, Any] = {
            "relationship": rel,
            "target_type": type(target).__name__,
        }
        external_id = getattr(target, "external_id", None)
        name = getattr(target, "name", None)
        if external_id:
            summary["target_external_id"] = external_id
        if name:
            summary["target_name"] = name
        if rel or external_id or name:
            return summary
        return str(rel) if rel else None
    if isinstance(value, list):
        items = [_edge_summary(item) for item in value[:30]]
        filtered = [item for item in items if item is not None]
        return filtered or None
    rel = getattr(value, "relationship_type", None)
    if rel:
        return str(rel)
    return None


def _datapoint_record(dp: Any) -> dict[str, Any]:
    record: dict[str, Any] = {"type": type(dp).__name__}
    model_fields = getattr(type(dp), "model_fields", None) or {}
    for key in model_fields:
        if key == "metadata":
            continue
        value = getattr(dp, key, None)
        if value is None:
            continue
        edge_text = _edge_summary(value)
        if edge_text is not None:
            record[key] = edge_text
            continue
        if isinstance(value, (str, int, float, bool)):
            record[key] = value
        elif isinstance(value, list):
            record[key] = [
                item.model_dump(mode="json")
                if hasattr(item, "model_dump")
                else str(item)
                for item in value[:30]
            ]
        elif hasattr(value, "model_dump"):
            record[key] = value.model_dump(mode="json", exclude_none=True)
        else:
            record[key] = str(value)[:500]
    return record


def serialize_datapoints_for_cloud(data_points: list[Any]) -> str:
    """Fallback text serialization when COGX push is unavailable."""
    blocks = [json.dumps(_datapoint_record(dp), indent=2) for dp in data_points]
    return _CLOUD_INGEST_HEADER + "\n\n" + "\n\n---\n\n".join(blocks)


async def ensure_cloud_tenant_dataset(dataset_name: str) -> None:
    """
    Provision a tenant-scoped dataset on Cognee Cloud.

    Cloud datasets are created on first write; this bootstrap call runs when a
    new tenant is registered so the remote namespace exists before full sync.
    """
    if not is_cognee_cloud_mode():
        logger.debug(
            "Skipping cloud dataset provision for %s — remote client not connected",
            dataset_name,
        )
        return

    import cognee

    await cognee.remember(_TENANT_DATASET_BOOTSTRAP, dataset_name=dataset_name)
    logger.info("Provisioned Cognee Cloud dataset %s", dataset_name)


async def push_tenant_ontology_graph(
    dataset_name: str,
    *,
    run_in_background: bool = False,
) -> dict[str, Any] | None:
    """
    Push locally indexed ontology graph to Cognee Cloud with relations preserved.

    Uses cognee.push(..., mode="preserve") so DataPoint edges (owns, authored,
    documents, blocks, etc.) land on cloud without LLM re-derivation.
    """
    if not is_cognee_cloud_mode():
        logger.warning(
            "Cannot push ontology graph for %s — Cognee Cloud not connected",
            dataset_name,
        )
        return None

    import cognee

    try:
        result = await cognee.push(
            dataset_name,
            target_dataset=dataset_name,
            mode="preserve",
            run_in_background=run_in_background,
        )
    except ValueError as exc:
        if "exported 0 nodes" in str(exc):
            logger.info(
                "Skipping cloud push for %s — no local ontology nodes to export yet",
                dataset_name,
            )
            return None
        raise

    logger.info(
        "Pushed ontology graph for %s to Cognee Cloud (%d nodes, %d edges)",
        dataset_name,
        result.num_nodes,
        result.num_edges,
    )
    return {
        "status": result.status,
        "num_nodes": result.num_nodes,
        "num_edges": result.num_edges,
        "pipeline_run_id": result.pipeline_run_id,
    }


async def configure_cognee_backend() -> Literal["local", "cloud"]:
    """
    Apply COGNEE_BACKEND=local|cloud.

    local — disconnect any remote client; Neo4j + Ollama handle ingest/search.
    cloud — cognee.serve() to COGNEE_SERVICE_URL; SDK ops proxy to tenant.
    """
    from app.config import get_settings

    import cognee

    settings = get_settings()
    if settings.cognee_backend == "local":
        await cognee.disconnect()
        logger.info("Cognee backend: local (Neo4j + configured LLM/embeddings)")
        return "local"

    service_url = settings.cognee_service_url.strip()
    if not service_url:
        raise RuntimeError(
            "COGNEE_BACKEND=cloud requires COGNEE_SERVICE_URL "
            "(and COGNEE_API_KEY for hosted tenants)"
        )

    await cognee.serve(url=service_url, api_key=settings.cognee_api_key)
    logger.info("Cognee backend: cloud at %s", service_url)
    return "cloud"


# Backward-compatible alias for callers expecting the old name.
async def connect_cognee_cloud() -> bool:
    return (await configure_cognee_backend()) == "cloud"
