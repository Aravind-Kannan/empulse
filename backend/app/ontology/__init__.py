"""Shared ontology spine for integration ingest."""

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
from app.ontology.spec import get_ontology_spec, is_structured_only, should_cognify_enrichment, validate_relation

__all__ = [
    "ChangeEvent",
    "CodeArtifact",
    "Discussion",
    "Document",
    "WorkItem",
    "REL_ASSIGNED",
    "REL_AUTHORED",
    "REL_BLOCKS",
    "REL_DISCUSSES",
    "REL_DOCUMENTS",
    "REL_MODIFIED",
    "get_ontology_spec",
    "is_structured_only",
    "should_cognify_enrichment",
    "validate_relation",
]
