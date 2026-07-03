"""Tests for phase-2 ontology cross-links."""

from __future__ import annotations

from cognee.infrastructure.engine.models.Edge import Edge

from app.ontology.crosslinks import (
    apply_ontology_cross_links,
    consolidate_code_artifacts,
    wire_discussion_resolves,
    wire_document_references,
    wire_github_touches,
)
from app.ontology.datapoints import ChangeEvent, CodeArtifact, Discussion, Document, WorkItem
from app.ontology.jira_keys import extract_jira_issue_keys as extract_keys
from app.ontology.relations import REL_AUTHORED, REL_REFERENCES, REL_RESOLVES, REL_TOUCHES
from app.services.cognee_ingest import GraphEmployee


def test_extract_jira_issue_keys():
    assert extract_keys("Investigating ENG-42 and ENG-42 again") == ("ENG-42",)
    assert extract_keys("no ticket here") == ()
    assert extract_keys("linked to eng-99 in slack", "follow-up ENG-100") == (
        "ENG-99",
        "ENG-100",
    )


def test_consolidate_code_artifacts_merges_same_path():
    author_one = GraphEmployee(
        external_id="emp-1",
        name="Dev One",
        role="Engineer",
        email="dev1@acme.test",
        tenure_years=2.0,
    )
    author_two = GraphEmployee(
        external_id="emp-2",
        name="Dev Two",
        role="Engineer",
        email="dev2@acme.test",
        tenure_years=1.0,
    )
    artifact_main = CodeArtifact(
        repository_url="https://github.com/acme/api",
        file_path="src/shared.py",
        ref="main-sha",
        primary_authors="dev1",
    )
    artifact_main.authored = (Edge(relationship_type=REL_AUTHORED), author_one)
    artifact_feature = CodeArtifact(
        repository_url="https://github.com/acme/api",
        file_path="src/shared.py",
        ref="feature-sha",
        primary_authors="dev2",
    )
    artifact_feature.authored = (Edge(relationship_type=REL_AUTHORED), author_two)
    points = [artifact_main, artifact_feature]
    assert consolidate_code_artifacts(points) == 1
    assert len(points) == 1
    merged = points[0]
    assert "dev1" in merged.primary_authors
    assert "dev2" in merged.primary_authors
    assert isinstance(merged.authored, list)
    assert len(merged.authored) == 2


def test_wire_github_touches_links_change_author_to_shared_file():
    author = GraphEmployee(
        external_id="emp-1",
        name="Dev One",
        role="Engineer",
        email="dev1@acme.test",
        tenure_years=2.0,
    )
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
    event.authored = (Edge(relationship_type=REL_AUTHORED), author)
    assert wire_github_touches([artifact, event]) == 2
    assert artifact.authored is not None
    if isinstance(artifact.authored, list):
        assert len(artifact.authored) == 1
        assert artifact.authored[0][1] is author
    else:
        assert artifact.authored[1] is author


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
