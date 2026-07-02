"""Tenant-scoped Cognee graph operations with per-dataset Neo4j/LanceDB isolation."""

from __future__ import annotations

import asyncio
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
from cognee.modules.users.methods import get_default_user
from cognee.tasks.storage import add_data_points

from app.config import run_cognee_add_and_cognify
from app.tenancy import tenant_dataset_name


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


async def tenant_add_data_points(tenant_id: uuid.UUID, data_points: list) -> None:
    async with _tenant_cognee_lock(tenant_id):
        async with tenant_cognee_context(tenant_id):
            await add_data_points(data_points)


async def tenant_add_and_cognify(
    content: str,
    tenant_id: uuid.UUID,
    *,
    custom_prompt: str | None = None,
) -> dict:
    dataset = tenant_dataset_name(tenant_id)
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

    dataset = tenant_dataset_name(tenant_id)
    content = json.dumps(record, indent=2)
    prompt = custom_prompt or (
        "Extract incident lifecycle updates, resolution notes, and status "
        "transitions for future investigation retrieval."
    )
    async with _tenant_cognee_lock(tenant_id):
        async with tenant_cognee_context(tenant_id):
            await cognee.add(content, dataset_name=dataset)
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
