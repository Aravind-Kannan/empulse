"""Disconnect cleanup — purge integration graph data from Cognee and Postgres."""

from __future__ import annotations

import logging
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.integration_sync_record import IntegrationSyncRecord
from app.models.operational import (
    DoaFileSnapshot,
    FileRiskSnapshot,
    GitHubOwnershipSnapshot,
    NotionDocSnapshot,
)
from app.ontology.datapoints import (
    ChangeEvent,
    CodeArtifact,
    Discussion,
    Document,
    WorkItem,
)
from app.services.integration_sync import (
    GraphCodeFile,
    GraphJiraTicket,
    GraphNotionPage,
    GraphPullRequest,
    GraphSlackThread,
)
from app.services.integration_telemetry import clear_integration_telemetry
from app.services.tenant_cognee import tenant_cognee_context

logger = logging.getLogger(__name__)

INTEGRATION_GRAPH_TYPES: dict[str, tuple[str, ...]] = {
    "github": (
        "ChangeEvent",
        "CodeArtifact",
        "GraphPullRequest",
        "GraphCodeFile",
    ),
    "jira": ("WorkItem", "GraphJiraTicket"),
    "notion": ("Document", "GraphNotionPage"),
    "slack": ("Discussion", "GraphSlackThread"),
}

_INTEGRATION_VECTOR_COLLECTIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "github": (
        ("ChangeEvent", "pr_number"),
        ("ChangeEvent", "file_path"),
        ("ChangeEvent", "branch"),
        ("CodeArtifact", "file_path"),
        ("CodeArtifact", "repository_url"),
        ("CodeArtifact", "ref"),
        ("CodeArtifact", "primary_authors"),
        ("GraphPullRequest", "pr_number"),
        ("GraphPullRequest", "file_path"),
        ("GraphPullRequest", "branch"),
        ("GraphCodeFile", "file_path"),
        ("GraphCodeFile", "repository_url"),
        ("GraphCodeFile", "ref"),
        ("GraphCodeFile", "primary_authors"),
    ),
    "jira": (
        ("WorkItem", "work_item_id"),
        ("WorkItem", "issue_type"),
        ("WorkItem", "status"),
        ("GraphJiraTicket", "ticket_id"),
        ("GraphJiraTicket", "issue_type"),
        ("GraphJiraTicket", "status"),
    ),
    "notion": (
        ("Document", "page_id"),
        ("Document", "title"),
        ("Document", "doc_kind"),
        ("GraphNotionPage", "page_id"),
        ("GraphNotionPage", "title"),
        ("GraphNotionPage", "page_kind"),
    ),
    "slack": (
        ("Discussion", "thread_id"),
        ("Discussion", "channel_name"),
        ("Discussion", "title"),
        ("GraphSlackThread", "thread_id"),
        ("GraphSlackThread", "channel_name"),
        ("GraphSlackThread", "title"),
    ),
}


def external_key_to_node_id(source: str, external_key: str) -> UUID | None:
    """Map a sync-ledger external key to the deterministic Cognee node id."""
    ids = external_key_to_node_ids(source, external_key)
    return ids[0] if ids else None


