"use client";

import type { SyncProgress } from "@/lib/sync-progress";
import {
  SYNC_PHASE_LABELS,
  formatSyncProgressLabel,
} from "@/lib/sync-progress";

import { CognifyProgress } from "./CognifyProgress";
import { RepoSyncProgress } from "./RepoSyncProgress";
import type { IntegrationSyncJobStatusResponse } from "@/lib/types";

interface GlobalSyncProgressBarProps {
  progress: SyncProgress;
  currentJob?: IntegrationSyncJobStatusResponse | null;
  compact?: boolean;
}

export function GlobalSyncProgressBar({
  progress,
  currentJob = null,
  compact = false,
}: GlobalSyncProgressBarProps) {
  const label = formatSyncProgressLabel(progress);
  const phaseLabel = progress.currentPhase
    ? SYNC_PHASE_LABELS[progress.currentPhase]
    : null;

  return (
    <div
      className={
        compact
          ? "space-y-2 rounded-xl border border-zinc-800 bg-zinc-950/40 px-4 py-3"
          : "space-y-3"
      }
    >
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-500">
        <span className="min-w-0 flex-1 truncate text-zinc-300">{label}</span>
        <span className="shrink-0 tabular-nums">
          {progress.total > 0
            ? `${progress.completedCount}/${progress.total} sources · ${progress.percent}%`
            : `${progress.percent}%`}
        </span>
      </div>

      <div
        className={`overflow-hidden rounded-full bg-zinc-800 ${compact ? "h-1.5" : "h-2"}`}
      >
        <div
          className="h-full rounded-full bg-gradient-to-r from-sky-500 to-emerald-400 transition-all duration-500 ease-out"
          style={{ width: `${progress.percent}%` }}
        />
      </div>

      {phaseLabel && progress.currentSource && (
        <p className="text-[11px] text-zinc-500">
          Active: {progress.currentSource} · {phaseLabel}
        </p>
      )}

      {currentJob?.job_kind === "github_repo" && (
        <RepoSyncProgress job={currentJob} compact />
      )}

      {currentJob?.phase === "cognifying" && (
        <CognifyProgress job={currentJob} compact />
      )}

      {progress.error && (
        <p className={`text-red-400 ${compact ? "text-xs" : "text-xs"}`}>
          {progress.error}
        </p>
      )}
    </div>
  );
}
