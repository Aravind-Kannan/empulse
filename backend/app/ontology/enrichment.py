"""Optional Cognee enrichment on top of structured ontology ingest (phase 3)."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.ontology.spec import (
    cognify_enrichment_message,
    cognify_enrichment_prompt,
    ingest_policy,
    is_structured_only,
    should_cognify_enrichment,
)
from app.config import get_settings
from app.services.tenant_cognee import tenant_add_and_cognify

logger = logging.getLogger(__name__)

COGNIFY_HEARTBEAT_SEC = 12

_OLLAMA_LIKE_PROVIDERS = frozenset({"ollama", "local"})


def cognify_enrichment_available() -> bool:
    """
    Whether post-structured cognify enrichment should run.

    Ollama/local models frequently return JSON that does not match Cognee's
    SummarizedContent instructor schema, causing long retry loops.
    Structured ontology nodes are already indexed without this step.
    Cognee Cloud uses hosted LLMs — always run enrichment when COGNEE_BACKEND=cloud.
    """
    from app.services.cognee_cloud import use_cognee_cloud_backend

    if use_cognee_cloud_backend():
        return True

    settings = get_settings()
    if settings.cognify_enrichment_enabled is not None:
        return settings.cognify_enrichment_enabled
    return settings.llm_provider.lower().strip() not in _OLLAMA_LIKE_PROVIDERS


def cognify_enrichment_skip_reason() -> str:
    from app.services.cognee_cloud import use_cognee_cloud_backend

    if use_cognee_cloud_backend():
        return "cognee cloud backend"

    settings = get_settings()
    if settings.cognify_enrichment_enabled is False:
        return "COGNIFY_ENRICHMENT_ENABLED=false"
    provider = settings.llm_provider.lower().strip()
    if provider in _OLLAMA_LIKE_PROVIDERS:
        return (
            f"{provider} LLM cannot reliably satisfy Cognee SummarizedContent schema "
            "(structured graph nodes are already indexed)"
        )
    return "cognify enrichment disabled"


def _build_cognify_stats(
    ingest_plan: Any,
    narrative: str,
    extra: dict[str, int | str] | None = None,
) -> dict[str, int | str]:
    stats: dict[str, int | str] = {
        "cognify_phase": "running",
        "cognify_started_at": datetime.now(UTC).isoformat(),
        "nodes_to_index": len(ingest_plan.to_ingest),
        "nodes_new": ingest_plan.new_count,
        "nodes_skipped": ingest_plan.skipped_count,
        "narrative_chars": len(narrative),
    }
    if extra:
        stats.update(extra)
    return stats


def _format_cognify_message(
    source: str,
    elapsed_sec: int,
    stats: dict[str, int | str],
) -> str:
    base = cognify_enrichment_message(source).rstrip("…")
    detail_parts: list[str] = []
    threads = stats.get("threads_fetched")
    if threads:
        detail_parts.append(f"{threads} threads")
    issues = stats.get("issues_fetched")
    if issues:
        detail_parts.append(f"{issues} issues")
    pages = stats.get("pages_fetched")
    if pages:
        detail_parts.append(f"{pages} pages")
    nodes = stats.get("nodes_to_index")
    if nodes:
        detail_parts.append(f"{nodes} graph nodes indexed")
    chars = stats.get("narrative_chars")
    if chars and int(chars) > 500:
        kb = max(1, int(chars) // 1000)
        detail_parts.append(f"~{kb}k chars for LLM enrichment")
    if elapsed_sec > 0:
        detail_parts.append(f"running {elapsed_sec}s")
    if detail_parts:
        return f"{base} · {' · '.join(detail_parts)}…"
    return f"{base}…"


async def _tenant_add_and_cognify_with_heartbeat(
    narrative: str,
    tenant_id: uuid.UUID,
    *,
    custom_prompt: str | None,
    source: str,
    stats: dict[str, int | str],
    report: Callable[..., None],
) -> None:
    started = time.monotonic()
    stopped = asyncio.Event()

    async def heartbeat() -> None:
        while not stopped.is_set():
            try:
                await asyncio.wait_for(stopped.wait(), timeout=COGNIFY_HEARTBEAT_SEC)
                return
            except TimeoutError:
                elapsed = max(1, int(time.monotonic() - started))
                report(
                    "cognifying",
                    _format_cognify_message(source, elapsed, stats),
                    {**stats, "cognify_elapsed_sec": elapsed},
                )

    heartbeat_task = asyncio.create_task(heartbeat())
    try:
        await tenant_add_and_cognify(
            narrative,
            tenant_id,
            custom_prompt=custom_prompt,
        )
    finally:
        stopped.set()
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass


def _short_error(exc: BaseException, *, limit: int = 180) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


async def _run_cognify_enrichment(
    narrative: str,
    tenant_id: uuid.UUID,
    *,
    custom_prompt: str | None,
    source: str,
    stats: dict[str, int | str],
    report: Callable[..., None],
) -> bool:
    """Run cognify enrichment; return True on success, False if skipped/failed."""
    try:
        await _tenant_add_and_cognify_with_heartbeat(
            narrative,
            tenant_id,
            custom_prompt=custom_prompt,
            source=source,
            stats=stats,
            report=report,
        )
        return True
    except Exception as exc:
        logger.warning(
            "Cognify enrichment failed for %s (structured ingest already indexed): %s",
            source,
            exc,
            exc_info=True,
        )
        report(
            "cognifying",
            (
                f"Skipped cognify enrichment for {source} — LLM structured output failed. "
                f"Structured graph nodes remain indexed. ({_short_error(exc)})"
            ),
            {**stats, "cognify_phase": "failed", "cognify_error": _short_error(exc)},
        )
        return False


async def run_post_structured_cognify_enrichment(
    source: str,
    tenant_id: uuid.UUID,
    narrative: str,
    ingest_plan: Any,
    report: Callable[..., None] | None = None,
    *,
    extra_stats: dict[str, int | str] | None = None,
) -> None:
    """
    Run cognify after structured DataPoint ingest when policy allows.

    structured_only — skip (deterministic graph only)
    structured_with_enrichment — add narrative + ontology-scoped cognify
    dual_path — legacy cognify prompt (unstructured-first integrations)
    """
    normalized = source.lower().strip()

    def _report(phase: str, message: str, stats: dict | None = None) -> None:
        if report is None:
            return
        if stats is None:
            report(phase, message)
        else:
            report(phase, message, stats)

    if not ingest_plan.should_cognify:
        _report("cognifying", ingest_plan.cognify_message())
        return

    if is_structured_only(normalized):
        _report(
            "cognifying",
            f"Skipped cognify — {normalized} uses structured-only ontology ingest.",
        )
        return

    if not cognify_enrichment_available():
        _report(
            "cognifying",
            f"Skipped cognify enrichment — {cognify_enrichment_skip_reason()}.",
            {"cognify_phase": "skipped", "nodes_to_index": len(ingest_plan.to_ingest)},
        )
        return

    if should_cognify_enrichment(normalized):
        cognify_stats = _build_cognify_stats(ingest_plan, narrative, extra_stats)
        _report(
            "cognifying",
            _format_cognify_message(normalized, 0, cognify_stats),
            cognify_stats,
        )
        await _run_cognify_enrichment(
            narrative,
            tenant_id,
            custom_prompt=cognify_enrichment_prompt(normalized),
            source=normalized,
            stats=cognify_stats,
            report=_report,
        )
        return

    if ingest_policy(normalized) == "dual_path":
        cognify_stats = _build_cognify_stats(ingest_plan, narrative, extra_stats)
        _report("cognifying", ingest_plan.cognify_message(), cognify_stats)
        await _run_cognify_enrichment(
            narrative,
            tenant_id,
            custom_prompt=(
                f"Extract {normalized} metadata using ontology relations: "
                "authored, documents, modified, assignedTo, blocks, discusses, "
                "touches, resolves, references, owns, reportsTo."
            ),
            source=normalized,
            stats=cognify_stats,
            report=_report,
        )
        return

    _report("cognifying", ingest_plan.cognify_message())
