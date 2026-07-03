"""Tenant graph purge helpers for shared Neo4j + structured ingest cleanup."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_DNS, uuid5

from cognee.infrastructure.engine import DataPoint
from cognee.modules.pipelines.models.DataItemStatus import DataItemStatus

from app.config import get_settings
from app.ontology.datapoints import ONTOLOGY_EDGE_ATTRS
from app.tenancy import tenant_dataset_name

logger = logging.getLogger(__name__)

_STRUCTURED_DATA_NAME = "__empulse_structured_graph__"
_COGNIFY_PIPELINE_NAME = "cognify_pipeline"
_STRUCTURED_INGEST_STUB = (
    "Empulse structured ontology ingest ledger.\n"
    "Structured DataPoints are indexed separately; this file is not narrative content.\n"
)


def _structured_ingest_file_path(dataset_id: uuid.UUID) -> Path:
    directory = Path(get_settings().cognee_data_root) / "empulse_structured_ingest"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{dataset_id}.txt"


def _ensure_structured_ingest_stub_file(dataset_id: uuid.UUID) -> str:
    """Write a real on-disk stub and return a file:// URI Cognee can open."""
    path = _structured_ingest_file_path(dataset_id)
    if not path.exists() or path.read_text(encoding="utf-8") != _STRUCTURED_INGEST_STUB:
        path.write_text(_STRUCTURED_INGEST_STUB, encoding="utf-8")
    return path.as_uri()


def _structured_ingest_pipeline_status(dataset_id: uuid.UUID) -> dict:
    """Mark cognify complete so enrichment skips the ledger row."""
    return {
        _COGNIFY_PIPELINE_NAME: {
            str(dataset_id): DataItemStatus.DATA_ITEM_PROCESSING_COMPLETED,
        }
    }


def _sync_structured_ingest_data_row(row: Any, dataset_id: uuid.UUID) -> bool:
    """Migrate memory:// paths and ensure cognify skips this ledger item."""
    file_uri = _ensure_structured_ingest_stub_file(dataset_id)
    changed = False

    if row.raw_data_location != file_uri:
        row.raw_data_location = file_uri
        changed = True
    if row.original_data_location != file_uri:
        row.original_data_location = file_uri
        changed = True
    if row.extension != "txt":
        row.extension = "txt"
        row.mime_type = "text/plain"
        row.loader_engine = "text"
        changed = True

    pipeline_status = dict(row.pipeline_status or {})
    cognify_status = dict(pipeline_status.get(_COGNIFY_PIPELINE_NAME, {}))
    completed = DataItemStatus.DATA_ITEM_PROCESSING_COMPLETED
    if cognify_status.get(str(dataset_id)) != completed:
        cognify_status[str(dataset_id)] = completed
        pipeline_status[_COGNIFY_PIPELINE_NAME] = cognify_status
        row.pipeline_status = pipeline_status
        changed = True

    metadata = dict(row.external_metadata or {})
    if not metadata.get("empulse_structured_ledger"):
        metadata["empulse_structured_ledger"] = True
        row.external_metadata = metadata
        changed = True

    return changed

# DataPoint field names that hold (Edge, target) tuples for graph extraction.
GRAPH_EDGE_FIELD_ATTRS = (
    *ONTOLOGY_EDGE_ATTRS,
    "contributedTo",
    "modifies",
    "blocksComponent",
    "documentedBy",
    "authoredBy",
    "resolvedBy",
    "discussesComponent",
    "documentsComponent",
    "blameAttributedTo",
    "touches",
    "resolves",
    "references",
    "owns",
    "reportsTo",
    "directReportOf",
    "manages",
    "ownsComponent",
)


def _belongs_to_tags(existing: Any, dataset_name: str) -> list[str]:
    tags: list[str] = []
    if isinstance(existing, list):
        for item in existing:
            if isinstance(item, str):
                tags.append(item)
            elif hasattr(item, "name"):
                tags.append(str(item.name))
    if dataset_name not in tags:
        tags.append(dataset_name)
    return tags


def _merge_dataset_tag(point: DataPoint, dataset_name: str) -> None:
    point.belongs_to_set = _belongs_to_tags(getattr(point, "belongs_to_set", None), dataset_name)


