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


def is_heavy_job_queue_busy() -> bool:
    """True when another heavy background job holds the global job semaphore."""
    return _job_semaphore().locked()


_current_heavy_job_label: str | None = None


def current_heavy_job_label() -> str | None:
    """Name of the async function currently holding the global job semaphore."""
    return _current_heavy_job_label


_QUEUE_WAIT_NOTIFY_SEC = 0.35


async def run_heavy_job(
    async_fn: Callable[..., Awaitable[T]],
    *args: object,
    on_waiting: Callable[[], None] | None = None,
    **kwargs: object,
) -> T:
    """Run a heavy async job on the main loop, serialized with a semaphore."""
    label = getattr(async_fn, "__name__", "background_job")
    holder = current_heavy_job_label()
    if holder:
        logger.info(
            "Queueing background job: %s (waiting — %s holds the job slot)",
            label,
            holder,
        )
    else:
        logger.info("Queueing background job: %s", label)

    semaphore = _job_semaphore()
    acquired = False
    wait_notifier: asyncio.Task[None] | None = None

    if on_waiting is not None:

        async def _notify_if_still_waiting() -> None:
            await asyncio.sleep(_QUEUE_WAIT_NOTIFY_SEC)
            if not acquired:
                on_waiting()

        wait_notifier = asyncio.create_task(_notify_if_still_waiting())

    global _current_heavy_job_label

    try:
        async with semaphore:
            acquired = True
            if wait_notifier is not None:
                wait_notifier.cancel()
            _current_heavy_job_label = label
            logger.info("Starting background job: %s", label)
            try:
                return await async_fn(*args, **kwargs)
            finally:
                logger.info("Finished background job: %s", label)
                _current_heavy_job_label = None
    finally:
        if wait_notifier is not None and not wait_notifier.done():
            wait_notifier.cancel()


# Backwards-compatible alias used by job schedulers.
run_off_main_loop = run_heavy_job
