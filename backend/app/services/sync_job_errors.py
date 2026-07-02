"""User-facing error messages for integration sync jobs."""

from __future__ import annotations


def format_sync_job_error(exc: BaseException | str | None) -> str:
    """Map internal exceptions to short, actionable sync failure messages."""
    if exc is None:
        return "Sync failed. Please try again."

    message = str(exc).strip()
    if not message:
        return "Sync failed. Please try again."

    lower = message.lower()

    if "attached to a different loop" in lower:
        return (
            "Graph database connection was reset — usually after a server reload. "
            "Restart the backend, then sync again."
        )

    if "interrupted by server restart" in lower:
        return "Sync was interrupted by a server restart. Please sync again."

    if "timed out" in lower or "timeouterror" in lower:
        return (
            "Sync timed out while waiting on the graph database or AI services. "
            "Wait a moment and retry."
        )

    if "cannot reach" in lower or "connection refused" in lower:
        return (
            "Could not reach an external service (GitHub, Jira, Notion, Slack, "
            "Neo4j, or Ollama). Check integrations and that dependent services are running."
        )

    if "not configured" in lower:
        return message

    if (
        len(message) > 240
        or "traceback" in lower
        or 'file "' in lower
        or "coro=" in lower
        or "task pending" in lower
    ):
        return (
            "Sync failed due to an internal error. "
            "Restart the backend if this keeps happening, then retry."
        )

    return message
