"""Tests for tenant graph purge and structured ingest tagging."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from cognee.infrastructure.engine.models.Edge import Edge
from cognee.modules.pipelines.models.DataItemStatus import DataItemStatus

from app.ontology.datapoints import ChangeEvent, CodeArtifact
from app.ontology.relations import REL_AUTHORED, REL_DOCUMENTS
from app.services.cognee_ingest import GraphComponent, GraphEmployee
from app.services.integration_disconnect import external_key_to_node_ids
from app.services.integration_sync import GraphCodeFile
from app.services.tenant_graph_purge import (
    _ensure_structured_ingest_stub_file,
    _sync_structured_ingest_data_row,
    expand_ingest_with_org_anchors,
    tag_datapoints_with_dataset,
)


def test_tag_datapoints_with_dataset():
    node = CodeArtifact(
        repository_url="https://github.com/acme/r",
        file_path="src/a.py",
        ref="abc",
    )
    tagged = tag_datapoints_with_dataset([node], "empulse_tenant_deadbeef")
    assert tagged[0].belongs_to_set == ["empulse_tenant_deadbeef"]


def test_tag_datapoints_tags_nested_edge_targets():
    component = GraphComponent(
        external_id="comp-api",
        name="API",
        description="",
        open_tasks_count=0,
        unresolved_incidents=0,
    )
    employee = GraphEmployee(
        external_id="emp-1",
        name="Dev One",
        role="Engineer",
        email="dev1@acme.test",
        tenure_years=1.0,
    )
    node = CodeArtifact(
        repository_url="https://github.com/acme/r",
        file_path="src/a.py",
        ref="abc",
        documents=(Edge(relationship_type=REL_DOCUMENTS), component),
        authored=(Edge(relationship_type=REL_AUTHORED), employee),
    )
    dataset = "empulse_tenant_deadbeef"
    tagged = tag_datapoints_with_dataset([node], dataset)
    assert tagged[0].belongs_to_set == [dataset]
    assert tagged[0].documents[1].belongs_to_set == [dataset]
    assert tagged[0].authored[1].belongs_to_set == [dataset]


def test_expand_ingest_with_org_anchors_adds_referenced_nodes():
    component = GraphComponent(
        external_id="comp-api",
        name="API",
        description="",
        open_tasks_count=0,
        unresolved_incidents=0,
    )
    employee = GraphEmployee(
        external_id="emp-1",
        name="Dev One",
        role="Engineer",
        email="dev1@acme.test",
        tenure_years=1.0,
    )
    change = ChangeEvent(
        repository_url="https://github.com/acme/r",
        pr_number=1,
        commit_sha="abc",
        branch="main",
        loc_added=1,
        loc_removed=0,
        file_path="src/a.py",
        authored=(Edge(relationship_type=REL_AUTHORED), employee),
        modified=(Edge(relationship_type="modified"), component),
    )
    expanded = expand_ingest_with_org_anchors(
        [change],
        employee_nodes={"emp-1": employee},
        component_nodes={"comp-api": component},
    )
    external_ids = {getattr(point, "external_id", None) for point in expanded}
    assert external_ids == {None, "emp-1", "comp-api"}
    assert len(expanded) == 3


def test_external_key_resolves_legacy_and_current_github_code_ids():
    external_key = "code|https://github.com/acme/api|src/main.py|deadbeef"
    ids = external_key_to_node_ids("github", external_key)
    assert len(ids) == 3
    assert ids[0] == CodeArtifact.id_for(
        "https://github.com/acme/api",
        "src/main.py",
    )
    assert ids[1] == GraphCodeFile.id_for(
        "https://github.com/acme/api",
        "src/main.py",
        "deadbeef",
    )
    assert ids[2] == CodeArtifact.id_for(
        "https://github.com/acme/api",
        "src/main.py",
        "deadbeef",
    )
    assert len(set(ids)) == 3


def test_structured_ingest_stub_file_uses_real_file_uri(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.tenant_graph_purge.get_settings",
        lambda: SimpleNamespace(cognee_data_root=str(tmp_path)),
    )
    dataset_id = uuid.uuid4()
    uri = _ensure_structured_ingest_stub_file(dataset_id)
    assert uri.startswith("file://")
    stub_path = tmp_path / "empulse_structured_ingest" / f"{dataset_id}.txt"
    assert stub_path.is_file()


def test_sync_structured_ingest_data_row_migrates_memory_path(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.tenant_graph_purge.get_settings",
        lambda: SimpleNamespace(cognee_data_root=str(tmp_path)),
    )
    dataset_id = uuid.uuid4()
    row = SimpleNamespace(
        raw_data_location="memory://empulse-structured-graph",
        original_data_location="memory://empulse-structured-graph",
        extension="json",
        mime_type="application/json",
        loader_engine="json",
        pipeline_status={},
        external_metadata=None,
    )
    changed = _sync_structured_ingest_data_row(row, dataset_id)
    assert changed is True
    assert row.raw_data_location.startswith("file://")
    assert row.extension == "txt"
    assert row.pipeline_status["cognify_pipeline"][str(dataset_id)] == (
        DataItemStatus.DATA_ITEM_PROCESSING_COMPLETED
    )
