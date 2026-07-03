import type { IntegrationSyncJobStatusResponse } from "@/lib/types";
import type { IntegrationId } from "@/lib/integrations";

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
      new Date(job.created_at).getTime() > new Date(existing.created_at).getTime()
    ) {
      bySource.set(source, job);
    }
  }
  return bySource;
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
  return { text: "Ready to sync", className: "text-zinc-400" };
}
