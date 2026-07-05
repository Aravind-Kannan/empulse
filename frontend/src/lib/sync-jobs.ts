import { apiDateToEpochMs } from "@/lib/datetime";
import {
  INTEGRATION_CATALOG,
  isIntegrationConnected,
  type IntegrationConfigMap,
  type IntegrationId,
} from "@/lib/integrations";
import type { IntegrationSyncJobStatusResponse } from "@/lib/types";

const BACKEND_SYNC_SOURCES = new Set<IntegrationId>(["github", "jira", "notion", "slack"]);

export function connectedBackendIntegrations(
  config: IntegrationConfigMap,
): IntegrationId[] {
  return INTEGRATION_CATALOG.filter(
    (app) =>
      BACKEND_SYNC_SOURCES.has(app.id) && isIntegrationConnected(app.id, config),
  ).map((app) => app.id);
}

/** True when every connected backend source has zero sync jobs on record. */
export function integrationsNeverSynced(
  config: IntegrationConfigMap,
  syncJobs: IntegrationSyncJobStatusResponse[],
): boolean {
  const connected = connectedBackendIntegrations(config);
  if (connected.length === 0) return false;
  const latestBySource = latestJobPerSource(syncJobs);
  return connected.every((id) => !latestBySource.has(id));
}

export function jobsBySource(
  jobs: IntegrationSyncJobStatusResponse[],
): Map<IntegrationId, IntegrationSyncJobStatusResponse[]> {
  const bySource = new Map<IntegrationId, IntegrationSyncJobStatusResponse[]>();
  for (const job of jobs) {
    const source =
      job.source === "github_repo" ? ("github" as IntegrationId) : (job.source as IntegrationId);
    const existing = bySource.get(source) ?? [];
    existing.push(job);
    bySource.set(source, existing);
  }
  return bySource;
}

export function jobsForIntegration(
  jobs: IntegrationSyncJobStatusResponse[],
  integrationId: IntegrationId,
): IntegrationSyncJobStatusResponse[] {
  if (integrationId === "github") {
    return jobs.filter(
      (job) => job.source === "github" || job.source === "github_repo",
    );
  }
  return jobs.filter((job) => job.source === integrationId);
}

export function latestJobPerSource(
  jobs: IntegrationSyncJobStatusResponse[],
): Map<IntegrationId, IntegrationSyncJobStatusResponse> {
  const bySource = new Map<IntegrationId, IntegrationSyncJobStatusResponse>();
  for (const job of jobs) {
    const source =
      job.source === "github_repo" ? ("github" as IntegrationId) : (job.source as IntegrationId);
    const existing = bySource.get(source);
    if (
      !existing ||
      apiDateToEpochMs(job.created_at) > apiDateToEpochMs(existing.created_at)
    ) {
      bySource.set(source, job);
    }
  }
  return bySource;
}

export function jobIntegrationId(
  job: IntegrationSyncJobStatusResponse,
): IntegrationId | null {
  if (job.source === "github" || job.source === "github_repo") {
    return "github";
  }
  if (job.source === "jira" || job.source === "slack" || job.source === "notion") {
    return job.source;
  }
  return null;
}

export function syncJobShortTitle(job: IntegrationSyncJobStatusResponse): string {
  if (job.job_kind === "github_repo" && job.repository_url) {
    try {
      const parts = new URL(job.repository_url).pathname.split("/").filter(Boolean);
      if (parts.length >= 2) {
        return `${parts[0]}/${parts[1]}`;
      }
    } catch {
      // fall through
    }
  }
  const integrationId = jobIntegrationId(job);
  return (
    INTEGRATION_CATALOG.find((app) => app.id === integrationId)?.name ??
    job.source.charAt(0).toUpperCase() + job.source.slice(1)
  );
}

export function syncJobKindLabel(job: IntegrationSyncJobStatusResponse): string | null {
  if (job.job_kind === "github_repo") {
    return "Full repo";
  }
  if (job.source === "github") {
    return "Activity";
  }
  return null;
}

