"""Tests for ontology-first GitHub ingest."""

from __future__ import annotations

from app.ontology.canonical import CanonicalCodeArtifact, CanonicalPersonRef
from app.ontology.datapoints import ChangeEvent, CodeArtifact
from app.ontology.github import normalize_github_code_snapshot
from app.ontology.mapper import map_change_event, map_code_artifact
from app.ontology.relations import REL_AUTHORED, REL_DOCUMENTS, REL_MODIFIED
from app.services.cognee_ingest import GraphComponent, GraphEmployee
from app.services.github_code import GitHubCodeFileSnapshot


def test_map_code_artifact_uses_ontology_edges():
    record = CanonicalCodeArtifact(
        source="github",
        repository_url="https://github.com/acme/repo",
        file_path="backend/main.py",
        ref="abc123",
        blob_sha="sha",
        content_preview="print('hi')",
        blame_summary="lines 1-3: dev1",
        primary_authors=("dev1",),
        component=None,
        blame_author=CanonicalPersonRef(
            employee_id="emp-1",
            provider="github",
            provider_user_id="gh-dev1",
            display_name="dev1",
        ),
    )
    employees = {
        "emp-1": GraphEmployee(
            external_id="emp-1",
            name="Dev One",
            role="Engineer",
            email="dev1@acme.test",
            tenure_years=2.0,
        )
    }
    node, edge_count = map_code_artifact(record, employee_nodes=employees, component_nodes={})
    assert isinstance(node, CodeArtifact)
    assert node.authored is not None
    assert node.authored[0].relationship_type == REL_AUTHORED
    assert edge_count == 1


def test_map_change_event_uses_modified_edge():
    from app.ontology.canonical import CanonicalChangeEvent, CanonicalComponentRef

    record = CanonicalChangeEvent(
        source="github",
        event_kind="pull_request",
        repository_url="https://github.com/acme/repo",
        pr_number=42,
        commit_sha="deadbeef",
        branch="main",
        file_path="src/app.ts",
        loc_added=10,
        loc_removed=2,
        pr_url="https://github.com/acme/repo/pull/42",
        author=CanonicalPersonRef(employee_id="emp-1", display_name="dev1"),
        component=CanonicalComponentRef(component_id="comp-api", name="API"),
        properties={"pr_url": "https://github.com/acme/repo/pull/42"},
    )
    employees = {
        "emp-1": GraphEmployee(
            external_id="emp-1",
            name="Dev One",
            role="Engineer",
            email="dev1@acme.test",
            tenure_years=2.0,
        )
    }
    components = {
        "comp-api": GraphComponent(
            external_id="comp-api",
            name="API",
            description="",
            open_tasks_count=0,
            unresolved_incidents=0,
        )
    }
    node, edge_count = map_change_event(
        record,
        employee_nodes=employees,
        component_nodes=components,
    )
    assert isinstance(node, ChangeEvent)
    assert node.authored[0].relationship_type == REL_AUTHORED
    assert node.modified[0].relationship_type == REL_MODIFIED
    assert edge_count == 2


def test_normalize_github_code_snapshot_fixture(db, tenant):
    snap = GitHubCodeFileSnapshot(
        repository_url="https://github.com/acme/repo",
        file_path="backend/main.py",
        ref="deadbeef",
        component_id="comp-api",
        content_preview="code",
        content_sha="sha1",
        primary_authors=["dev1"],
    )
    canonical = normalize_github_code_snapshot(
        snap,
        db=db,
        tenant_id=tenant.id,
        components_by_id={"comp-api": type("C", (), {"name": "API"})()},
    )
    assert canonical.file_path == "backend/main.py"
    assert canonical.component is not None
    assert canonical.component.component_id == "comp-api"


def test_normalize_github_pr_file_change_without_component(db, tenant):
    from app.ontology.github import normalize_github_pr_file_change
    from app.schemas.integrations import GitHubConfigRequest
    from app.services.github_types import GitHubFileChange, GitHubPullRequestActivity

    activity = GitHubPullRequestActivity(
        pr_number=7,
        commit_sha="abc123",
        merge_commit_sha="abc123",
        branch="main",
        author_provider_user_id="gh-dev1",
        author_login="dev1",
        author_type="User",
        pr_url="https://github.com/acme/repo/pull/7",
        merged_at=None,
        files=[],
    )
    file_change = GitHubFileChange(
        path="src/unmapped.py",
        loc_added=3,
        loc_removed=1,
        component_id=None,
    )
    config = GitHubConfigRequest(
        repository_url="https://github.com/acme/repo",
        branch_target="main",
    )
    canonical = normalize_github_pr_file_change(
        activity,
        file_change,
        config=config,
        db=db,
        tenant_id=tenant.id,
        components_by_id={},
    )
    assert canonical is not None
    assert canonical.file_path == "src/unmapped.py"
    assert canonical.component is None
