"""Serialize heavy background jobs on the main event loop.

Cognee and Neo4j async clients are bound to the uvicorn event loop at startup.
Running jobs in a worker thread with asyncio.run() causes loop mismatch errors.

Blocking external API calls are offloaded via asyncio.to_thread inside job code.
"""

from __future__ import annotations

import asyncio
import logging
import weakref
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Per-event-loop semaphores — safe across uvicorn --reload (new loop per worker).
_semaphores: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop,
    asyncio.Semaphore,
] = weakref.WeakKeyDictionary()


def _job_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    semaphore = _semaphores.get(loop)
    if semaphore is None:
        semaphore = asyncio.Semaphore(1)
        _semaphores[loop] = semaphore
    return semaphore


async def run_heavy_job(
    async_fn: Callable[..., Awaitable[T]],
    *args: object,
    **kwargs: object,
) -> T:
    """Run a heavy async job on the main loop, serialized with a semaphore."""
    label = getattr(async_fn, "__name__", "background_job")
    logger.info("Queueing background job: %s", label)

    async with _job_semaphore():
        logger.info("Starting background job: %s", label)
        try:
            return await async_fn(*args, **kwargs)
        finally:
            logger.info("Finished background job: %s", label)


# Backwards-compatible alias used by job schedulers.
run_off_main_loop = run_heavy_job
