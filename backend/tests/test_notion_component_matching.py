"""Notion page → GitHub component linking tests."""

from __future__ import annotations

from app.services.notion_client import match_component_for_document, parse_document_pages


COMPONENT_NAMES = {
    "comp-backend": "Aravind-Kannan/empulse / Backend",
    "comp-design": "Aravind-Kannan/empulse / Design Docs",
    "comp-frontend": "Aravind-Kannan/empulse / Frontend",
    "comp-prompts": "Aravind-Kannan/empulse / Prompts",
}

PATH_MAP = {
    "backend/": "comp-backend",
    "design-docs/": "comp-design",
    "frontend/": "comp-frontend",
    "prompts/": "comp-prompts",
}


def test_path_prefix_links_notion_docs_design():
    component_id = match_component_for_document(
        "KRA — Knowledge Risk Assessment",
        path_hint="notion-docs/design/02-kra.md",
        component_names=COMPONENT_NAMES,
        path_component_map=PATH_MAP,
    )
    assert component_id == "comp-design"


def test_path_prefix_links_runbook_to_backend():
    component_id = match_component_for_document(
        "Integration sync",
        path_hint="notion-docs/runbooks/02-integration-sync.md",
        component_names=COMPONENT_NAMES,
        path_component_map=PATH_MAP,
    )
    assert component_id == "comp-backend"


def test_title_topic_links_kra_without_path():
    component_id = match_component_for_document(
        "KRA design notes",
        component_names=COMPONENT_NAMES,
        path_component_map=PATH_MAP,
    )
    assert component_id == "comp-design"


def test_repo_pack_page_parsed_with_component():
    docs = parse_document_pages(
        [
            {
                "page_id": "github-abc",
                "title": "KRA — Knowledge Risk Assessment",
                "page_url": "https://github.com/org/repo/blob/main/notion-docs/design/02-kra.md",
                "last_edited_at": "2026-07-03T00:00:00+00:00",
                "repo_path": "notion-docs/design/02-kra.md",
                "page_kind": "architecture",
                "is_archived": False,
            }
        ],
        component_names=COMPONENT_NAMES,
        path_component_map=PATH_MAP,
    )
    assert len(docs) == 1
    assert docs[0]["component_id"] == "comp-design"