def _tag_datapoint_tree(target: Any, dataset_name: str) -> None:
    if isinstance(target, list):
        for item in target:
            _tag_datapoint_tree(item, dataset_name)
        return
    if not isinstance(target, DataPoint):
        return
    _merge_dataset_tag(target, dataset_name)
    for attr in GRAPH_EDGE_FIELD_ATTRS:
        _tag_edge_field_targets(getattr(target, attr, None), dataset_name)


def _tag_edge_field_targets(field: Any, dataset_name: str) -> None:
    if field is None:
        return
    if isinstance(field, tuple) and len(field) == 2:
        _tag_datapoint_tree(field[1], dataset_name)
        return
    if isinstance(field, list):
        for item in field:
            if isinstance(item, tuple) and len(item) == 2:
                _tag_datapoint_tree(item[1], dataset_name)
            else:
                _tag_datapoint_tree(item, dataset_name)
        return
    _tag_datapoint_tree(field, dataset_name)


def _walk_edge_field_targets(field: Any, visit: Any) -> None:
    if field is None:
        return
    if isinstance(field, tuple) and len(field) == 2:
        visit(field[1])
        return
    if isinstance(field, list):
        for item in field:
            if isinstance(item, tuple) and len(item) == 2:
                visit(item[1])
            else:
                visit(item)
        return
    visit(field)


def _collect_referenced_org_external_ids(data_points: list[Any]) -> tuple[set[str], set[str]]:
    employees: set[str] = set()
    components: set[str] = set()

    def visit(target: Any) -> None:
        if isinstance(target, list):
            for item in target:
                visit(item)
            return
        if not isinstance(target, DataPoint):
            return
        external_id = getattr(target, "external_id", None)
        if not external_id:
            return
        type_name = type(target).__name__
        if type_name == "GraphEmployee":
            employees.add(str(external_id))
        elif type_name == "GraphComponent":
            components.add(str(external_id))

    for point in data_points:
        for attr in GRAPH_EDGE_FIELD_ATTRS:
            _walk_edge_field_targets(getattr(point, attr, None), visit)

    return employees, components


def expand_ingest_with_org_anchors(
    data_points: list[Any],
    employee_nodes: dict[str, Any],
    component_nodes: dict[str, Any],
) -> list[Any]:
    """
    Co-ingest Person/Component anchor nodes referenced by integration edges.

    Integration sync only emits source nodes (CodeArtifact, ChangeEvent, …).
    Without anchors in the batch, Neo4j may show nodes but few visible edges.
    """
    if not data_points:
        return data_points

    referenced_employees, referenced_components = _collect_referenced_org_external_ids(
        data_points
    )
    if not referenced_employees and not referenced_components:
        return data_points

    present_external_ids = {
        str(ext)
        for point in data_points
        if (ext := getattr(point, "external_id", None))
    }

    expanded = list(data_points)
    for employee_id in referenced_employees:
        if employee_id in present_external_ids:
            continue
        anchor = employee_nodes.get(employee_id)
        if anchor is None:
            continue
        expanded.append(anchor)
        present_external_ids.add(employee_id)

    for component_id in referenced_components:
        if component_id in present_external_ids:
            continue
        anchor = component_nodes.get(component_id)
        if anchor is None:
            continue
        expanded.append(anchor)
        present_external_ids.add(component_id)

    return expanded


def tag_datapoints_with_dataset(data_points: list[Any], dataset_name: str) -> list[Any]:
    """Stamp belongs_to_set on nodes and nested edge targets for shared Neo4j scope."""
    tagged: list[Any] = []
    for point in data_points:
        copy = point.model_copy(deep=True)
        _tag_datapoint_tree(copy, dataset_name)
        tagged.append(copy)
    return tagged


