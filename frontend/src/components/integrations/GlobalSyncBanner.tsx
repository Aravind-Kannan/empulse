"use client";

import { useMemo } from "react";
import {
  CheckCircle2,
  Database,
  Loader2,
  RefreshCw,
  SkipForward,
  Sparkles,
} from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import {
  INTEGRATION_CATALOG,
  getConnectedIntegrationIds,
  isIntegrationConnected,
} from "@/lib/integrations";
import type { IntegrationSyncJobStatusResponse } from "@/lib/types";
import { latestJobPerSource } from "@/lib/sync-jobs";

import { SyncJobsPanel } from "./SyncJobsPanel";
import { GlobalSyncProgressBar } from "./GlobalSyncProgressBar";

function aggregateSyncStats(jobs: IntegrationSyncJobStatusResponse[]) {
  const completed = jobs.filter((job) => job.status === "completed" && job.result);
  let ingested = 0;
  let skipped = 0;

  for (const job of completed) {
    const result = job.result!;
    ingested += result.graph_nodes_created ?? 0;
    skipped += result.items_skipped ?? 0;
  }

  return { ingested, skipped, completedCount: completed.length };
}

function StatCard({
  label,
  value,
  hint,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon: typeof Database;
}) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 px-4 py-3">
      <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-zinc-500">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-zinc-100">{value}</p>
      {hint && <p className="mt-0.5 text-[11px] text-zinc-500">{hint}</p>}
    </div>
  );
}

/** Onboarding sync step — batch sync controls and job history. */
export function GlobalSyncBanner() {
  const {
    config,
    syncProgress,
    syncJobs,
    syncActionError,
    globalSyncPending,
    triggerGlobalSync,
    triggerSourceSync,
    cancelSyncJob,
  } = useIntegrations();

  const connectedCount = getConnectedIntegrationIds(config).length;
  const latestBySource = useMemo(() => latestJobPerSource(syncJobs), [syncJobs]);
  const stats = useMemo(() => aggregateSyncStats(syncJobs), [syncJobs]);
  const hasStartedSync = syncJobs.length > 0 || globalSyncPending;

  const isGlobalBusy = syncProgress.active || globalSyncPending;
  const connectedApps = INTEGRATION_CATALOG.filter((app) =>
    isIntegrationConnected(app.id, config),
  );
  const allConnectedDone =
    connectedCount > 0 &&
    connectedApps.every((app) => latestBySource.get(app.id)?.status === "completed");

  return (
    <section className="rounded-2xl border border-zinc-800 bg-gradient-to-b from-zinc-900/80 to-zinc-950/90 p-6">
      <div className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-3">
          <StatCard
            icon={Sparkles}
            label="Connected"
            value={connectedCount}
            hint={`of ${INTEGRATION_CATALOG.length} sources`}
          />
          <StatCard
            icon={Database}
            label="Synced"
            value={stats.ingested || "—"}
            hint={
              stats.completedCount
                ? `${stats.completedCount} source(s) finished`
                : "Run sync to import data"
            }
          />
          <StatCard
            icon={SkipForward}
            label="Skipped"
            value={stats.skipped || "—"}
            hint="Unchanged since last sync"
          />
        </div>

        <div className="flex flex-col gap-4 rounded-xl border border-zinc-800 bg-zinc-950/40 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-200">
              {hasStartedSync
                ? isGlobalBusy
                  ? "Sync in progress"
                  : allConnectedDone
                    ? "All connected sources synced"
                    : "Sync partially complete"
                : "Ready to sync your data"}
            </p>
            <p className="mt-1 max-w-xl text-xs text-zinc-500">
              {connectedCount === 0
                ? "Connect at least one integration on the previous step."
                : "Pull metadata, code, docs, and tickets into your workspace. Unchanged items are skipped automatically."}
            </p>
          </div>

          <button
            type="button"
            disabled={isGlobalBusy || connectedCount === 0}
            onClick={() => void triggerGlobalSync()}
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-zinc-100 px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isGlobalBusy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Syncing…
              </>
            ) : hasStartedSync ? (
              <>
                <RefreshCw className="h-4 w-4" />
                Re-sync all
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Start sync
              </>
            )}
          </button>
        </div>

        {allConnectedDone && !isGlobalBusy && (
          <p className="flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            Sync complete — you can enter the dashboard or re-sync anytime.
          </p>
        )}
      </div>

      {syncActionError && (
        <p className="mt-5 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {syncActionError}
        </p>
      )}

      {(syncProgress.active || globalSyncPending) && (
        <div className="mt-5 border-t border-zinc-800 pt-5">
          <GlobalSyncProgressBar
            progress={syncProgress}
            currentJob={syncProgress.currentJob}
          />
        </div>
      )}

      <div className="mt-5 border-t border-zinc-800 pt-5">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-zinc-500">
          Sync runs
        </p>
        <SyncJobsPanel
          jobs={syncJobs}
          onRetrySource={(source) => {
            void triggerSourceSync(source);
          }}
          onCancelJob={(jobId) => {
            void cancelSyncJob(jobId);
          }}
        />
      </div>
    </section>
  );
}
