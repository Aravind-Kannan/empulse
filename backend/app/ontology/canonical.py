"""Source-agnostic canonical records before Cognee mapping."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CanonicalPersonRef:
    employee_id: str | None = None
    provider: str = ""
    provider_user_id: str = ""
    display_name: str = ""


@dataclass(frozen=True)
class CanonicalComponentRef:
    component_id: str
    name: str = ""


@dataclass(frozen=True)
class CanonicalCodeArtifact:
    source: str
    repository_url: str
    file_path: str
    ref: str
    blob_sha: str = ""
    content_preview: str = ""
    patch_preview: str = ""
    blame_summary: str = ""
    primary_authors: tuple[str, ...] = ()
    component: CanonicalComponentRef | None = None
    blame_authors: tuple[CanonicalPersonRef, ...] = ()


@dataclass(frozen=True)
class CanonicalChangeEvent:
    source: str
    event_kind: str
    repository_url: str
    pr_number: int
    commit_sha: str
    branch: str
    file_path: str
    loc_added: int
    loc_removed: int
    pr_url: str = ""
    author: CanonicalPersonRef | None = None
    component: CanonicalComponentRef | None = None
    properties: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalWorkItem:
    source: str
    work_item_id: str
    issue_type: str
    priority: str
    status: str
    project_key: str
    summary: str = ""
    assignee: CanonicalPersonRef | None = None
    reporter: CanonicalPersonRef | None = None
    component: CanonicalComponentRef | None = None
    description: str = ""
    resolution: str = ""
    labels: tuple[str, ...] = ()
    linked_work_item_ids: tuple[str, ...] = ()
    comment_excerpts: tuple[str, ...] = ()
    properties: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalDocument:
    source: str
    page_id: str
    title: str
    last_edited: str
    page_url: str = ""
    doc_kind: str = "runbook"
    author: CanonicalPersonRef | None = None
    component: CanonicalComponentRef | None = None
    referenced_work_item_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CanonicalDiscussion:
    source: str
    thread_id: str
    channel_name: str
    title: str
    thread_url: str = ""
    resolver: CanonicalPersonRef | None = None
    component: CanonicalComponentRef | None = None
    referenced_work_item_ids: tuple[str, ...] = ()
