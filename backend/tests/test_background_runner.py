"""Tests for serialized background job runner."""

from __future__ import annotations

import asyncio

from app.services.background_runner import run_heavy_job


def test_run_heavy_job_executes_async_fn():
    seen: list[str] = []

    async def job(value: str) -> str:
        await asyncio.sleep(0.01)
        seen.append(value)
        return f"done:{value}"

    async def run() -> str:
        return await run_heavy_job(job, "sync")

    result = asyncio.run(run())
    assert result == "done:sync"
    assert seen == ["sync"]
