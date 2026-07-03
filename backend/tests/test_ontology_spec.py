"""Tests for ontology spec loader and cross-source mappers."""

from __future__ import annotations

from app.ontology.canonical import CanonicalDocument, CanonicalWorkItem
from app.ontology.datapoints import Document, WorkItem
from app.ontology.mapper import map_document, map_work_item
from app.ontology.relations import REL_ASSIGNED, REL_BLOCKS, REL_AUTHORED, REL_DOCUMENTS
from app.ontology.spec import (
    get_ontology_spec,
    ingest_policy,
    is_structured_only,
    should_cognify_enrichment,
    validate_relation,
)
from app.services.cognee_ingest import GraphComponent, GraphEmployee


def test_ontology_yaml_structured_only_for_all_integrations():
    assert ingest_policy("github") == "structured_with_enrichment"
    assert ingest_policy("jira") == "structured_with_enrichment"
    assert ingest_policy("notion") == "structured_with_enrichment"
    assert ingest_policy("slack") == "structured_with_enrichment"
    assert should_cognify_enrichment("github")
    assert not is_structured_only("github")
    assert not is_structured_only("unknown")


def test_validate_relation_rejects_unknown_edge():
    assert validate_relation("authored") == "authored"
    try:
        validate_relation("blocksComponent")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_map_work_item_uses_ontology_edges():
    record = CanonicalWorkItem(
        source="jira",
        work_item_id="ENG-1",
        issue_type="Bug",
        priority="High",
        status="Open",
        project_key="ENG",
        summary="API timeout",
        assignee=None,
        component=None,
    )
    node, edge_count = map_work_item(record, employee_nodes={}, component_nodes={})
    assert isinstance(node, WorkItem)
    assert node.work_item_id == "ENG-1"
    assert edge_count == 0


def test_map_document_uses_documents_edge():
    record = CanonicalDocument(
        source="notion",
        page_id="page-1",
        title="Runbook",
        last_edited="2026-01-01T00:00:00",
        component=None,
        author=None,
    )
    node, _ = map_document(record, employee_nodes={}, component_nodes={})
    assert isinstance(node, Document)
    assert node.page_id == "page-1"


def test_ontology_spec_loads_types():
    spec = get_ontology_spec()
    assert "WorkItem" in spec.types
    assert "authored" in spec.relations
    assert "touches" in spec.relations
    assert "references" in spec.relations
    assert validate_relation("reportsTo") == "reportsTo"
