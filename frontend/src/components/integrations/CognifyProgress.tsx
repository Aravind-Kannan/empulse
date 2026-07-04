"use client";

import { useEffect, useState } from "react";

import { apiDateToEpochMs } from "@/lib/datetime";
import type { IntegrationSyncJobStatusResponse } from "@/lib/types";

export interface CognifyProgressStats {
  cognify_phase?: string;
  cognify_started_at?: string;
  cognify_elapsed_sec?: number;
  threads_fetched?: number;
  issues_fetched?: number;
  pages_fetched?: number;
  prs_fetched?: number;
  nodes_to_index?: number;
  nodes_new?: number;
  nodes_skipped?: number;
  narrative_chars?: number;
  channels_scanned?: number;
}

export function parseCognifyStats(
  job: IntegrationSyncJobStatusResponse | null | undefined,
): CognifyProgressStats | null {
  if (!job?.progress_stats) return null;
  return job.progress_stats as CognifyProgressStats;
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

function useCognifyElapsed(
  stats: CognifyProgressStats | null,
  isActive: boolean,
): number {
  const startedAt = stats?.cognify_started_at;
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!isActive || !startedAt) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [isActive, startedAt]);

  if (startedAt) {
    const startedMs = apiDateToEpochMs(startedAt);
    if (startedMs) {
      return Math.max(0, Math.floor((now - startedMs) / 1000));
    }
  }
  return stats?.cognify_elapsed_sec ?? 0;
}

interface CognifyProgressProps {
  job: IntegrationSyncJobStatusResponse | null | undefined;
  compact?: boolean;
}

export function CognifyProgress({ job, compact = false }: CognifyProgressProps) {
  const stats = parseCognifyStats(job);
  const isActive = job?.status === "running" && job.phase === "cognifying";
  const elapsed = useCognifyElapsed(stats, isActive);

  if (!isActive) return null;

  const detailParts: string[] = [];
  if (stats?.threads_fetched) {
    detailParts.push(`${stats.threads_fetched} threads`);
  }
  if (stats?.issues_fetched) {
    detailParts.push(`${stats.issues_fetched} issues`);
  }
  if (stats?.pages_fetched) {
    detailParts.push(`${stats.pages_fetched} pages`);
  }
  if (stats?.nodes_to_index != null) {
    detailParts.push(`${stats.nodes_to_index} nodes indexed`);
  }
  if (stats?.nodes_new) {
    detailParts.push(`${stats.nodes_new} new`);
  }

  return (
    <div className={compact ? "mt-1 space-y-1" : "mt-2 space-y-2"}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-zinc-500">
        <span className="text-sky-400/90">
          LLM enrichment · {formatElapsed(elapsed)}
        </span>
        {detailParts.map((part) => (
          <span key={part} className="tabular-nums text-zinc-400">
            {part}
          </span>
        ))}
      </div>

      <div className="h-1 overflow-hidden rounded-full bg-zinc-800">
        <div className="h-full w-1/3 animate-pulse rounded-full bg-sky-500/80" />
      </div>

      <p className={`text-zinc-500 ${compact ? "text-[10px]" : "text-[11px]"}`}>
        This step can take several minutes for large sources. Elapsed time updates
        while it runs.
      </p>

      {job?.progress_message && (
        <p className={`truncate text-sky-400/80 ${compact ? "text-[10px]" : "text-[11px]"}`}>
          {job.progress_message}
        </p>
      )}
    </div>
  );
}
