"use client";

import { Clock, History, Loader2 } from "lucide-react";

import { SyncActiveJobCard } from "./SyncActiveJobCard";
import { SyncHistoryCard } from "./SyncHistoryCard";
import { apiDateToEpochMs } from "@/lib/datetime";
import type { IntegrationId } from "@/lib/integrations";
import type { IntegrationSyncJobStatusResponse } from "@/lib/types";

interface SyncJobsPanelProps {
  jobs: IntegrationSyncJobStatusResponse[];
  onRetrySource?: (source: IntegrationId) => void;
  onCancelJob?: (jobId: string) => void;
  compact?: boolean;
  embedded?: boolean;
  sourceFilter?: IntegrationId;
  maxHistory?: number;
}

export function SyncJobsPanel({
  jobs,
  onRetrySource,
  onCancelJob,
  compact = false,
  embedded = false,
  sourceFilter,
  maxHistory,
}: SyncJobsPanelProps) {
  const filtered = sourceFilter
    ? jobs.filter((job) =>
        sourceFilter === "github"
          ? job.source === "github" || job.source === "github_repo"
          : job.source === sourceFilter,
      )
    : jobs;
  const sorted = [...filtered].sort(
    (a, b) => apiDateToEpochMs(b.created_at) - apiDateToEpochMs(a.created_at),
  );
  const historyLimit = maxHistory ?? (compact || embedded ? 8 : sorted.length);

  const activeJobs = sorted.filter(
    (job) => job.status === "queued" || job.status === "running",
  );
  const pastJobs = sorted.filter(
    (job) =>
      job.status === "completed" || job.status === "failed" || job.status === "cancelled",
  );
  const visiblePastJobs = pastJobs.slice(0, historyLimit);
  const hiddenPastCount = Math.max(0, pastJobs.length - visiblePastJobs.length);

  if (sorted.length === 0) {
    return (
      <section
        className={
          embedded
            ? "rounded-lg border border-dashed border-zinc-800/80 px-3 py-4 text-center"
            : compact
              ? "rounded-lg border border-dashed border-zinc-800/80 px-3 py-4 text-center text-xs text-zinc-500"
              : "rounded-2xl border border-dashed border-zinc-800 bg-zinc-950/30 px-5 py-8 text-center"
        }
      >
        <History
          className={`mx-auto text-zinc-600 ${embedded ? "h-4 w-4" : "h-5 w-5"}`}
          aria-hidden
        />
        <p
          className={`mt-2 text-zinc-500 ${
            embedded ? "text-[10px]" : compact ? "text-xs" : "text-sm"
          }`}
        >
          No sync runs yet.
          {!embedded && !compact && " Connect a source and trigger a sync."}
        </p>
      </section>
    );
  }

  const sectionGap = embedded ? "space-y-3" : compact ? "space-y-4" : "space-y-6";

  return (
    <section className={sectionGap} aria-live="polite">
      <div>
        {!compact && !embedded && (
          <header className="mb-3 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                In progress
              </p>
              <h3 className="mt-0.5 text-sm font-semibold text-zinc-100">
                Active syncs
              </h3>
            </div>
            {activeJobs.length > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-500/25 bg-sky-500/10 px-2.5 py-1 text-[11px] font-medium text-sky-400">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                {activeJobs.length} running
              </span>
            )}
          </header>
        )}

        {(compact || embedded) && activeJobs.length > 0 && (
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-zinc-500">
            Running
          </p>
        )}

        {activeJobs.length === 0 ? (
          !compact &&
          !embedded && (
            <p className="rounded-xl border border-zinc-800/60 bg-zinc-950/40 px-4 py-3 text-xs text-zinc-500">
              No syncs in progress.
            </p>
          )
        ) : (
          <ul className="space-y-2">
            {activeJobs.map((job) => (
              <SyncActiveJobCard
                key={job.job_id}
                job={job}
                onCancel={onCancelJob}
                compact={compact}
                embedded={embedded}
              />
            ))}
          </ul>
        )}
      </div>

      {visiblePastJobs.length > 0 && (
        <div>
          <header
            className={`flex items-center justify-between gap-2 ${
              embedded ? "mb-1.5" : compact ? "mb-2" : "mb-3"
            }`}
          >
            <div className="flex items-center gap-2">
              {!compact && !embedded && (
                <Clock className="h-3.5 w-3.5 text-zinc-500" aria-hidden />
              )}
              <div>
                {(compact || embedded) && (
                  <h3 className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
                    History
                  </h3>
                )}
                {!compact && !embedded && (
                  <>
                    <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                      History
                    </p>
                    <h3 className="text-sm font-semibold text-zinc-100">Past sync runs</h3>
                  </>
                )}
              </div>
            </div>
            <span className="text-[10px] tabular-nums text-zinc-600">
              {visiblePastJobs.length}
              {hiddenPastCount > 0 ? ` of ${pastJobs.length}` : ""}
            </span>
          </header>

          <ul
            className={`space-y-2 overflow-y-auto pr-0.5 ${
              embedded ? "max-h-44" : compact ? "max-h-56" : "max-h-[32rem]"
            }`}
          >
            {visiblePastJobs.map((job) => (
              <SyncHistoryCard
                key={job.job_id}
                job={job}
                onRetry={onRetrySource}
                compact={compact}
                embedded={embedded}
              />
            ))}
          </ul>

          {hiddenPastCount > 0 && (
            <p className="mt-2 text-center text-[10px] text-zinc-600">
              +{hiddenPastCount} older run{hiddenPastCount === 1 ? "" : "s"} not shown
            </p>
          )}
        </div>
      )}
    </section>
  );
}