def external_key_to_node_ids(source: str, external_key: str) -> list[UUID]:
    """Resolve current + legacy ontology node IDs for one ledger key."""
    normalized = source.lower().strip()
    ids: list[UUID] = []

    if normalized == "github":
        if external_key.startswith("code|"):
            parts = external_key.split("|", 3)
            if len(parts) != 4:
                return []
            _, repository_url, file_path, ref = parts
            ids.extend(
                [
                    CodeArtifact.id_for(repository_url, file_path, ref),
                    GraphCodeFile.id_for(repository_url, file_path, ref),
                ]
            )
        else:
            parts = external_key.split("|", 3)
            if len(parts) != 4:
                return []
            repository_url, pr_number, commit_sha, file_path = parts
            try:
                pr_num = int(pr_number)
            except ValueError:
                return []
            ids.extend(
                [
                    ChangeEvent.id_for(repository_url, pr_num, commit_sha, file_path),
                    GraphPullRequest.id_for(repository_url, pr_num, commit_sha, file_path),
                ]
            )
    elif normalized == "jira":
        ids.extend([WorkItem.id_for(external_key), GraphJiraTicket.id_for(external_key)])
    elif normalized == "notion":
        ids.extend([Document.id_for(external_key), GraphNotionPage.id_for(external_key)])
    elif normalized == "slack":
        ids.extend([Discussion.id_for(external_key), GraphSlackThread.id_for(external_key)])

    deduped: list[UUID] = []
    seen: set[str] = set()
    for node_id in ids:
        key = str(node_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(node_id)
    return deduped


def _legacy_external_key_to_node_id(source: str, external_key: str) -> UUID | None:
    ids = external_key_to_node_ids(source, external_key)
    return ids[1] if len(ids) > 1 else None


def _ledger_node_ids(db: Session, tenant_id: uuid.UUID, source: str) -> list[str]:
    rows = (
        db.query(IntegrationSyncRecord.external_key)
        .filter(
            IntegrationSyncRecord.tenant_id == tenant_id,
            IntegrationSyncRecord.source == source,
        )
        .all()
    )
    node_ids: list[str] = []
    seen: set[str] = set()
    for (external_key,) in rows:
        for node_id in external_key_to_node_ids(source, external_key):
            node_id_str = str(node_id)
            if node_id_str in seen:
                continue
            seen.add(node_id_str)
            node_ids.append(node_id_str)
    return node_ids


async def _delete_vector_embeddings(
    source: str,
    node_ids: list[str],
) -> None:
    if not node_ids:
        return

    from cognee.infrastructure.databases.vector.get_vector_engine import get_vector_engine

    vector_engine = get_vector_engine()
    uuid_ids = [UUID(node_id) for node_id in node_ids]
    for type_name, field_name in _INTEGRATION_VECTOR_COLLECTIONS.get(source, ()):
        collection = f"{type_name}_{field_name}"
        try:
            await vector_engine.delete_data_points(collection, uuid_ids)
        except Exception as exc:
            logger.warning(
                "Vector cleanup skipped for collection %s: %s",
                collection,
                exc,
            )


async def purge_integration_cognee_data(
    tenant_id: uuid.UUID,
    source: str,
    db: Session,
) -> dict[str, Any]:
    """Remove integration-specific structured nodes from the tenant Cognee graph."""
    normalized = source.lower().strip()
    if normalized not in INTEGRATION_GRAPH_TYPES:
        raise ValueError(f"Unsupported integration source '{source}'.")

    node_ids = _ledger_node_ids(db, tenant_id, normalized)
    nodes_removed = 0

    if node_ids:
        async with tenant_cognee_context(tenant_id):
            from cognee.infrastructure.databases.graph.get_graph_engine import get_graph_engine

            graph_engine = await get_graph_engine()
            await graph_engine.delete_nodes(node_ids)
            await _delete_vector_embeddings(normalized, node_ids)
            nodes_removed = len(node_ids)

    deleted_ledger_rows = (
        db.query(IntegrationSyncRecord)
        .filter(
            IntegrationSyncRecord.tenant_id == tenant_id,
            IntegrationSyncRecord.source == normalized,
        )
        .delete(synchronize_session=False)
    )
    db.commit()

    return {
        "source": normalized,
        "graph_nodes_removed": nodes_removed,
        "ledger_rows_removed": deleted_ledger_rows,
    }


def purge_integration_postgres_data(
    db: Session,
    tenant_id: uuid.UUID,
    source: str,
) -> None:
    """Clear Postgres telemetry snapshots written during integration sync."""
    normalized = source.lower().strip()
    if normalized == "github":
        db.query(GitHubOwnershipSnapshot).filter(
            GitHubOwnershipSnapshot.tenant_id == tenant_id,
        ).delete(synchronize_session=False)
        db.query(DoaFileSnapshot).filter(
            DoaFileSnapshot.tenant_id == tenant_id,
        ).delete(synchronize_session=False)
        db.query(FileRiskSnapshot).filter(
            FileRiskSnapshot.tenant_id == tenant_id,
        ).delete(synchronize_session=False)
    elif normalized == "notion":
        db.query(NotionDocSnapshot).filter(
            NotionDocSnapshot.tenant_id == tenant_id,
        ).delete(synchronize_session=False)

    clear_integration_telemetry(normalized)
    db.commit()


async def disconnect_integration(
    db: Session,
    tenant_id: uuid.UUID,
    source: str,
) -> dict[str, Any]:
    """Full disconnect: Cognee purge, telemetry cleanup, then config removal."""
    from app.services.integration_config_store import delete_source_config

    normalized = source.lower().strip()
    cognee_result = await purge_integration_cognee_data(db=db, tenant_id=tenant_id, source=normalized)
    purge_integration_postgres_data(db, tenant_id, normalized)
    delete_source_config(db, tenant_id, normalized)
    return cognee_result
