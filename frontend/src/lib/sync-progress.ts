import type { IntegrationSyncPhase, IntegrationSyncJobStatusResponse } from "@/lib/types";
import { apiDateToEpochMs } from "@/lib/datetime";
import { syncJobLabel } from "@/lib/sync-jobs";

export const SYNC_PHASE_LABELS: Record<IntegrationSyncPhase, string> = {
  fetching: "Fetching data",
  building_graph: "Processing data",
  cognifying: "Enriching data",
  finalizing: "Finishing",
};

const PHASE_PROGRESS_WEIGHT: Partial<Record<IntegrationSyncPhase, number>> = {
  fetching: 0.2,
  building_graph: 0.45,
  cognifying: 0.75,
  finalizing: 0.9,
};

export interface SyncProgress {
  active: boolean;
  currentSource: string | null;
  currentMessage: string | null;
  currentPhase: IntegrationSyncPhase | null;
  currentJob: IntegrationSyncJobStatusResponse | null;
  completed: string[];
  completedCount: number;
  total: number;
  percent: number;
  error: string | null;
}

function sortJobsOldestFirst(
  jobs: IntegrationSyncJobStatusResponse[],
): IntegrationSyncJobStatusResponse[] {
  return [...jobs].sort(
    (a, b) => apiDateToEpochMs(a.created_at) - apiDateToEpochMs(b.created_at),
  );
}

function pickCurrentJob(
  jobs: IntegrationSyncJobStatusResponse[],
): IntegrationSyncJobStatusResponse | null {
  const ordered = sortJobsOldestFirst(jobs);
  const running = ordered.filter((job) => job.status === "running");
  if (running.length > 0) return running[0];
  const queued = ordered.filter((job) => job.status === "queued");
  if (queued.length > 0) return queued[0];
  return null;
}

function scopeJobsForProgress(
  syncJobs: IntegrationSyncJobStatusResponse[],
  batchJobIds: string[] | null,
): IntegrationSyncJobStatusResponse[] {
  if (batchJobIds?.length) {
    const idSet = new Set(batchJobIds);
    return syncJobs.filter((job) => idSet.has(job.job_id));
  }

  const activeJobs = syncJobs.filter(
    (job) => job.status === "queued" || job.status === "running",
  );
  if (activeJobs.length === 0) return [];

  const anchorTime = Math.min(
    ...activeJobs.map((job) => apiDateToEpochMs(job.created_at)),
  );
  const windowMs = 5 * 60 * 1000;

  return syncJobs.filter((job) => {
    const created = apiDateToEpochMs(job.created_at);
    if (created < anchorTime - windowMs) return false;
    return (
      job.status === "queued" ||
      job.status === "running" ||
      job.status === "completed" ||
      job.status === "failed" ||
      job.status === "cancelled"
    );
  });
}

export function deriveSyncProgress(
  syncJobs: IntegrationSyncJobStatusResponse[],
  batchJobIds: string[] | null = null,
): SyncProgress {
  const scopedJobs = scopeJobsForProgress(syncJobs, batchJobIds);
  const activeJobs = scopedJobs.filter(
    (job) => job.status === "queued" || job.status === "running",
  );
  const completedJobs = scopedJobs.filter((job) => job.status === "completed");
  const failedJob = scopedJobs.find((job) => job.status === "failed");
  const currentJob = pickCurrentJob(scopedJobs);

  const total = scopedJobs.length;
  const completedCount = completedJobs.length;
  const completed = completedJobs.map((job) => syncJobLabel(job));

  let percent = 0;
  if (total > 0) {
    let fractional = completedCount;
    if (currentJob?.status === "running") {
      const phaseWeight =
        PHASE_PROGRESS_WEIGHT[currentJob.phase ?? "fetching"] ?? 0.15;
      fractional += phaseWeight;
    } else if (currentJob?.status === "queued") {
      fractional += 0.05;
    }
    percent = Math.min(100, Math.round((fractional / total) * 100));
  }

  return {
    active: activeJobs.length > 0,
    currentSource: currentJob ? syncJobLabel(currentJob) : null,
    currentMessage: currentJob?.progress_message ?? null,
    currentPhase: currentJob?.phase ?? null,
    currentJob,
    completed,
    completedCount,
    total,
    percent,
    error: failedJob?.error ?? null,
  };
}

export function formatSyncProgressLabel(progress: SyncProgress): string {
  if (progress.currentMessage) return progress.currentMessage;
  if (progress.currentSource && progress.currentPhase) {
    const phase = SYNC_PHASE_LABELS[progress.currentPhase] ?? progress.currentPhase;
    return `${progress.currentSource} — ${phase}…`;
  }
  if (progress.currentSource) {
    return `Syncing ${progress.currentSource}…`;
  }
  return "Preparing sync jobs…";
}

export function isBatchComplete(
  syncJobs: IntegrationSyncJobStatusResponse[],
  batchJobIds: string[],
): boolean {
  if (batchJobIds.length === 0) return true;
  const idSet = new Set(batchJobIds);
  const batchJobs = syncJobs.filter((job) => idSet.has(job.job_id));
  if (batchJobs.length < batchJobIds.length) return false;
  return batchJobs.every(
    (job) =>
      job.status === "completed" ||
      job.status === "failed" ||
      job.status === "cancelled",
  );
}
