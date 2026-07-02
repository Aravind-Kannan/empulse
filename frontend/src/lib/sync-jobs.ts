import type { IntegrationSyncJobStatusResponse } from "@/lib/types";
import type { IntegrationId } from "@/lib/integrations";

export function jobsBySource(
  jobs: IntegrationSyncJobStatusResponse[],
): Map<IntegrationId, IntegrationSyncJobStatusResponse[]> {
  const bySource = new Map<IntegrationId, IntegrationSyncJobStatusResponse[]>();
  for (const job of jobs) {
    const source = job.source as IntegrationId;
    const existing = bySource.get(source) ?? [];
    existing.push(job);
    bySource.set(source, existing);
  }
  return bySource;
}

export function latestJobPerSource(
  jobs: IntegrationSyncJobStatusResponse[],
): Map<IntegrationId, IntegrationSyncJobStatusResponse> {
  const bySource = new Map<IntegrationId, IntegrationSyncJobStatusResponse>();
  for (const job of jobs) {
    const source = job.source as IntegrationId;
    const existing = bySource.get(source);
    if (
      !existing ||
      new Date(job.created_at).getTime() > new Date(existing.created_at).getTime()
    ) {
      bySource.set(source, job);
    }
  }
  return bySource;
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
  if (!connected) {
    return { text: "Not connected", className: "text-zinc-500" };
  }
  return { text: "Ready to sync", className: "text-zinc-400" };
}
