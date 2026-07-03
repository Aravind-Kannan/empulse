"use client";

import { Loader2, Square } from "lucide-react";

import { CognifyProgress } from "./CognifyProgress";
import { RepoSyncProgress } from "./RepoSyncProgress";
import { SyncDuration } from "./SyncDuration";
import { IntegrationLogo } from "./IntegrationLogos";
import {
  jobIntegrationId,
  syncJobKindLabel,
  syncJobShortTitle,
} from "@/lib/sync-jobs";
import type { IntegrationSyncJobStatusResponse } from "@/lib/types";

const PHASE_LABELS: Record<string, string> = {
  fetching: "Fetching",
  building_graph: "Building graph",
  cognifying: "Cognee cognify",
  finalizing: "Finishing",
};

interface SyncActiveJobCardProps {
  job: IntegrationSyncJobStatusResponse;
  compact?: boolean;
  embedded?: boolean;
  onCancel?: (jobId: string) => void;
}

export function SyncActiveJobCard({
  job,
  compact = false,
  embedded = false,
  onCancel,
}: SyncActiveJobCardProps) {
  const isQueueWaiting =
    job.status === "queued" &&
    (job.progress_message?.toLowerCase().includes("waiting for another") ?? false);
  const integrationId = jobIntegrationId(job);
  const kindLabel = syncJobKindLabel(job);
  const phaseLabel = job.phase ? PHASE_LABELS[job.phase] ?? job.phase : null;
  const dense = compact || embedded;

  return (
    <li
      className={`border-l-2 border-l-sky-500/80 ${
        dense
          ? "rounded-lg border border-sky-500/20 bg-sky-500/[0.04] px-2.5 py-2"
          : "rounded-xl border border-sky-500/25 bg-gradient-to-br from-sky-500/[0.07] to-zinc-950/60 px-3 py-3 sm:px-4"
      }`}
    >
      <div className="flex items-start gap-2.5">
        {integrationId && (
          <div
            className={`mt-0.5 flex shrink-0 items-center justify-center rounded-md border border-sky-500/20 bg-sky-500/10 ${
              dense ? "h-7 w-7" : "h-8 w-8"
            }`}
          >
            <IntegrationLogo
              id={integrationId}
              className={dense ? "h-3.5 w-3.5" : "h-4 w-4"}
            />
          </div>
        )}

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p
                className={`truncate font-medium text-zinc-100 ${
                  dense ? "text-[11px]" : "text-sm"
                }`}
              >
                {syncJobShortTitle(job)}
              </p>
              {kindLabel && (
                <p className="text-[10px] text-zinc-500">{kindLabel} sync</p>
              )}
            </div>

            <div className="flex shrink-0 items-center gap-2">
              <SyncDuration
                job={job}
                className={`font-medium text-sky-400/90 ${
                  dense ? "text-[10px]" : "text-[11px]"
                }`}
              />
              {onCancel && (
                <button
                  type="button"
                  onClick={() => onCancel(job.job_id)}
                  className="inline-flex items-center gap-1 rounded-md border border-zinc-700/80 bg-zinc-900/80 px-2 py-1 text-[10px] font-medium text-zinc-300 hover:border-red-500/40 hover:text-red-300"
                  title="Stop sync"
                >
                  <Square className="h-3 w-3 fill-current" />
                  Stop
                </button>
              )}
            </div>
          </div>

          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-1 rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-sky-400 ${
                isQueueWaiting ? "border-amber-500/30 bg-amber-500/10 text-amber-400" : ""
              }`}
            >
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
              {isQueueWaiting ? "Waiting" : job.status}
            </span>
            {phaseLabel && job.job_kind !== "github_repo" && (
              <span className="text-[10px] text-zinc-500">{phaseLabel}</span>
            )}
          </div>

          <p
            className={`mt-1.5 text-zinc-400 ${
              dense ? "text-[10px] leading-snug" : "text-xs"
            }`}
          >
            {job.progress_message ?? "Starting…"}
          </p>

          {isQueueWaiting && (
            <p
              className={`mt-1 text-amber-400/90 ${
                dense ? "text-[10px]" : "text-[11px]"
              }`}
            >
              One sync at a time — starts when current job finishes.
            </p>
          )}

          {job.job_kind === "github_repo" && (
            <RepoSyncProgress job={job} compact={dense} />
          )}

          {job.phase === "cognifying" && (
            <CognifyProgress job={job} compact={dense} />
          )}
        </div>
      </div>
    </li>
  );
}
