"""Tenant-scoped Cognee graph operations."""

from __future__ import annotations

import uuid

import cognee

from app.config import run_cognee_add_and_cognify
from app.tenancy import tenant_dataset_name


async def tenant_add_and_cognify(
    content: str,
    tenant_id: uuid.UUID,
    *,
    custom_prompt: str | None = None,
) -> dict:
    dataset = tenant_dataset_name(tenant_id)
    return await run_cognee_add_and_cognify(
        content,
        dataset_name=dataset,
        custom_prompt=custom_prompt,
    )


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
    try:
        results = await cognee.search(
            query_text,
            datasets=[dataset],
            top_k=top_k,
        )
        return results if isinstance(results, list) else list(results or [])
    except TypeError:
        # Older Cognee builds may use dataset_name instead of datasets
        results = await cognee.search(query_text, dataset_name=dataset, top_k=top_k)
        return results if isinstance(results, list) else list(results or [])
