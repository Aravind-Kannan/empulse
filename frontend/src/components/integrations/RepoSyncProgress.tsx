"use client";

import type { IntegrationSyncJobStatusResponse } from "@/lib/types";

import { SyncDuration } from "./SyncDuration";

export interface RepoSyncProgressStats {
  branches_total?: number;
  branches_completed?: number;
  current_branch?: string;
  files_total?: number;
  files_completed?: number;
}

export function parseRepoSyncStats(
  job: IntegrationSyncJobStatusResponse | null | undefined,
): RepoSyncProgressStats | null {
  if (!job?.progress_stats) return null;
  return job.progress_stats as RepoSyncProgressStats;
}

interface RepoSyncProgressProps {
  job: IntegrationSyncJobStatusResponse | null | undefined;
  compact?: boolean;
}

export function RepoSyncProgress({ job, compact = false }: RepoSyncProgressProps) {
  const stats = parseRepoSyncStats(job);
  if (!stats) {
    if (job?.progress_message) {
      return (
        <div className={compact ? "space-y-0.5" : "space-y-1"}>
          {job && <SyncDuration job={job} className={`text-zinc-500 ${compact ? "text-[10px]" : "text-[11px]"}`} />}
          <p className={`text-sky-400/90 ${compact ? "text-[10px]" : "text-xs"}`}>
            {job.progress_message}
          </p>
        </div>
      );
    }
    return job ? (
      <SyncDuration job={job} className={`text-zinc-500 ${compact ? "text-[10px]" : "text-[11px]"}`} />
    ) : null;
  }

  const filesTotal = stats.files_total ?? 0;
  const filesCompleted = stats.files_completed ?? 0;
  const branchesTotal = stats.branches_total ?? 0;
  const branchesCompleted = stats.branches_completed ?? 0;
  const currentBranch = stats.current_branch ?? "";
  const filePct = filesTotal > 0 ? Math.round((filesCompleted / filesTotal) * 100) : 0;

  return (
    <div className={compact ? "mt-1 space-y-1" : "mt-2 space-y-2"}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-zinc-500">
        {job && (
          <SyncDuration job={job} className="text-sky-400/70" />
        )}
        {branchesTotal > 0 && (
          <span>
            Branches{" "}
            <span className="tabular-nums text-zinc-400">
              {Math.min(branchesCompleted + (filesCompleted < filesTotal ? 1 : 0), branchesTotal)}
              /{branchesTotal}
            </span>
            {currentBranch && filesCompleted < filesTotal && (
              <span className="text-sky-400/80"> · {currentBranch}</span>
            )}
          </span>
        )}
        {filesTotal > 0 && (
          <span>
            Files{" "}
            <span className="tabular-nums text-zinc-300">
              {filesCompleted}/{filesTotal}
            </span>
          </span>
        )}
      </div>

      {filesTotal > 0 && (
        <div className="h-1 overflow-hidden rounded-full bg-zinc-800">
          <div
            className="h-full rounded-full bg-sky-500 transition-all duration-300"
            style={{ width: `${filePct}%` }}
          />
        </div>
      )}

      {job?.progress_message && (
        <p className={`truncate text-sky-400/80 ${compact ? "text-[10px]" : "text-[11px]"}`}>
          {job.progress_message}
        </p>
      )}
    </div>
  );
}
