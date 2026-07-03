"""Tests for phase-3 cognify enrichment policy."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from app.ontology.enrichment import (
    _format_cognify_message,
    run_post_structured_cognify_enrichment,
)
from app.ontology.spec import (
    cognify_enrichment_prompt,
    ingest_policy,
    is_structured_only,
    should_cognify_enrichment,
    uses_structured_ingest,
)
from app.services.sync_ledger import SyncIngestPlan


def test_ingest_policy_defaults_to_enrichment_for_integrations():
    assert ingest_policy("github") == "structured_with_enrichment"
    assert ingest_policy("jira") == "structured_with_enrichment"
    assert ingest_policy("notion") == "structured_with_enrichment"
    assert ingest_policy("slack") == "structured_with_enrichment"
    assert ingest_policy("unknown") == "dual_path"


def test_structured_only_is_distinct_from_enrichment():
    assert not is_structured_only("github")
    assert should_cognify_enrichment("github")
    assert uses_structured_ingest("github")


def test_cognify_enrichment_prompt_mentions_ontology_guardrails():
    prompt = cognify_enrichment_prompt("jira")
    assert "do NOT recreate" in prompt
    assert "assignedTo" in prompt
    assert "touches" in prompt


def test_run_post_structured_cognify_enrichment_skips_structured_only():
    plan = SyncIngestPlan(fetched_count=1, to_ingest=[object()], new_count=1)
    messages: list[str] = []

    def report(phase: str, message: str) -> None:
        messages.append(f"{phase}:{message}")

    with patch(
        "app.ontology.enrichment.should_cognify_enrichment",
        return_value=False,
    ), patch(
        "app.ontology.enrichment.is_structured_only",
        return_value=True,
    ), patch(
        "app.ontology.enrichment.tenant_add_and_cognify",
        new=AsyncMock(),
    ) as cognify_mock:
        asyncio.run(
            run_post_structured_cognify_enrichment(
                "github",
                __import__("uuid").uuid4(),
                "narrative",
                plan,
                report=report,
            )
        )

    cognify_mock.assert_not_called()
    assert any("structured-only" in msg for msg in messages)


def test_run_post_structured_cognify_enrichment_runs_for_enrichment_policy():
    plan = SyncIngestPlan(fetched_count=1, to_ingest=[object()], new_count=1)

    with patch(
        "app.ontology.enrichment.cognify_enrichment_available",
        return_value=True,
    ), patch(
        "app.ontology.enrichment.should_cognify_enrichment",
        return_value=True,
    ), patch(
        "app.ontology.enrichment.cognify_enrichment_prompt",
        return_value="enrichment-prompt",
    ), patch(
        "app.ontology.enrichment.tenant_add_and_cognify",
        new=AsyncMock(),
    ) as cognify_mock:
        tenant_id = __import__("uuid").uuid4()
        asyncio.run(
            run_post_structured_cognify_enrichment(
                "slack",
                tenant_id,
                "thread narrative",
                plan,
            )
        )

    cognify_mock.assert_awaited_once_with(
        "thread narrative",
        tenant_id,
        custom_prompt="enrichment-prompt",
    )


def test_format_cognify_message_includes_thread_and_elapsed():
    stats = {
        "threads_fetched": 42,
        "nodes_to_index": 38,
        "narrative_chars": 12500,
    }
    message = _format_cognify_message("slack", 75, stats)
    assert "42 threads" in message
    assert "38 graph nodes" in message
    assert "running 75s" in message
    assert "~12k chars" in message


def test_run_post_structured_cognify_enrichment_reports_heartbeat_stats():
    plan = SyncIngestPlan(fetched_count=2, to_ingest=[object(), object()], new_count=2)
    phases: list[tuple[str, str, dict | None]] = []

    def report(phase: str, message: str, stats: dict | None = None) -> None:
        phases.append((phase, message, stats))

    async def slow_cognify(*_args, **_kwargs) -> None:
        await asyncio.sleep(0.25)

    with patch(
        "app.ontology.enrichment.cognify_enrichment_available",
        return_value=True,
    ), patch(
        "app.ontology.enrichment.should_cognify_enrichment",
        return_value=True,
    ), patch(
        "app.ontology.enrichment.cognify_enrichment_prompt",
        return_value="enrichment-prompt",
    ), patch(
        "app.ontology.enrichment.COGNIFY_HEARTBEAT_SEC",
        0.05,
    ), patch(
        "app.ontology.enrichment.tenant_add_and_cognify",
        new=slow_cognify,
    ):
        asyncio.run(
            run_post_structured_cognify_enrichment(
                "slack",
                __import__("uuid").uuid4(),
                "narrative",
                plan,
                report=report,
                extra_stats={"threads_fetched": 3},
            )
        )

    assert phases[0][0] == "cognifying"
    assert phases[0][2] is not None
    assert phases[0][2]["threads_fetched"] == 3
    assert phases[0][2]["cognify_started_at"]
    assert len(phases) >= 2
    assert any(
        stats and stats.get("cognify_elapsed_sec", 0) > 0
        for _, _, stats in phases
    )


def test_run_post_structured_cognify_enrichment_skips_for_ollama_by_default():
    plan = SyncIngestPlan(fetched_count=1, to_ingest=[object()], new_count=1)
    messages: list[str] = []

    def report(phase: str, message: str, stats: dict | None = None) -> None:
        messages.append(message)

    with patch(
        "app.ontology.enrichment.get_settings",
        return_value=type(
            "S",
            (),
            {"llm_provider": "ollama", "cognify_enrichment_enabled": None},
        )(),
    ), patch(
        "app.ontology.enrichment.should_cognify_enrichment",
        return_value=True,
    ), patch(
        "app.ontology.enrichment.tenant_add_and_cognify",
        new=AsyncMock(),
    ) as cognify_mock:
        asyncio.run(
            run_post_structured_cognify_enrichment(
                "jira",
                __import__("uuid").uuid4(),
                "narrative",
                plan,
                report=report,
            )
        )

    cognify_mock.assert_not_called()
    assert any("Skipped cognify enrichment" in msg for msg in messages)
    assert any("SummarizedContent" in msg or "structured graph" in msg for msg in messages)
