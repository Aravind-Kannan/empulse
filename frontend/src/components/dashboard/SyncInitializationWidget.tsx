"use client";

import { useIntegrations } from "@/context/IntegrationsContext";
import {
  getConnectedIntegrationIds,
  INTEGRATION_CATALOG,
  isIntegrationConnected,
} from "@/lib/integrations";
import { GlobalSyncProgressBar } from "@/components/integrations/GlobalSyncProgressBar";
import { Loader2, Sparkles, Zap } from "lucide-react";

import { SyncJobsPanel } from "@/components/integrations/SyncJobsPanel";

/**
 * Dashboard widget — user-initiated sync. Never blocks navigation.
 */
export function SyncInitializationWidget() {
  const {
    config,
    syncProgress,
    syncJobs,
    syncActionError,
    globalSyncPending,
    isSyncing,
    isSyncComplete,
    triggerGlobalSync,
    triggerSourceSync,
    cancelSyncJob,
  } = useIntegrations();

  const connectedCount = getConnectedIntegrationIds(config).length;
  const connectedApps = INTEGRATION_CATALOG.filter((app) =>
    isIntegrationConnected(app.id, config),
  );

  if (connectedCount === 0) return null;

  return (
    <section className="rounded-2xl border border-violet-500/20 bg-gradient-to-br from-violet-500/10 via-zinc-900/50 to-zinc-950/80 p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-violet-500/30 bg-violet-500/10">
            <Zap className="h-5 w-5 text-violet-300" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-zinc-100">
              Knowledge graph initialization
            </h2>
            <p className="mt-1 max-w-xl text-sm text-zinc-400">
              {isSyncComplete
                ? "Your organizational memory graph is ready. Re-sync anytime to pull fresh data."
                : "Cognee compiles PRs, docs, tickets, and threads in the background. Start when ready — you can browse freely while jobs run."}
            </p>
          </div>
        </div>

        <button
          type="button"
          disabled={isSyncing || connectedCount === 0}
          onClick={() => void triggerGlobalSync()}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-zinc-100 px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          {isSyncing ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Syncing…
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              {isSyncComplete ? "Re-sync all engines" : "Sync all engines"}
            </>
          )}
        </button>
      </div>

      {(isSyncing || globalSyncPending) && (
        <div className="mt-5">
          <GlobalSyncProgressBar progress={syncProgress} currentJob={syncProgress.currentJob} />
        </div>
      )}

      {syncActionError && (
        <p className="mt-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {syncActionError}
        </p>
      )}

      <div className="mt-5 flex flex-wrap gap-2">
        {connectedApps.map((app) => (
          <button
            key={app.id}
            type="button"
            disabled={isSyncing}
            onClick={() => void triggerSourceSync(app.id)}
            className="rounded-lg border border-zinc-700 bg-zinc-950/60 px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-100 disabled:opacity-40"
          >
            Sync {app.name}
          </button>
        ))}
      </div>

      {syncJobs.length > 0 && (
        <div className="mt-5 border-t border-zinc-800 pt-5">
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
      )}
    </section>
  );
}
