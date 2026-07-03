import { apiDateToEpochMs } from "@/lib/datetime";
import type { IntegrationSyncJobStatusResponse } from "@/lib/types";

/** Human-readable wall-clock duration (e.g. 2m 14s). */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  if (total < 60) {
    return `${total}s`;
  }
  const minutes = Math.floor(total / 60);
  const remSeconds = total % 60;
  if (minutes < 60) {
    return remSeconds > 0 ? `${minutes}m ${remSeconds}s` : `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  const remMinutes = minutes % 60;
  return remMinutes > 0 ? `${hours}h ${remMinutes}m` : `${hours}h`;
}

export function isSyncJobActive(
  status: IntegrationSyncJobStatusResponse["status"],
): boolean {
  return status === "queued" || status === "running";
}

/** Elapsed seconds for active jobs; total duration for finished jobs. */
export function syncJobElapsedSeconds(
  job: Pick<
    IntegrationSyncJobStatusResponse,
    "created_at" | "completed_at" | "duration_seconds" | "status"
  >,
  nowMs = Date.now(),
): number | null {
  if (job.duration_seconds != null && !isSyncJobActive(job.status)) {
    return job.duration_seconds;
  }
  const startedMs = apiDateToEpochMs(job.created_at);
  if (!startedMs) {
    return null;
  }
  if (job.completed_at) {
    const endedMs = apiDateToEpochMs(job.completed_at);
    if (endedMs) {
      return Math.max(0, (endedMs - startedMs) / 1000);
    }
  }
  if (isSyncJobActive(job.status)) {
    return Math.max(0, (nowMs - startedMs) / 1000);
  }
  return null;
}

export function syncDurationLabel(
  job: Pick<
    IntegrationSyncJobStatusResponse,
    "created_at" | "completed_at" | "duration_seconds" | "status"
  >,
  nowMs = Date.now(),
): string | null {
  const seconds = syncJobElapsedSeconds(job, nowMs);
  if (seconds == null) {
    return null;
  }
  const formatted = formatDuration(seconds);
  return isSyncJobActive(job.status) ? `${formatted} elapsed` : `took ${formatted}`;
}
