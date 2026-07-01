"""Resolve per-tenant Cognee storage locations for internal debugging."""

from __future__ import annotations

import os
import uuid
from urllib.parse import urlparse

from cognee.base_config import get_base_config
from cognee.context_global_variables import backend_access_control_enabled
from cognee.infrastructure.databases.utils.get_or_create_dataset_database import (
    _existing_dataset_database,
    get_or_create_dataset_database,
)
from cognee.infrastructure.databases.vector.config import get_vectordb_config
from cognee.modules.data.methods import get_unique_dataset_id
from cognee.modules.users.methods import get_default_user

from app.config import get_settings
from app.schemas.tenant_storage import (
    CogneeMetadataDbDetails,
    Neo4jAccessDetails,
    TenantCogneeStorageAccess,
    VectorStoreDetails,
)
from app.services.tenant_cognee import ensure_tenant_cognee_dataset


def _neo4j_browser_url(bolt_url: str) -> str:
    parsed = urlparse(bolt_url)
    host = parsed.hostname or "localhost"
    # Neo4j Browser defaults to HTTP on 7474; bolt is usually 7687.
    return f"http://{host}:7474/browser/"


def _vector_store_path(*, user_id: uuid.UUID, dataset_id: uuid.UUID) -> str:
    base_config = get_base_config()
    return os.path.join(
        base_config.system_root_directory,
        "databases",
        str(user_id),
        f"{dataset_id}.lance.db",
    )


def _neo4j_database_name_for_dataset(dataset_id: uuid.UUID) -> str:
    return f"cognee{dataset_id.hex}"


async def get_tenant_cognee_storage_access(tenant_id: uuid.UUID) -> TenantCogneeStorageAccess:
    settings = get_settings()
    vector_config = get_vectordb_config()
    base_config = get_base_config()

    dataset_name = await ensure_tenant_cognee_dataset(tenant_id)
    user = await get_default_user()
    dataset_id = await get_unique_dataset_id(dataset_name, user)

    access_control = backend_access_control_enabled()
    dataset_database = await _existing_dataset_database(dataset_id, user)
    if access_control and dataset_database is None:
        dataset_database = await get_or_create_dataset_database(dataset_name, user)

    if access_control and dataset_database is not None:
        neo4j_database = dataset_database.graph_database_name
        vector_path = dataset_database.vector_database_url
        isolation_mode = "dedicated_neo4j_and_lancedb_per_dataset"
        vector_isolated = True
    else:
        neo4j_database = settings.cognee_graph_db_name
        vector_path = vector_config.vector_db_url or os.path.join(
            base_config.system_root_directory,
            "databases",
            "cognee.lancedb",
        )
        isolation_mode = "shared_neo4j_and_lancedb_dataset_scoped_metadata"
        vector_isolated = False

    dedicated_neo4j = access_control and neo4j_database != settings.cognee_graph_db_name
    # When access control is on but the DB is not provisioned yet, compute the expected name.
    if access_control and not dedicated_neo4j:
        neo4j_database = _neo4j_database_name_for_dataset(dataset_id)
        dedicated_neo4j = True
        vector_path = _vector_store_path(user_id=user.id, dataset_id=dataset_id)
        vector_isolated = True
        isolation_mode = "dedicated_neo4j_and_lancedb_per_dataset"

    bolt_url = settings.cognee_graph_db_url
    browser_url = _neo4j_browser_url(bolt_url)

    startup_commands: list[str] = []
    if dedicated_neo4j:
        startup_commands.append(f":use {neo4j_database}")
    sample_cypher = [
        "MATCH (n) RETURN labels(n) AS labels, count(*) AS count",
        "MATCH (n)-[r]->(m) RETURN type(r) AS relationship, count(*) AS count",
        "MATCH (n) RETURN n LIMIT 25",
    ]

    browser_instructions = (
        f"Open {browser_url}, sign in with the bolt URL and credentials below, "
        + (
            f"then run `:use {neo4j_database}` in the Cypher shell to scope queries to this tenant."
            if dedicated_neo4j
            else (
                f"then query the shared `{neo4j_database}` database. "
                "Tenant graph nodes are dataset-scoped in Cognee metadata; "
                "use dataset-filtered search APIs for safe isolation."
            )
        )
    )

    sqlite_path = os.path.join(base_config.system_root_directory, "databases", "cognee_db")

    return TenantCogneeStorageAccess(
        tenant_id=tenant_id,
        cognee_dataset_name=dataset_name,
        cognee_dataset_id=dataset_id,
        isolation_mode=isolation_mode,
        backend_access_control_enabled=access_control,
        neo4j=Neo4jAccessDetails(
            browser_url=browser_url,
            bolt_url=bolt_url,
            username=settings.cognee_graph_db_username,
            password=settings.cognee_graph_db_password,
            database=neo4j_database,
            dedicated_database=dedicated_neo4j,
            browser_instructions=browser_instructions,
            startup_commands=startup_commands,
            sample_cypher=sample_cypher,
        ),
        vector_store=VectorStoreDetails(
            provider=vector_config.vector_db_provider,
            path=vector_path,
            isolated_per_tenant=vector_isolated,
            note=(
                "Per-tenant LanceDB files under .cognee_system/databases/<user_id>/ "
                "when ENABLE_BACKEND_ACCESS_CONTROL=true."
                if vector_isolated
                else (
                    "Shared LanceDB index; retrieval is scoped by cognee dataset name "
                    f"({dataset_name}) in API calls."
                )
            ),
        ),
        cognee_metadata_db=CogneeMetadataDbDetails(
            provider="sqlite",
            path=sqlite_path,
            isolated_per_tenant=False,
            note=(
                "Single Cognee metadata database for all tenants. Dataset rows, permissions, "
                "and dataset_database mappings are keyed by cognee_dataset_id / dataset name."
            ),
        ),
    )
