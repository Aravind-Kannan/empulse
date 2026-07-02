"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  ChevronDown,
  Loader2,
  RefreshCw,
  Settings2,
} from "lucide-react";

import type { IntegrationDefinition, IntegrationStatus } from "@/lib/integrations";
import { syncStatusLabel } from "@/lib/sync-jobs";
import type { IntegrationSyncJobStatusResponse } from "@/lib/types";

import { IntegrationLogo } from "./IntegrationLogos";
import { SyncJobsPanel } from "./SyncJobsPanel";

const STATUS_STYLES: Record<
  IntegrationStatus,
  { label: string; className: string }
> = {
  connected: {
    label: "Connected",
    className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  },
  available: {
    label: "Not connected",
    className: "border-zinc-700/80 bg-zinc-900/40 text-zinc-500",
  },
  disconnected: {
    label: "Disconnected",
    className: "border-zinc-600/50 bg-zinc-800/40 text-zinc-400",
  },
  syncing: {
    label: "Syncing",
    className: "border-sky-500/30 bg-sky-500/10 text-sky-400",
  },
  pending: {
    label: "Pending verification",
    className: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  },
};

interface IntegrationRowProps {
  app: IntegrationDefinition;
  status: IntegrationStatus;
  connected: boolean;
  syncing: boolean;
  latestJob: IntegrationSyncJobStatusResponse | null;
  sourceJobs: IntegrationSyncJobStatusResponse[];
  onConfigure: () => void;
  onSync: () => void;
}

export function IntegrationRow({
  app,
  status,
  connected,
  syncing,
  latestJob,
  sourceJobs,
  onConfigure,
  onSync,
}: IntegrationRowProps) {
  const badge = STATUS_STYLES[status];
  const isConnected = status === "connected" || status === "syncing";
  const syncLabel = syncStatusLabel(latestJob, syncing, connected);
  const isActive =
    syncing || latestJob?.status === "running" || latestJob?.status === "queued";
  const showHistory = connected || sourceJobs.length > 0;
  const [historyOpen, setHistoryOpen] = useState(isActive);

  useEffect(() => {
    if (isActive) {
      setHistoryOpen(true);
    }
  }, [isActive]);

  return (
    <li className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950/40">
      <div className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:gap-4 sm:px-5">
        <div className="flex min-w-0 flex-1 items-start gap-3 sm:items-center">
          <div
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${app.accentBg}`}
          >
            <IntegrationLogo
              id={app.id}
              className={`h-5 w-5 ${app.iconClassName}`}
            />
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-semibold text-zinc-100">{app.name}</h3>
              <span
                className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${badge.className}`}
              >
                {status === "syncing" && (
                  <Loader2 className="h-2.5 w-2.5 animate-spin" />
                )}
                {badge.label}
              </span>
            </div>

            <p className="mt-0.5 line-clamp-1 text-xs text-zinc-500">
              {app.description}
            </p>
            <p className="mt-0.5 line-clamp-1 text-[11px] text-zinc-600">
              {app.syncsToCognee}
            </p>

            {connected && (
              <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px]">
                <span className={syncLabel.className}>{syncLabel.text}</span>
                {isActive && latestJob?.progress_message && (
                  <span className="truncate text-sky-400/90">
                    · {latestJob.progress_message}
                  </span>
                )}
                {!isActive &&
                  latestJob?.status === "completed" &&
                  latestJob.completed_at && (
                    <span className="flex items-center gap-1 text-zinc-500">
                      <CheckCircle2 className="h-3 w-3 text-emerald-500/80" />
                      {new Date(latestJob.completed_at).toLocaleString()}
                      {latestJob.result && (
                        <span className="text-zinc-600">
                          · {latestJob.result.graph_nodes_created} ingested
                        </span>
                      )}
                    </span>
                  )}
              </div>
            )}
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">
          {showHistory && (
            <button
              type="button"
              onClick={() => setHistoryOpen((open) => !open)}
              className="inline-flex items-center gap-1 rounded-lg border border-zinc-800 bg-zinc-900/60 px-2.5 py-2 text-[11px] font-medium text-zinc-400 transition hover:border-zinc-700 hover:text-zinc-200"
              aria-expanded={historyOpen}
            >
              Runs
              <span className="rounded-full bg-zinc-800 px-1.5 py-0.5 text-[10px] tabular-nums text-zinc-500">
                {sourceJobs.length}
              </span>
              <ChevronDown
                className={`h-3.5 w-3.5 transition-transform ${historyOpen ? "rotate-180" : ""}`}
              />
            </button>
          )}

          {isConnected && (
            <button
              type="button"
              disabled={!connected || isActive}
              onClick={onSync}
              className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs font-medium text-zinc-100 transition hover:border-zinc-600 hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {isActive ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Syncing…
                </>
              ) : (
                <>
                  <RefreshCw className="h-3.5 w-3.5" />
                  Sync
                </>
              )}
            </button>
          )}

          <button
            type="button"
            onClick={onConfigure}
            className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs font-medium text-zinc-100 transition hover:border-zinc-600 hover:bg-zinc-800"
          >
            {isConnected ? (
              <>
                <Settings2 className="h-3.5 w-3.5" />
                Configure
              </>
            ) : (
              "Connect"
            )}
          </button>
        </div>
      </div>

      {showHistory && historyOpen && (
        <div className="border-t border-zinc-800/80 bg-zinc-950/60 px-4 py-3 sm:px-5">
          <SyncJobsPanel
            jobs={sourceJobs}
            embedded
            compact
            maxHistory={8}
            onRetrySource={() => onSync()}
          />
        </div>
      )}
    </li>
  );
}
