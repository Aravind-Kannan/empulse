"use client";

import { useMemo } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  History,
  Loader2,
  Plug,
  RefreshCw,
  Sparkles,
} from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import { formatRelativeTime } from "@/lib/datetime";
import {
  INTEGRATION_CATALOG,
  getConnectedIntegrationIds,
  isIntegrationConnected,
} from "@/lib/integrations";
import {
  aggregateWorkspaceSyncStats,
  formatSyncChangeSummary,
  latestJobPerSource,
  sourcesNeedingAttention,
} from "@/lib/sync-jobs";

import { IntegrationStatCard } from "./IntegrationStatCard";
import { SyncJobsPanel } from "./SyncJobsPanel";
import { GlobalSyncProgressBar } from "./GlobalSyncProgressBar";

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
  const stats = useMemo(() => aggregateWorkspaceSyncStats(syncJobs), [syncJobs]);
  const attention = useMemo(
    () => sourcesNeedingAttention(config, syncJobs),
    [config, syncJobs],
  );
  const hasStartedSync = syncJobs.length > 0 || globalSyncPending;

  const isGlobalBusy = syncProgress.active || globalSyncPending;
  const connectedApps = INTEGRATION_CATALOG.filter((app) =>
    isIntegrationConnected(app.id, config),
  );
  const allConnectedDone =
    connectedCount > 0 &&
    connectedApps.every((app) => latestBySource.get(app.id)?.status === "completed");

  const lastSyncValue =
    stats.completedCount > 0
      ? formatSyncChangeSummary(
          stats.newItems,
          stats.updatedItems,
          stats.skippedItems,
        )
      : "—";

  const lastSyncHint =
    stats.lastCompletedAt != null
      ? `Last completed ${formatRelativeTime(stats.lastCompletedAt)}`
      : connectedCount > 0
        ? "Run sync to import data"
        : "Link a source first";

  return (
    <section className="rounded-2xl border border-zinc-800 bg-gradient-to-b from-zinc-900/80 to-zinc-950/90 p-6">
      <div className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-3">
          <IntegrationStatCard
            icon={Plug}
            label="Sources linked"
            value={connectedCount}
            hint="Add only the tools you use"
            className="border-zinc-800 bg-zinc-950/60"
          />
          <IntegrationStatCard
            icon={History}
            label="Last sync"
            value={lastSyncValue}
            hint={lastSyncHint}
            compactValue
            info="New and updated items imported into the knowledge graph. Unchanged items were already stored and not re-imported."
            className="border-zinc-800 bg-zinc-950/60"
          />
          <IntegrationStatCard
            icon={attention.count > 0 ? AlertTriangle : CheckCircle2}
            label="Needs attention"
            value={connectedCount === 0 ? "—" : attention.count}
            hint={
              connectedCount === 0
                ? "Link a source to begin"
                : attention.count === 0
                  ? "All sources healthy"
                  : attention.labels.join(", ")
            }
            className="border-zinc-800 bg-zinc-950/60"
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
                : "Pull metadata, code, docs, and tickets into your workspace. Items already in the graph are left unchanged."}
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
