"""Tests for phase-2 ontology cross-links."""

from __future__ import annotations

from cognee.infrastructure.engine.models.Edge import Edge

from app.ontology.crosslinks import (
    apply_ontology_cross_links,
    wire_discussion_resolves,
    wire_document_references,
    wire_github_touches,
)
from app.ontology.datapoints import ChangeEvent, CodeArtifact, Discussion, Document, WorkItem
from app.ontology.jira_keys import extract_jira_issue_keys as extract_keys
from app.ontology.relations import REL_REFERENCES, REL_RESOLVES, REL_TOUCHES


def test_extract_jira_issue_keys():
    assert extract_keys("Investigating ENG-42 and ENG-42 again") == ("ENG-42",)
    assert extract_keys("no ticket here") == ()
    assert extract_keys("linked to eng-99 in slack", "follow-up ENG-100") == (
        "ENG-99",
        "ENG-100",
    )


def test_wire_github_touches_matches_repo_and_path():
    artifact = CodeArtifact(
        repository_url="https://github.com/acme/api",
        file_path="src/main.py",
        ref="deadbeef",
    )
    event = ChangeEvent(
        repository_url="https://github.com/acme/api",
        pr_number=7,
        commit_sha="abc123",
        branch="main",
        loc_added=2,
        loc_removed=1,
        file_path="src/main.py",
    )
    assert wire_github_touches([artifact, event]) == 1
    assert event.touches[0].relationship_type == REL_TOUCHES
    assert event.touches[1] is artifact


def test_wire_github_touches_creates_stub_artifact_when_missing():
    event = ChangeEvent(
        repository_url="https://github.com/acme/api",
        pr_number=7,
        commit_sha="abc123",
        branch="main",
        loc_added=2,
        loc_removed=1,
        file_path="src/other.py",
    )
    assert wire_github_touches([event]) == 1
    assert isinstance(event.touches[1], CodeArtifact)
    assert event.touches[1].file_path == "src/other.py"


def test_wire_discussion_resolves_links_jira_key():
    discussion = Discussion(
        thread_id="C1:123.456",
        channel_name="incidents",
        title="ENG-55 outage",
        metadata={"linked_work_item_ids": ["ENG-55"]},
    )
    work_item = WorkItem(
        work_item_id="ENG-55",
        issue_type="Bug",
        priority="High",
        status="Open",
        project_key="ENG",
        summary="Outage",
    )
    assert wire_discussion_resolves([discussion, work_item]) == 1
    assert discussion.resolves[0].relationship_type == REL_RESOLVES
    assert discussion.resolves[1] is work_item


def test_wire_document_references_uses_stub_when_work_item_missing():
    document = Document(
        page_id="page-1",
        title="Runbook for ENG-77",
        last_edited="2026-01-01",
        metadata={"linked_work_item_ids": ["ENG-77"]},
    )
    assert wire_document_references([document]) == 1
    assert document.references[0].relationship_type == REL_REFERENCES
    assert document.references[1].work_item_id == "ENG-77"


def test_apply_ontology_cross_links_combines_wirings():
    artifact = CodeArtifact(
        repository_url="https://github.com/acme/api",
        file_path="src/a.py",
        ref="ref1",
    )
    event = ChangeEvent(
        repository_url="https://github.com/acme/api",
        pr_number=1,
        commit_sha="ref1",
        branch="main",
        loc_added=1,
        loc_removed=0,
        file_path="src/a.py",
    )
    discussion = Discussion(
        thread_id="t1",
        channel_name="inc",
        title="ENG-1",
        metadata={"linked_work_item_ids": ["ENG-1"]},
    )
    work_item = WorkItem(
        work_item_id="ENG-1",
        issue_type="Bug",
        priority="Low",
        status="Open",
        project_key="ENG",
    )
    edges = apply_ontology_cross_links([artifact, event, discussion, work_item])
    assert edges == 2
