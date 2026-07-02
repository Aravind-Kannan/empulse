/** User-facing messages for integration sync job failures. */

export function formatSyncJobError(raw: string | null | undefined): string {
  if (!raw?.trim()) {
    return "Sync failed. Please try again.";
  }

  const message = raw.trim();
  const lower = message.toLowerCase();

  if (lower.includes("attached to a different loop")) {
    return (
      "Graph database connection was reset — usually after a server reload. " +
      "Restart the backend, then sync again."
    );
  }

  if (lower.includes("interrupted by server restart")) {
    return "Sync was interrupted by a server restart. Please sync again.";
  }

  if (lower.includes("timed out") || lower.includes("timeouterror")) {
    return (
      "Sync timed out while waiting on the graph database or AI services. " +
      "Wait a moment and retry."
    );
  }

  if (lower.includes("cannot reach") || lower.includes("connection refused")) {
    return (
      "Could not reach an external service. Check integrations and that " +
      "GitHub, Jira, Neo4j, and Ollama are available."
    );
  }

  if (
    message.length > 240 ||
    lower.includes("traceback") ||
    lower.includes('file "') ||
    lower.includes("coro=") ||
    lower.includes("task pending")
  ) {
    return (
      "Sync failed due to an internal error. " +
      "Restart the backend if this keeps happening, then retry."
    );
  }

  return message;
}
