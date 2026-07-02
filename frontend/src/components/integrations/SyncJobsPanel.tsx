"use client";

import { CheckCircle2, Clock, Loader2, RefreshCw, XCircle } from "lucide-react";

import type { IntegrationSyncJobStatusResponse } from "@/lib/types";
import { INTEGRATION_CATALOG, type IntegrationId } from "@/lib/integrations";
import { formatSyncJobError } from "@/lib/sync-errors";

const PHASE_LABELS: Record<string, string> = {
  fetching: "Fetching data",
  building_graph: "Building graph",
  cognifying: "Cognee cognify",
  finalizing: "Finishing",
};

function sourceLabel(source: string): string {
  return (
    INTEGRATION_CATALOG.find((app) => app.id === source)?.name ??
    source.charAt(0).toUpperCase() + source.slice(1)
  );
}

function statusStyles(status: IntegrationSyncJobStatusResponse["status"]) {
  switch (status) {
    case "completed":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-400";
    case "failed":
      return "border-red-500/30 bg-red-500/10 text-red-400";
    case "running":
      return "border-sky-500/30 bg-sky-500/10 text-sky-400";
    default:
      return "border-zinc-700 bg-zinc-900/60 text-zinc-400";
  }
}

function formatWhen(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function JobRow({
  job,
  onRetry,
  compact = false,
  embedded = false,
}: {
  job: IntegrationSyncJobStatusResponse;
  onRetry?: (source: IntegrationId) => void;
  compact?: boolean;
  embedded?: boolean;
}) {
  const isActive = job.status === "queued" || job.status === "running";
  const phaseLabel = job.phase ? PHASE_LABELS[job.phase] ?? job.phase : null;

  return (
    <li
      className={
        embedded
          ? "rounded-lg border border-zinc-800/80 bg-zinc-950/40 px-3 py-2"
          : "rounded-xl border border-zinc-800 bg-zinc-950/60 px-4 py-3"
      }
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {!embedded && (
              <p className="text-sm font-medium text-zinc-100">
                {sourceLabel(job.source)}
              </p>
            )}
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${statusStyles(job.status)}`}
            >
              {job.status === "completed" && <CheckCircle2 className="h-3 w-3" />}
              {job.status === "failed" && <XCircle className="h-3 w-3" />}
              {isActive && <Loader2 className="h-3 w-3 animate-spin" />}
              {job.status}
            </span>
            <span className="text-[10px] text-zinc-600">
              {formatWhen(job.created_at)}
            </span>
          </div>

          <p className={`text-zinc-400 ${embedded ? "mt-0.5 text-[10px]" : "mt-1 text-xs"}`}>
            {job.progress_message ?? (isActive ? "Starting…" : "No progress details")}
          </p>

          {phaseLabel && isActive && (
            <p className="mt-1 text-[11px] text-zinc-500">Phase: {phaseLabel}</p>
          )}

                  {job.status === "completed" && job.result && (
                    <div className="mt-1.5 space-y-1">
                      <p className="text-[11px] text-emerald-400/80">
                        {job.result.graph_nodes_created} nodes ingested
                        {job.result.items_skipped
                          ? ` · ${job.result.items_skipped} already in Cognee`
                          : ""}
                        {job.result.items_new
                          ? ` · ${job.result.items_new} new`
                          : ""}
                        {job.result.items_updated
                          ? ` · ${job.result.items_updated} updated`
                          : ""}
                        {job.completed_at && (
                          <span className="text-zinc-500">
                            {" "}
                            · finished {formatWhen(job.completed_at)}
                          </span>
                        )}
                      </p>
                      {job.result.already_synced_note && (
                        <p className="text-[11px] text-zinc-500">
                          {job.result.already_synced_note}
                        </p>
                      )}
                      {!compact && job.result.narrative_preview && (
                        <p className="text-[11px] leading-relaxed text-zinc-500">
                          {job.result.narrative_preview}
                        </p>
                      )}
                    </div>
                  )}

          {job.status === "failed" && job.error && (
            <div className="mt-1.5">
              <p className="text-[11px] text-red-400">
                {formatSyncJobError(job.error)}
              </p>
              {onRetry && (
                <button
                  type="button"
                  onClick={() => onRetry(job.source as IntegrationId)}
                  className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-sky-400 hover:text-sky-300"
                >
                  <RefreshCw className="h-3 w-3" />
                  Retry {sourceLabel(job.source)}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </li>
  );
}

interface SyncJobsPanelProps {
  jobs: IntegrationSyncJobStatusResponse[];
  onRetrySource?: (source: IntegrationId) => void;
  compact?: boolean;
  embedded?: boolean;
  sourceFilter?: IntegrationId;
  maxHistory?: number;
}

export function SyncJobsPanel({
  jobs,
  onRetrySource,
  compact = false,
  embedded = false,
  sourceFilter,
  maxHistory,
}: SyncJobsPanelProps) {
  const filtered = sourceFilter
    ? jobs.filter((job) => job.source === sourceFilter)
    : jobs;
  const sorted = [...filtered].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
  const historyLimit = maxHistory ?? (compact || embedded ? 8 : sorted.length);

  const activeJobs = sorted.filter(
    (job) => job.status === "queued" || job.status === "running",
  );
  const pastJobs = sorted.filter(
    (job) => job.status === "completed" || job.status === "failed",
  );

  if (sorted.length === 0) {
    return (
      <section
        className={
          embedded
            ? "px-1 py-1 text-[10px] text-zinc-500"
            : compact
              ? "rounded-lg border border-dashed border-zinc-800/80 px-3 py-2 text-xs text-zinc-500"
              : "rounded-2xl border border-dashed border-zinc-800 bg-zinc-950/30 p-5"
        }
      >
        {embedded ? (
          <p>No sync runs yet.</p>
        ) : compact ? (
          <p>No sync runs yet.</p>
        ) : (
          <p className="text-sm text-zinc-500">
            No sync runs yet. Connect a source and trigger a sync.
          </p>
        )}
      </section>
    );
  }

  return (
    <section
      className={embedded ? "space-y-2" : compact ? "space-y-4" : "space-y-6"}
      aria-live="polite"
    >
      <div>
        {!compact && !embedded && (
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                In progress
              </p>
              <h3 className="mt-1 text-sm font-semibold text-zinc-100">
                Current sync jobs
              </h3>
            </div>
            {activeJobs.length > 0 && (
              <span className="inline-flex items-center gap-1.5 text-xs text-sky-400">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                {activeJobs.length} running
              </span>
            )}
          </div>
        )}

        {(compact || embedded) && activeJobs.length > 0 && (
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-zinc-500">
            Running
          </p>
        )}

        {activeJobs.length === 0 ? (
          !compact && !embedded && (
            <p className="rounded-xl border border-zinc-800/60 bg-zinc-950/40 px-4 py-3 text-xs text-zinc-500">
              No syncs in progress.
            </p>
          )
        ) : (
          <ul className="space-y-2">
            {activeJobs.map((job) => (
              <JobRow
                key={job.job_id}
                job={job}
                compact={compact}
                embedded={embedded}
              />
            ))}
          </ul>
        )}
      </div>

      {pastJobs.length > 0 && (
        <div>
          <div className={`flex items-center gap-2 ${embedded ? "mb-1.5" : compact ? "mb-2" : "mb-3"}`}>
            {!compact && !embedded && <Clock className="h-3.5 w-3.5 text-zinc-500" />}
            <div>
              {!compact && !embedded && (
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  History
                </p>
              )}
              {(compact || embedded) && (
                <h3 className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
                  {embedded ? "History" : "Recent"}
                </h3>
              )}
              {!compact && !embedded && (
                <h3 className="text-sm font-semibold text-zinc-100">Past sync runs</h3>
              )}
            </div>
          </div>

          <ul
            className={`space-y-2 overflow-y-auto pr-1 ${
              embedded ? "max-h-36" : compact ? "max-h-48" : "max-h-[28rem]"
            }`}
          >
            {pastJobs.slice(0, historyLimit).map((job) => (
              <JobRow
                key={job.job_id}
                job={job}
                onRetry={onRetrySource}
                compact={compact}
                embedded={embedded}
              />
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
