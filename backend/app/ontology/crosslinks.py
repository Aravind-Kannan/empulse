"""Phase-2 ontology cross-links between integration node batches."""

from __future__ import annotations

from typing import Any

from cognee.infrastructure.engine.models.Edge import Edge

from app.ontology.datapoints import ChangeEvent, CodeArtifact, Discussion, Document, WorkItem
from app.ontology.relations import REL_AUTHORED, REL_REFERENCES, REL_RESOLVES, REL_TOUCHES
from app.ontology.spec import validate_relation


def _edge(relationship_type: str, **properties: object) -> Edge:
    validate_relation(relationship_type)
    if properties:
        return Edge(relationship_type=relationship_type, properties=properties)
    return Edge(relationship_type=relationship_type)


def _linked_work_item_ids(point: Any) -> list[str]:
    metadata = getattr(point, "metadata", None) or {}
    raw = metadata.get("linked_work_item_ids") or []
    if isinstance(raw, str):
        return [item.strip() for item in raw.split(",") if item.strip()]
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def _work_item_index(data_points: list[Any]) -> dict[str, WorkItem]:
    return {
        point.work_item_id: point
        for point in data_points
        if isinstance(point, WorkItem) and point.work_item_id
    }


def work_item_link_target(work_item_id: str, index: dict[str, WorkItem]) -> WorkItem:
    """Reuse batch node or emit a deterministic stub for cross-sync edges."""
    existing = index.get(work_item_id)
    if existing is not None:
        return existing
    project_key = work_item_id.rsplit("-", 1)[0] if "-" in work_item_id else ""
    return WorkItem(
        source="jira",
        work_item_id=work_item_id,
        issue_type="linked",
        priority="",
        status="",
        project_key=project_key,
        summary=work_item_id,
    )


def _set_multi_edge(node: Any, attr: str, relationship_type: str, targets: list[Any]) -> int:
    if not targets:
        return 0
    if len(targets) == 1:
        setattr(node, attr, (_edge(relationship_type), targets[0]))
    else:
        setattr(
            node,
            attr,
            [(_edge(relationship_type), target) for target in targets],
        )
    return len(targets)


def _authored_targets(node: Any) -> list[Any]:
    existing = getattr(node, "authored", None)
    if existing is None:
        return []
    if isinstance(existing, list):
        return [target for _, target in existing]
    return [existing[1]]


def _employee_id(node: Any) -> str | None:
    return getattr(node, "external_id", None)


def _append_authored(artifact: CodeArtifact, author: Any) -> bool:
    targets = _authored_targets(artifact)
    author_id = _employee_id(author)
    if author_id and any(_employee_id(target) == author_id for target in targets):
        return False
    targets.append(author)
    _set_multi_edge(artifact, "authored", REL_AUTHORED, targets)
    return True


def _merge_primary_authors(existing: str, incoming: str) -> str:
    merged: list[str] = []
    seen: set[str] = set()
    for chunk in (existing, incoming):
        for name in chunk.split(","):
            cleaned = name.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                merged.append(cleaned)
    return ", ".join(merged)


def _merge_code_artifact(canonical: CodeArtifact, other: CodeArtifact) -> None:
    canonical.primary_authors = _merge_primary_authors(
        canonical.primary_authors or "",
        other.primary_authors or "",
    )
    if other.blame_summary and (
        not canonical.blame_summary
        or len(other.blame_summary) > len(canonical.blame_summary)
    ):
        canonical.blame_summary = other.blame_summary
    if other.blob_sha:
        canonical.blob_sha = other.blob_sha
    if other.ref:
        canonical.ref = other.ref
    if other.content_preview and len(other.content_preview) > len(
        canonical.content_preview or ""
    ):
        canonical.content_preview = other.content_preview
    if other.patch_preview and len(other.patch_preview) > len(
        canonical.patch_preview or ""
    ):
        canonical.patch_preview = other.patch_preview
    for author in _authored_targets(other):
        _append_authored(canonical, author)


