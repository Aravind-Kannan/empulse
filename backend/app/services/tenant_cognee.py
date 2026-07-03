"""Tenant-scoped Cognee graph operations with per-dataset Neo4j/LanceDB isolation."""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

_tenant_cognee_locks: dict[uuid.UUID, asyncio.Lock] = {}


def _tenant_cognee_lock(tenant_id: uuid.UUID) -> asyncio.Lock:
    lock = _tenant_cognee_locks.get(tenant_id)
    if lock is None:
        lock = asyncio.Lock()
        _tenant_cognee_locks[tenant_id] = lock
    return lock

import cognee
from cognee.context_global_variables import (
    backend_access_control_enabled,
    current_dataset_id,
    set_database_global_context_variables,
)
from cognee.modules.pipelines.layers.resolve_authorized_user_dataset import (
    resolve_authorized_user_dataset,
)
from cognee.modules.pipelines.models import PipelineContext
from cognee.modules.users.methods import get_default_user
from cognee.tasks.storage import add_data_points

from app.config import run_cognee_add_and_cognify
from app.services.tenant_graph_purge import (
    ensure_structured_ingest_data_item,
    expand_ingest_with_org_anchors,
    tag_datapoints_with_dataset,
)
from app.tenancy import tenant_dataset_name

logger = logging.getLogger(__name__)


async def ensure_tenant_cognee_dataset(tenant_id: uuid.UUID) -> str:
    """Register the tenant dataset in Cognee metadata."""
    dataset = tenant_dataset_name(tenant_id)
    user = await get_default_user()
    await resolve_authorized_user_dataset(dataset, user=user)
    return dataset


@asynccontextmanager
async def tenant_cognee_context(tenant_id: uuid.UUID) -> AsyncIterator[str]:
    """
    Scope Cognee operations to one tenant dataset.

    With ENABLE_BACKEND_ACCESS_CONTROL=true and Neo4j Enterprise, each dataset
    also gets its own Neo4j database. On Neo4j Community, datasets are isolated
    at the Cognee metadata/search layer while sharing the default graph DB.
    """
    dataset = await ensure_tenant_cognee_dataset(tenant_id)
    user = await get_default_user()

    if backend_access_control_enabled():
        async with set_database_global_context_variables(dataset, user.id):
            yield dataset
        return

    token = current_dataset_id.set(dataset)
    try:
        yield dataset
    finally:
        current_dataset_id.reset(token)


@asynccontextmanager
async def tenant_cognee_context_for_dataset(dataset_name: str) -> AsyncIterator[str]:
    """Scope Cognee operations when the dataset name is already known."""
    user = await get_default_user()
    await resolve_authorized_user_dataset(dataset_name, user=user)

    if backend_access_control_enabled():
        async with set_database_global_context_variables(dataset_name, user.id):
            yield dataset_name
        return

    token = current_dataset_id.set(dataset_name)
    try:
        yield dataset_name
    finally:
        current_dataset_id.reset(token)


async def tenant_add_data_points(
    tenant_id: uuid.UUID,
    data_points: list,
    *,
    employee_nodes: dict | None = None,
    component_nodes: dict | None = None,
) -> None:
    """Add structured DataPoints with dataset ledger + belongs_to_set tagging."""
    if not data_points:
        return

    if employee_nodes is not None and component_nodes is not None:
        data_points = expand_ingest_with_org_anchors(
            data_points,
            employee_nodes,
            component_nodes,
        )

    async with _tenant_cognee_lock(tenant_id):
        async with tenant_cognee_context(tenant_id) as dataset_name:
            user, dataset = await resolve_authorized_user_dataset(
                dataset_name,
                user=await get_default_user(),
            )
            tagged_points = tag_datapoints_with_dataset(data_points, dataset_name)
            data_item = await ensure_structured_ingest_data_item(dataset, user)
            ctx = PipelineContext(
                user=user,
                dataset=dataset,
                data_item=data_item,
                pipeline_name="empulse_structured_ingest",
            )
            await add_data_points(tagged_points, ctx=ctx)


async def tenant_add_and_cognify(
    content: str,
    tenant_id: uuid.UUID,
    *,
    custom_prompt: str | None = None,
) -> dict:
    from app.ontology.enrichment import (
        cognify_enrichment_available,
        cognify_enrichment_skip_reason,
    )

    dataset = tenant_dataset_name(tenant_id)
    if not cognify_enrichment_available():
        logger.info(
            "Skipping tenant_add_and_cognify for %s — %s",
            dataset,
            cognify_enrichment_skip_reason(),
        )
        return {
            "dataset": dataset,
            "cognify_result": None,
            "skipped": True,
            "skip_reason": cognify_enrichment_skip_reason(),
        }

    async with _tenant_cognee_lock(tenant_id):
        async with tenant_cognee_context(tenant_id):
            return await run_cognee_add_and_cognify(
                content,
                dataset_name=dataset,
                custom_prompt=custom_prompt,
            )


async def tenant_write_memory_record(
    tenant_id: uuid.UUID,
    record: dict,
    *,
    custom_prompt: str | None = None,
) -> None:
    """Append structured memory to the tenant dataset and re-cognify."""
    import json

    from app.ontology.enrichment import cognify_enrichment_available

    dataset = tenant_dataset_name(tenant_id)
    content = json.dumps(record, indent=2)
    prompt = custom_prompt or (
        "Extract incident lifecycle updates, resolution notes, and status "
        "transitions for future investigation retrieval."
    )
    async with _tenant_cognee_lock(tenant_id):
        async with tenant_cognee_context(tenant_id):
            await cognee.add(content, dataset_name=dataset)
            if cognify_enrichment_available():
                await cognee.cognify(datasets=dataset, custom_prompt=prompt)


async def tenant_graph_search(
    query_text: str,
    tenant_id: uuid.UUID,
    *,
    top_k: int = 8,
) -> list:
    """
    Search only within the tenant's Cognee dataset namespace.
    Prevents cross-tenant vector / graph retrieval.
    """
    dataset = tenant_dataset_name(tenant_id)
    async with tenant_cognee_context(tenant_id):
        try:
            results = await cognee.search(
                query_text,
                datasets=[dataset],
                top_k=top_k,
            )
            return results if isinstance(results, list) else list(results or [])
        except TypeError:
            results = await cognee.search(query_text, dataset_name=dataset, top_k=top_k)
            return results if isinstance(results, list) else list(results or [])
