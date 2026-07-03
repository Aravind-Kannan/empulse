"""Map canonical ontology records to Cognee DataPoints."""

from __future__ import annotations

from cognee.infrastructure.engine.models.Edge import Edge

from app.ontology.canonical import (
    CanonicalChangeEvent,
    CanonicalCodeArtifact,
    CanonicalDiscussion,
    CanonicalDocument,
    CanonicalWorkItem,
)
from app.ontology.datapoints import (
    ChangeEvent,
    CodeArtifact,
    Discussion,
    Document,
    WorkItem,
)
from app.ontology.relations import (
    REL_ASSIGNED,
    REL_AUTHORED,
    REL_BLOCKS,
    REL_DISCUSSES,
    REL_DOCUMENTS,
    REL_MODIFIED,
)
from app.ontology.spec import validate_relation
from app.services.cognee_ingest import GraphComponent, GraphEmployee


def _edge(relationship_type: str, **properties: object) -> Edge:
    validate_relation(relationship_type)
    if properties:
        return Edge(relationship_type=relationship_type, properties=properties)
    return Edge(relationship_type=relationship_type)


def map_code_artifact(
    record: CanonicalCodeArtifact,
    *,
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
) -> tuple[CodeArtifact, int]:
    node = CodeArtifact(
        source=record.source,
        repository_url=record.repository_url,
        file_path=record.file_path,
        ref=record.ref,
        content_preview=record.content_preview,
        patch_preview=record.patch_preview,
        blame_summary=record.blame_summary,
        primary_authors=", ".join(record.primary_authors),
        blob_sha=record.blob_sha,
    )
    edge_count = 0

    if record.component:
        component = component_nodes.get(record.component.component_id)
        if component:
            node.documents = (_edge(REL_DOCUMENTS), component)
            edge_count += 1

    if record.blame_author and record.blame_author.employee_id:
        author = employee_nodes.get(record.blame_author.employee_id)
        if author:
            node.authored = (
                _edge(REL_AUTHORED, attribution="blame"),
                author,
            )
            edge_count += 1

    return node, edge_count


def map_change_event(
    record: CanonicalChangeEvent,
    *,
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
) -> tuple[ChangeEvent, int]:
    node = ChangeEvent(
        source=record.source,
        event_kind=record.event_kind,
        repository_url=record.repository_url,
        pr_number=record.pr_number,
        commit_sha=record.commit_sha,
        branch=record.branch,
        file_path=record.file_path,
        loc_added=record.loc_added,
        loc_removed=record.loc_removed,
        pr_url=record.pr_url,
    )
    edge_count = 0

    if record.author and record.author.employee_id:
        author = employee_nodes.get(record.author.employee_id)
        if author:
            node.authored = (
                _edge(REL_AUTHORED, **dict(record.properties)),
                author,
            )
            edge_count += 1

    if record.component:
        component = component_nodes.get(record.component.component_id)
        if component:
            node.modified = (
                _edge(REL_MODIFIED, **dict(record.properties)),
                component,
            )
            edge_count += 1

    return node, edge_count


def map_work_item(
    record: CanonicalWorkItem,
    *,
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
) -> tuple[WorkItem, int]:
    node = WorkItem(
        source=record.source,
        work_item_id=record.work_item_id,
        issue_type=record.issue_type,
        priority=record.priority,
        status=record.status,
        project_key=record.project_key,
        summary=record.summary,
        description_preview=record.description,
        resolution=record.resolution,
        labels=", ".join(record.labels),
        comment_preview=" | ".join(record.comment_excerpts[:5]),
        reporter_name=(
            record.reporter.display_name if record.reporter else ""
        ),
    )
    edge_count = 0

    if record.assignee and record.assignee.employee_id:
        assignee = employee_nodes.get(record.assignee.employee_id)
        if assignee:
            node.assignedTo = (_edge(REL_ASSIGNED), assignee)
            edge_count += 1

    if record.component:
        component = component_nodes.get(record.component.component_id)
        if component:
            node.blocks = (
                _edge(REL_BLOCKS, **dict(record.properties)),
                component,
            )
            edge_count += 1

    _attach_linked_work_items(node, record.linked_work_item_ids)

    return node, edge_count


def _attach_linked_work_items(node, referenced_work_item_ids: tuple[str, ...]) -> None:
    if not referenced_work_item_ids:
        return
    metadata = dict(getattr(node, "metadata", None) or {})
    metadata["linked_work_item_ids"] = list(referenced_work_item_ids)
    node.metadata = metadata


def map_document(
    record: CanonicalDocument,
    *,
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
) -> tuple[Document, int]:
    node = Document(
        source=record.source,
        page_id=record.page_id,
        title=record.title,
        last_edited=record.last_edited,
        page_url=record.page_url,
        doc_kind=record.doc_kind,
    )
    edge_count = 0

    if record.component:
        component = component_nodes.get(record.component.component_id)
        if component:
            node.documents = (_edge(REL_DOCUMENTS), component)
            edge_count += 1

    if record.author and record.author.employee_id:
        author = employee_nodes.get(record.author.employee_id)
        if author:
            node.authored = (_edge(REL_AUTHORED), author)
            edge_count += 1

    _attach_linked_work_items(node, record.referenced_work_item_ids)

    return node, edge_count


def map_discussion(
    record: CanonicalDiscussion,
    *,
    employee_nodes: dict[str, GraphEmployee],
    component_nodes: dict[str, GraphComponent],
) -> tuple[Discussion, int]:
    node = Discussion(
        source=record.source,
        thread_id=record.thread_id,
        channel_name=record.channel_name,
        title=record.title,
        thread_url=record.thread_url,
    )
    edge_count = 0

    if record.resolver and record.resolver.employee_id:
        resolver = employee_nodes.get(record.resolver.employee_id)
        if resolver:
            node.authored = (
                _edge(REL_AUTHORED, attribution="resolved"),
                resolver,
            )
            edge_count += 1

    if record.component:
        component = component_nodes.get(record.component.component_id)
        if component:
            node.discusses = (_edge(REL_DISCUSSES), component)
            edge_count += 1

    _attach_linked_work_items(node, record.referenced_work_item_ids)

    return node, edge_count
