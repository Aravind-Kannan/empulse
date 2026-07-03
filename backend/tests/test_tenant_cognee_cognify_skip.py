"""Tests for Ollama-safe Cognee cognify guards."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from app.services.tenant_cognee import tenant_add_and_cognify


def test_tenant_add_and_cognify_skips_for_ollama():
    with patch(
        "app.ontology.enrichment.cognify_enrichment_available",
        return_value=False,
    ), patch(
        "app.ontology.enrichment.cognify_enrichment_skip_reason",
        return_value="ollama LLM cannot reliably satisfy Cognee SummarizedContent schema",
    ), patch(
        "app.services.tenant_cognee.run_cognee_add_and_cognify",
        new_callable=AsyncMock,
    ) as cognify_mock:
        tenant_id = __import__("uuid").uuid4()
        result = asyncio.run(
            tenant_add_and_cognify("narrative", tenant_id, custom_prompt="prompt"),
        )

    cognify_mock.assert_not_called()
    assert result["skipped"] is True
    assert "ollama" in result["skip_reason"]
