"""Tests for GitHub component display labels."""

from app.services.github_component_display import (
    format_github_component_name,
    format_github_component_name_from_description,
    format_github_component_name_from_label,
)


def test_format_github_component_name_from_auto_description():
    name = format_github_component_name_from_description(
        "AUTO:github:Aravind-Kannan/empulse:notion-docs/"
    )
    assert name == "empulse / notion-docs"


def test_format_github_component_name_from_legacy_label():
    name = format_github_component_name_from_label(
        "Aravind-Kannan/empulse / Notion Docs"
    )
    assert name == "empulse / notion-docs"


def test_format_github_component_name_nested_path_uses_first_folder():
    assert format_github_component_name("acme/empulse", "backend/app/") == "empulse / backend"


def test_display_folder_uses_feature_name_not_docs_root():
    from app.services.github_component_display import display_folder

    assert display_folder("docs/features/era/") == "era"
    assert display_folder("notion-docs/design/") == "notion-docs"
    assert format_github_component_name(
        "Aravind-Kannan/empulse", "docs/features/integration-sync/"
    ) == "empulse / integration-sync"