async def ensure_structured_ingest_data_item(dataset: Any, user: Any) -> Any:
    """
    Stable Cognee Data row so add_data_points registers nodes in the dataset ledger.

    Without a data_item, structured ingest writes Neo4j nodes that cognee.forget
    cannot find (no relational Node rows with dataset_id).
    """
    from sqlalchemy import select

    from cognee.infrastructure.databases.relational import get_async_session
    from cognee.modules.data.models import Data
    from cognee.modules.data.models.DatasetData import DatasetData

    data_id = uuid5(NAMESPACE_DNS, f"empulse-structured-ingest-{dataset.id}")
    file_uri = _ensure_structured_ingest_stub_file(dataset.id)
    async with get_async_session() as session:
        existing = await session.get(Data, data_id)
        if existing is not None:
            if _sync_structured_ingest_data_row(existing, dataset.id):
                await session.commit()
                await session.refresh(existing)
            return existing

        owner_id = getattr(user, "id", None)
        row = Data(
            id=data_id,
            name=_STRUCTURED_DATA_NAME,
            extension="txt",
            mime_type="text/plain",
            loader_engine="text",
            raw_data_location=file_uri,
            original_data_location=file_uri,
            owner_id=owner_id,
            tenant_id=getattr(user, "tenant_id", None),
            content_hash=_STRUCTURED_DATA_NAME,
            raw_content_hash=_STRUCTURED_DATA_NAME,
            external_metadata={"empulse_structured_ledger": True},
            pipeline_status=_structured_ingest_pipeline_status(dataset.id),
            token_count=0,
        )
        session.add(row)
        session.add(DatasetData(dataset_id=dataset.id, data_id=data_id))
        await session.commit()
        await session.refresh(row)
        return row


async def purge_tenant_graph_residuals(
    tenant_id: uuid.UUID,
    *,
    dataset_name: str | None = None,
) -> dict[str, int]:
    """
    Hard-delete Neo4j nodes cognee.forget can miss on shared DB:

    - Nodes tagged with belongs_to_set (cognify + fixed structured ingest)
    - Tenant org-chart nodes (external_id prefix)
    - Legacy structured integration nodes linked to tenant org anchors
    """
    dataset = dataset_name or tenant_dataset_name(tenant_id)
    tenant_prefix = tenant_id.hex[:8]
    emp_prefix = f"emp-{tenant_prefix}-"
    comp_prefix = f"comp-{tenant_prefix}-"

    from cognee.infrastructure.databases.graph.get_graph_engine import get_graph_engine

    graph_engine = await get_graph_engine()

    tagged_result = await graph_engine.query(
        """
        MATCH (n:`__Node__`)
        WHERE $datasetName IN coalesce(n.belongs_to_set, [])
        WITH collect(n) AS nodes
        FOREACH (node IN nodes | DETACH DELETE node)
        RETURN size(nodes) AS deleted
        """,
        {"datasetName": dataset},
    )
    tagged_deleted = int((tagged_result or [{}])[0].get("deleted", 0))

    org_result = await graph_engine.query(
        """
        MATCH (n:`__Node__`)
        WHERE n.external_id STARTS WITH $empPrefix
           OR n.external_id STARTS WITH $compPrefix
        WITH collect(n) AS nodes
        FOREACH (node IN nodes | DETACH DELETE node)
        RETURN size(nodes) AS deleted
        """,
        {"empPrefix": emp_prefix, "compPrefix": comp_prefix},
    )
    org_deleted = int((org_result or [{}])[0].get("deleted", 0))

    neighbor_result = await graph_engine.query(
        """
        MATCH (anchor:`__Node__`)
        WHERE anchor.external_id STARTS WITH $empPrefix
           OR anchor.external_id STARTS WITH $compPrefix
        MATCH (anchor)-[]-(neighbor:`__Node__`)
        WHERE NOT neighbor.external_id STARTS WITH $empPrefix
          AND NOT neighbor.external_id STARTS WITH $compPrefix
          AND NOT $datasetName IN coalesce(neighbor.belongs_to_set, [])
        WITH collect(DISTINCT neighbor) AS nodes
        FOREACH (node IN nodes | DETACH DELETE node)
        RETURN size(nodes) AS deleted
        """,
        {
            "datasetName": dataset,
            "empPrefix": emp_prefix,
            "compPrefix": comp_prefix,
        },
    )
    neighbor_deleted = int((neighbor_result or [{}])[0].get("deleted", 0))

    total = tagged_deleted + org_deleted + neighbor_deleted
    logger.info(
        "Purged residual graph nodes for tenant %s dataset %s "
        "(tagged=%s org=%s neighbors=%s total=%s)",
        tenant_id,
        dataset,
        tagged_deleted,
        org_deleted,
        neighbor_deleted,
        total,
    )
    return {
        "tagged_deleted": tagged_deleted,
        "org_deleted": org_deleted,
        "neighbor_deleted": neighbor_deleted,
        "total_deleted": total,
    }