def consolidate_code_artifacts(data_points: list[Any]) -> int:
    """Merge in-batch CodeArtifact nodes that share repository_url + file_path."""
    canonical_by_path: dict[tuple[str, str], CodeArtifact] = {}
    duplicate_count = 0

    for point in data_points:
        if not isinstance(point, CodeArtifact):
            continue
        key = (point.repository_url, point.file_path)
        existing = canonical_by_path.get(key)
        if existing is None:
            canonical_by_path[key] = point
            continue
        duplicate_count += 1
        _merge_code_artifact(existing, point)

    if duplicate_count == 0:
        return 0

    deduped: list[Any] = []
    seen_paths: set[tuple[str, str]] = set()
    for point in data_points:
        if isinstance(point, CodeArtifact):
            key = (point.repository_url, point.file_path)
            if key in seen_paths:
                continue
            seen_paths.add(key)
            deduped.append(canonical_by_path[key])
            continue
        if isinstance(point, ChangeEvent) and getattr(point, "touches", None):
            edge, target = point.touches
            if isinstance(target, CodeArtifact):
                key = (target.repository_url, target.file_path)
                point.touches = (edge, canonical_by_path.get(key, target))
        deduped.append(point)

    data_points[:] = deduped
    return duplicate_count


def _change_event_author(event: ChangeEvent) -> Any | None:
    authored = getattr(event, "authored", None)
    if authored is None:
        return None
    if isinstance(authored, list):
        return authored[0][1] if authored else None
    return authored[1]


def wire_github_touches(data_points: list[Any]) -> int:
    """Link ChangeEvent -> CodeArtifact when repo + file_path match."""
    artifacts: dict[tuple[str, str], CodeArtifact] = {}
    for point in data_points:
        if isinstance(point, CodeArtifact):
            artifacts[(point.repository_url, point.file_path)] = point

    edge_count = 0
    for point in data_points:
        if not isinstance(point, ChangeEvent):
            continue
        if getattr(point, "touches", None) is not None:
            continue
        key = (point.repository_url, point.file_path)
        artifact = artifacts.get(key)
        if artifact is None:
            artifact = CodeArtifact(
                source="github",
                repository_url=point.repository_url,
                file_path=point.file_path,
                ref=point.commit_sha,
            )
            artifacts[key] = artifact
        point.touches = (
            _edge(REL_TOUCHES, file_path=point.file_path, commit_sha=point.commit_sha),
            artifact,
        )
        edge_count += 1
        author = _change_event_author(point)
        if author and _append_authored(artifact, author):
            edge_count += 1
    return edge_count


def wire_discussion_resolves(data_points: list[Any]) -> int:
    """Link Discussion -> WorkItem when thread text mentions a Jira key."""
    work_items = _work_item_index(data_points)
    edge_count = 0
    for point in data_points:
        if not isinstance(point, Discussion):
            continue
        if getattr(point, "resolves", None) is not None:
            continue
        linked_ids = _linked_work_item_ids(point)
        if not linked_ids:
            continue
        targets = [work_item_link_target(item_id, work_items) for item_id in linked_ids]
        edge_count += _set_multi_edge(point, "resolves", REL_RESOLVES, targets)
    return edge_count


def wire_document_references(data_points: list[Any]) -> int:
    """Link Document -> WorkItem when page title mentions a Jira key."""
    work_items = _work_item_index(data_points)
    edge_count = 0
    for point in data_points:
        if not isinstance(point, Document):
            continue
        if getattr(point, "references", None) is not None:
            continue
        linked_ids = _linked_work_item_ids(point)
        if not linked_ids:
            continue
        targets = [work_item_link_target(item_id, work_items) for item_id in linked_ids]
        edge_count += _set_multi_edge(point, "references", REL_REFERENCES, targets)
    return edge_count


def apply_ontology_cross_links(data_points: list[Any]) -> int:
    """Apply all in-batch ontology cross-links. Returns new edge count."""
    if not data_points:
        return 0
    consolidate_code_artifacts(data_points)
    return (
        wire_github_touches(data_points)
        + wire_discussion_resolves(data_points)
        + wire_document_references(data_points)
    )
