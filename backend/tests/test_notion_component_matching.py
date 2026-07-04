"""Notion page → GitHub component linking tests."""

from __future__ import annotations

from app.services.notion_client import match_component_for_document, parse_document_pages


COMPONENT_NAMES = {
    "comp-backend": "empulse / backend",
    "comp-design": "empulse / design-docs",
    "comp-notion": "empulse / notion-docs",
    "comp-frontend": "empulse / frontend",
    "comp-prompts": "empulse / prompts",
}

PATH_MAP = {
    "backend/": "comp-backend",
    "design-docs/": "comp-design",
    "notion-docs/": "comp-notion",
    "frontend/": "comp-frontend",
    "prompts/": "comp-prompts",
}


COMPONENT_DESCRIPTIONS = {
    "comp-backend": "AUTO:github:org/empulse:backend/",
    "comp-design": "AUTO:github:org/empulse:design-docs/",
    "comp-notion": "AUTO:github:org/empulse:notion-docs/",
    "comp-frontend": "AUTO:github:org/empulse:frontend/",
    "comp-prompts": "AUTO:github:org/empulse:prompts/",
}


def test_notion_docs_design_path_links_to_notion_component():
    component_id = match_component_for_document(
        "KRA — Knowledge Risk Assessment",
        path_hint="notion-docs/design/02-kra.md",
        component_names=COMPONENT_NAMES,
        path_component_map=PATH_MAP,
        component_descriptions=COMPONENT_DESCRIPTIONS,
    )
    assert component_id == "comp-notion"


def test_notion_docs_runbook_links_to_notion_component():
    component_id = match_component_for_document(
        "Integration sync",
        path_hint="notion-docs/runbooks/02-integration-sync.md",
        component_names=COMPONENT_NAMES,
        path_component_map=PATH_MAP,
        component_descriptions=COMPONENT_DESCRIPTIONS,
    )
    assert component_id == "comp-notion"


def test_design_docs_path_stays_on_design_component():
    component_id = match_component_for_document(
        "ERA Step 14 — DOA ownership",
        path_hint="design-docs/era/step-14-doa-ownership.md",
        component_names=COMPONENT_NAMES,
        path_component_map=PATH_MAP,
        component_descriptions=COMPONENT_DESCRIPTIONS,
    )
    assert component_id == "comp-design"


def test_title_without_path_matches_auto_tag_needles():
    component_id = match_component_for_document(
        "KRA design notes (notion docs)",
        component_names=COMPONENT_NAMES,
        path_component_map=PATH_MAP,
        component_descriptions=COMPONENT_DESCRIPTIONS,
    )
    assert component_id == "comp-notion"


def test_platform_overview_title_matches_notion_component_name():
    component_id = match_component_for_document(
        "Platform Overview — notion-docs pack",
        component_names=COMPONENT_NAMES,
        path_component_map=PATH_MAP,
        component_descriptions=COMPONENT_DESCRIPTIONS,
    )
    assert component_id == "comp-notion"


def test_repo_pack_page_parsed_with_notion_component():
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
        component_descriptions=COMPONENT_DESCRIPTIONS,
    )
    assert len(docs) == 1
    assert docs[0]["component_id"] == "comp-notion"


def test_notion_slug_url_links_employee_exit_page_to_notion_component():
    docs = parse_document_pages(
        [
            {
                "id": "39237189-07b0-811a-a8e1-e6cc767f01e4",
                "object": "page",
                "url": (
                    "https://app.notion.com/p/04-employee-exit-3923718907b0811aa8e1e6cc767f01e4"
                ),
                "last_edited_time": "2026-07-03T00:00:00+00:00",
                "properties": {
                    "title": {
                        "type": "title",
                        "title": [{"plain_text": "Employee Exit (EE)"}],
                    }
                },
            }
        ],
        component_names=COMPONENT_NAMES,
        path_component_map=PATH_MAP,
        component_descriptions=COMPONENT_DESCRIPTIONS,
    )
    assert len(docs) == 1
    assert docs[0]["component_id"] == "comp-notion"
    assert docs[0]["page_url"] == (
        "https://app.notion.com/p/04-employee-exit-3923718907b0811aa8e1e6cc767f01e4"
    )
