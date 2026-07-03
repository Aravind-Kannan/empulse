"""Ontology-aligned Cognee DataPoint types."""

from __future__ import annotations

from typing import Any

from pydantic import SkipValidation

from cognee.infrastructure.engine import DataPoint

from app.ontology.relations import (
    REL_ASSIGNED,
    REL_AUTHORED,
    REL_BLOCKS,
    REL_DISCUSSES,
    REL_DOCUMENTS,
    REL_MODIFIED,
)


class CodeArtifact(DataPoint):
    """Canonical code file node (GitHub repo sync, blame, diffs)."""

    source: str = "github"
    repository_url: str
    file_path: str
    ref: str
    content_preview: str = ""
    patch_preview: str = ""
    blame_summary: str = ""
    primary_authors: str = ""
    blob_sha: str = ""
    documents: SkipValidation[Any] = None
    authored: SkipValidation[Any] = None
    metadata: dict = {
        "ontology_type": "CodeArtifact",
        "index_fields": [
            "file_path",
            "repository_url",
            "ref",
            "primary_authors",
            "source",
        ],
        "identity_fields": ["repository_url", "file_path", "ref"],
    }


class ChangeEvent(DataPoint):
    """Canonical engineering change (PR, commit, branch diff)."""

    source: str = "github"
    event_kind: str = "pull_request"
    pr_number: int
    commit_sha: str
    branch: str
    repository_url: str
    loc_added: int
    loc_removed: int
    file_path: str
    pr_url: str = ""
    authored: SkipValidation[Any] = None
    modified: SkipValidation[Any] = None
    touches: SkipValidation[Any] = None
    metadata: dict = {
        "ontology_type": "ChangeEvent",
        "index_fields": [
            "pr_number",
            "file_path",
            "branch",
            "event_kind",
            "source",
        ],
        "identity_fields": ["repository_url", "pr_number", "commit_sha", "file_path"],
    }


class WorkItem(DataPoint):
    """Canonical work tracker item (Jira issues, tasks, incidents)."""

    source: str = "jira"
    work_item_id: str
    issue_type: str
    priority: str
    status: str
    project_key: str
    summary: str = ""
    description_preview: str = ""
    resolution: str = ""
    labels: str = ""
    comment_preview: str = ""
    reporter_name: str = ""
    assignedTo: SkipValidation[Any] = None
    blocks: SkipValidation[Any] = None
    metadata: dict = {
        "ontology_type": "WorkItem",
        "index_fields": [
            "work_item_id",
            "issue_type",
            "status",
            "summary",
            "description_preview",
            "resolution",
            "labels",
            "comment_preview",
            "reporter_name",
            "source",
        ],
        "identity_fields": ["work_item_id"],
    }


class Document(DataPoint):
    """Canonical documentation page (Notion runbooks, architecture docs)."""

    source: str = "notion"
    page_id: str
    title: str
    last_edited: str
    page_url: str = ""
    doc_kind: str = "runbook"
    documents: SkipValidation[Any] = None
    authored: SkipValidation[Any] = None
    references: SkipValidation[Any] = None
    metadata: dict = {
        "ontology_type": "Document",
        "index_fields": ["page_id", "title", "doc_kind", "source"],
        "identity_fields": ["page_id"],
    }


class Discussion(DataPoint):
    """Canonical incident or on-call thread metadata (Slack)."""

    source: str = "slack"
    thread_id: str
    channel_name: str
    title: str
    thread_url: str = ""
    discusses: SkipValidation[Any] = None
    authored: SkipValidation[Any] = None
    resolves: SkipValidation[Any] = None
    metadata: dict = {
        "ontology_type": "Discussion",
        "index_fields": ["thread_id", "channel_name", "title", "source"],
        "identity_fields": ["thread_id"],
    }


ONTOLOGY_EDGE_ATTRS = (
    "authored",
    "documents",
    "modified",
    "assignedTo",
    "blocks",
    "discusses",
    "touches",
    "resolves",
    "references",
    "owns",
    "reportsTo",
    "directReportOf",
    "manages",
    "ownsComponent",
)
