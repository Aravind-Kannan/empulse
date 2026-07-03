"""Tests for cognify enrichment when Cognee Cloud is configured."""

from __future__ import annotations

from unittest.mock import patch

from app.ontology.enrichment import cognify_enrichment_available


def test_cognify_enrichment_available_when_cloud_backend():
    with patch("app.config.get_settings") as settings_mock:
        settings_mock.return_value.cognee_backend = "cloud"
        settings_mock.return_value.llm_provider = "ollama"
        settings_mock.return_value.cognify_enrichment_enabled = False
        assert cognify_enrichment_available() is True


def test_cognify_enrichment_available_when_cloud_connected():
    with patch(
        "app.services.cognee_cloud.use_cognee_cloud_backend",
        return_value=True,
    ):
        assert cognify_enrichment_available() is True
