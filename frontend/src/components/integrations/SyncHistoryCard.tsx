"use client";

import {
  Ban,
  CheckCircle2,
  RefreshCw,
  XCircle,
} from "lucide-react";

import { SyncDuration } from "./SyncDuration";
import { IntegrationLogo } from "./IntegrationLogos";
import { formatLocalDateTime } from "@/lib/datetime";
import { formatSyncJobError } from "@/lib/sync-errors";
import {
  jobIntegrationId,
  syncJobKindLabel,
  syncJobShortTitle,
} from "@/lib/sync-jobs";
import type { IntegrationId } from "@/lib/integrations";
import type { IntegrationSyncJobStatusResponse } from "@/lib/types";

const STATUS_UI = {
  completed: {
    label: "Completed",
    accent: "border-l-emerald-500/80",
    pill: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400",
    Icon: CheckCircle2,
  },
  failed: {
    label: "Failed",
    accent: "border-l-red-500/80",
    pill: "border-red-500/25 bg-red-500/10 text-red-400",
    Icon: XCircle,
  },
  cancelled: {
    label: "Cancelled",
    accent: "border-l-zinc-600",
    pill: "border-zinc-600/40 bg-zinc-800/50 text-zinc-400",
    Icon: Ban,
  },
} as const;

function StatChip({
  value,
  label,
  compact,
}: {
  value: number;
  label: string;
  compact?: boolean;
}) {
  if (value <= 0) return null;
  return (
    <div
      className={`rounded-md border border-zinc-800/90 bg-zinc-900/70 ${
        compact ? "px-2 py-1" : "px-2.5 py-1.5"
      }`}
    >
      <p
        className={`font-semibold tabular-nums text-zinc-100 ${
          compact ? "text-[11px]" : "text-xs"
        }`}
      >
        {value.toLocaleString()}
      </p>
      <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
        {label}
      </p>
    </div>
  );
}

interface SyncHistoryCardProps {
  job: IntegrationSyncJobStatusResponse;
  compact?: boolean;
  embedded?: boolean;
  onRetry?: (source: IntegrationId) => void;
}

export function SyncHistoryCard({
  job,
  compact = false,
  embedded = false,
  onRetry,
}: SyncHistoryCardProps) {
  const status = job.status as keyof typeof STATUS_UI;
  const ui = STATUS_UI[status];
  if (!ui) return null;

  const integrationId = jobIntegrationId(job);
  const kindLabel = syncJobKindLabel(job);
  const { Icon } = ui;
  const result = job.result;
  const dense = compact || embedded;

  return (
    <li
      className={`border-l-2 ${ui.accent} ${
        dense
          ? "rounded-lg border border-zinc-800/80 bg-zinc-950/50 px-2.5 py-2"
          : "rounded-xl border border-zinc-800/90 bg-zinc-950/60 px-3 py-3 sm:px-4"
      }`}
    >
      <div className="flex items-start gap-2.5">
        {integrationId && (
          <div
            className={`mt-0.5 flex shrink-0 items-center justify-center rounded-md border border-zinc-800 bg-zinc-900/80 ${
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
            <span
              className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${ui.pill}`}
            >
              <Icon className="h-3 w-3" aria-hidden />
              {ui.label}
            </span>
          </div>

          <div
            className={`mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-zinc-500 ${
              dense ? "text-[10px]" : "text-[11px]"
            }`}
          >
            <time dateTime={job.created_at}>{formatLocalDateTime(job.created_at)}</time>
            <span className="text-zinc-700">·</span>
            <SyncDuration job={job} className="text-zinc-500" />
          </div>

          {status === "completed" && result && (
            <div className={`flex flex-wrap gap-1.5 ${dense ? "mt-1.5" : "mt-2.5"}`}>
              <StatChip
                value={result.graph_nodes_created ?? 0}
                label="ingested"
                compact={dense}
              />
              {(result.items_new ?? 0) > 0 && (
                <StatChip value={result.items_new ?? 0} label="new" compact={dense} />
              )}
              {(result.items_updated ?? 0) > 0 && (
                <StatChip
                  value={result.items_updated ?? 0}
                  label="updated"
                  compact={dense}
                />
              )}
              {(result.items_skipped ?? 0) > 0 && (
                <StatChip
                  value={result.items_skipped ?? 0}
                  label="skipped"
                  compact={dense}
                />
              )}
              {job.job_kind === "github_repo" && (result.files_discovered ?? 0) > 0 && (
                <StatChip
                  value={result.files_discovered ?? 0}
                  label="files"
                  compact={dense}
                />
              )}
            </div>
          )}

          {status === "completed" && result?.already_synced_note && !dense && (
            <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">
              {result.already_synced_note}
            </p>
          )}

          {status === "failed" && job.error && (
            <div className={dense ? "mt-1.5" : "mt-2"}>
              <p
                className={`leading-relaxed text-red-400/90 ${
                  dense ? "text-[10px] line-clamp-2" : "text-[11px]"
                }`}
              >
                {formatSyncJobError(job.error)}
              </p>
              {onRetry && integrationId && (
                <button
                  type="button"
                  onClick={() => onRetry(integrationId)}
                  className={`mt-2 inline-flex items-center gap-1 font-medium text-sky-400 hover:text-sky-300 ${
                    dense ? "text-[10px]" : "text-[11px]"
                  }`}
                >
                  <RefreshCw className="h-3 w-3" />
                  Retry sync
                </button>
              )}
            </div>
          )}

          {status === "cancelled" && (
            <p className={`mt-1 text-zinc-500 ${dense ? "text-[10px]" : "text-[11px]"}`}>
              Stopped before completion.
            </p>
          )}
        </div>
      </div>
    </li>
  );
}