export function syncJobLabel(job: IntegrationSyncJobStatusResponse): string {
  if (job.job_kind === "github_repo" && job.repository_url) {
    try {
      const parts = new URL(job.repository_url).pathname.split("/").filter(Boolean);
      if (parts.length >= 2) {
        return `GitHub repo ${parts[0]}/${parts[1]}`;
      }
    } catch {
      // fall through
    }
    return `GitHub repo ${job.repository_url}`;
  }
  return job.source.charAt(0).toUpperCase() + job.source.slice(1);
}

export interface WorkspaceSyncStats {
  newItems: number;
  updatedItems: number;
  skippedItems: number;
  changedItems: number;
  completedCount: number;
  lastCompletedAt: string | null;
}

export function aggregateWorkspaceSyncStats(
  jobs: IntegrationSyncJobStatusResponse[],
): WorkspaceSyncStats {
  const completed = jobs.filter((job) => job.status === "completed" && job.result);
  let newItems = 0;
  let updatedItems = 0;
  let skippedItems = 0;
  let lastCompletedAt: string | null = null;
  let lastCompletedMs = 0;

  for (const job of completed) {
    const result = job.result!;
    newItems += result.items_new ?? 0;
    updatedItems += result.items_updated ?? 0;
    skippedItems += result.items_skipped ?? 0;
    if (job.completed_at) {
      const completedMs = apiDateToEpochMs(job.completed_at);
      if (completedMs > lastCompletedMs) {
        lastCompletedMs = completedMs;
        lastCompletedAt = job.completed_at;
      }
    }
  }

  return {
    newItems,
    updatedItems,
    skippedItems,
    changedItems: newItems + updatedItems,
    completedCount: completed.length,
    lastCompletedAt,
  };
}

export function formatSyncChangeSummary(
  newItems: number,
  updatedItems: number,
  skippedItems?: number,
): string {
  const parts: string[] = [];
  if (newItems > 0) parts.push(`${newItems.toLocaleString()} new`);
  if (updatedItems > 0) parts.push(`${updatedItems.toLocaleString()} updated`);
  if (skippedItems !== undefined && skippedItems > 0) {
    parts.push(`${skippedItems.toLocaleString()} unchanged`);
  }
  return parts.join(" · ") || "No changes";
}

export function latestCompletedJob(
  jobs: IntegrationSyncJobStatusResponse[],
): IntegrationSyncJobStatusResponse | null {
  let latest: IntegrationSyncJobStatusResponse | null = null;
  let latestMs = 0;

  for (const job of jobs) {
    if (job.status !== "completed" || !job.result) continue;
    const completedMs = apiDateToEpochMs(job.completed_at ?? job.created_at);
    if (completedMs >= latestMs) {
      latestMs = completedMs;
      latest = job;
    }
  }

  return latest;
}

export function sourcesNeedingAttention(
  config: IntegrationConfigMap,
  syncJobs: IntegrationSyncJobStatusResponse[],
): { count: number; labels: string[] } {
  const connected = connectedBackendIntegrations(config);
  const latestBySource = latestJobPerSource(syncJobs);
  const labels: string[] = [];

  for (const id of connected) {
    const latest = latestBySource.get(id);
    const appName = INTEGRATION_CATALOG.find((app) => app.id === id)?.name ?? id;
    if (!latest || latest.status === "failed" || latest.status === "cancelled") {
      labels.push(appName);
    }
  }

  return { count: labels.length, labels };
}

export function syncStatusLabel(
  job: IntegrationSyncJobStatusResponse | null,
  syncing: boolean,
  connected: boolean,
): { text: string; className: string } {
  if (syncing || job?.status === "running" || job?.status === "queued") {
    return { text: "Syncing", className: "text-sky-400" };
  }
  if (job?.status === "completed") {
    return { text: "Synced", className: "text-emerald-400" };
  }
  if (job?.status === "failed") {
    return { text: "Sync failed", className: "text-red-400" };
  }
  if (job?.status === "cancelled") {
    return { text: "Cancelled", className: "text-zinc-500" };
  }
  if (!connected) {
    return { text: "Not connected", className: "text-zinc-500" };
  }
  return { text: "Awaiting first import", className: "text-zinc-400" };
}
