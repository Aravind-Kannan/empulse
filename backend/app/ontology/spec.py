"""Load ontology.yaml for ingest policy and relation validation."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.ontology.relations import (
    REL_ASSIGNED,
    REL_AUTHORED,
    REL_BLOCKS,
    REL_DISCUSSES,
    REL_DOCUMENTS,
    REL_MODIFIED,
    REL_OWNS,
    REL_REFERENCES,
    REL_REPORTS_TO,
    REL_RESOLVES,
    REL_TOUCHES,
)

_ONTOLOGY_PATH = Path(__file__).with_name("ontology.yaml")
_BUILTIN_RELATIONS = frozenset(
    {
        REL_AUTHORED,
        REL_DOCUMENTS,
        REL_MODIFIED,
        REL_ASSIGNED,
        REL_BLOCKS,
        REL_DISCUSSES,
        REL_TOUCHES,
        REL_RESOLVES,
        REL_REFERENCES,
        REL_OWNS,
        REL_REPORTS_TO,
    }
)


@dataclass(frozen=True)
class OntologySpec:
    types: dict[str, object]
    relations: dict[str, str]
    ingest_policy: dict[str, str]


@lru_cache(maxsize=1)
def get_ontology_spec() -> OntologySpec:
    raw = yaml.safe_load(_ONTOLOGY_PATH.read_text(encoding="utf-8"))
    return OntologySpec(
        types=dict(raw.get("types") or {}),
        relations=dict(raw.get("relations") or {}),
        ingest_policy={
            str(source).lower(): str(mode)
            for source, mode in (raw.get("ingest_policy") or {}).items()
        },
    )


def ingest_policy(source: str) -> str:
    return get_ontology_spec().ingest_policy.get(source.lower().strip(), "dual_path")


def is_structured_only(source: str) -> bool:
    return ingest_policy(source) == "structured_only"


def uses_structured_ingest(source: str) -> bool:
    return ingest_policy(source) in {"structured_only", "structured_with_enrichment"}


def should_cognify_enrichment(source: str) -> bool:
    return ingest_policy(source) == "structured_with_enrichment"


def cognify_enrichment_prompt(source: str) -> str:
    relations = ", ".join(sorted(allowed_relations()))
    normalized = source.lower().strip()
    return (
        f"Empulse ontology enrichment for {normalized} integration sync. "
        "Structured ontology DataPoints (CodeArtifact, ChangeEvent, WorkItem, "
        "Document, Discussion, GraphEmployee, GraphComponent) are already ingested "
        "with deterministic IDs — do NOT recreate those entities or duplicate their "
        "primary keys. From this narrative, add only supplementary retrieval context: "
        "short semantic summaries, incident themes, and cross-references between "
        f"people, components, and work items. Use only these relation names: {relations}."
    )


def cognify_enrichment_message(source: str) -> str:
    normalized = source.lower().strip()
    return (
        f"Running ontology-scoped cognify enrichment for {normalized} "
        "(structured graph already indexed)…"
    )


def allowed_relations() -> frozenset[str]:
    spec = get_ontology_spec()
    names = set(_BUILTIN_RELATIONS)
    names.update(spec.relations.keys())
    return frozenset(names)


def validate_relation(relationship_type: str) -> str:
    if relationship_type not in allowed_relations():
        allowed = ", ".join(sorted(allowed_relations()))
        raise ValueError(
            f"Unknown ontology relation '{relationship_type}'. Allowed: {allowed}"
        )
    return relationship_type
