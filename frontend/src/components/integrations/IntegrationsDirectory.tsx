"use client";

import { useMemo } from "react";
import { Loader2, RefreshCw } from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import {
  INTEGRATION_CATALOG,
  getConnectedIntegrationIds,
  isIntegrationConnected,
} from "@/lib/integrations";
import { jobsForIntegration, latestJobPerSource } from "@/lib/sync-jobs";

import { GlobalSyncProgressBar } from "./GlobalSyncProgressBar";
import { IntegrationCard } from "./IntegrationCard";
import { IntegrationsStatsRow } from "./IntegrationsStatsRow";

interface IntegrationsDirectoryProps {
  showSyncToolbar?: boolean;
  className?: string;
  returnTo?: string;
}

export function IntegrationsDirectory({
  showSyncToolbar = false,
  className = "",
  returnTo,
}: IntegrationsDirectoryProps) {
  const {
    config,
    syncJobs,
    syncProgress,
    syncActionError,
    globalSyncPending,
    getStatus,
    triggerGlobalSync,
  } = useIntegrations();

  const latestBySource = useMemo(() => latestJobPerSource(syncJobs), [syncJobs]);
  const connectedCount = getConnectedIntegrationIds(config).length;
  const isGlobalBusy = syncProgress.active || globalSyncPending;

  return (
    <div className={`space-y-6 ${className}`}>
      {showSyncToolbar && (
        <>
          <IntegrationsStatsRow />

          <div className="rounded-2xl border border-zinc-800/80 bg-gradient-to-b from-zinc-900/60 to-zinc-950/80 p-5 backdrop-blur-sm">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-medium text-zinc-200">
                  {connectedCount === 0
                    ? "Connect a source to start building your graph"
                    : `${connectedCount} source${connectedCount === 1 ? "" : "s"} connected`}
                </p>
                <p className="mt-1 max-w-xl text-xs text-zinc-500">
                  {connectedCount === 0
                    ? "Choose an integration below to connect and configure."
                    : "Unchanged items are skipped automatically on re-sync."}
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
                    Syncing all…
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-4 w-4" />
                    Sync all connected ({connectedCount})
                  </>
                )}
              </button>
            </div>

            {syncActionError && (
              <p className="mt-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-300">
                {syncActionError}
              </p>
            )}

            {(syncProgress.active || globalSyncPending) && (
              <div className="mt-4 border-t border-zinc-800/60 pt-4">
                <GlobalSyncProgressBar
                  progress={syncProgress}
                  currentJob={syncProgress.currentJob}
                  compact
                />
              </div>
            )}
          </div>
        </>
      )}

      <section>
        <div className="mb-5">
          <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
            Data sources
          </h2>
          <p className="mt-1 text-sm text-zinc-400">
            Connect engineering tools and keep your workspace data in sync.
          </p>
        </div>

        <ul className="grid gap-4 sm:grid-cols-2">
          {INTEGRATION_CATALOG.map((app) => {
            const status = getStatus(app.id);
            const connected = isIntegrationConnected(app.id, config);
            const sourceJobs = jobsForIntegration(syncJobs, app.id);

            return (
              <IntegrationCard
                key={app.id}
                app={app}
                status={status}
                connected={connected}
                syncing={status === "syncing"}
                latestJob={latestBySource.get(app.id) ?? null}
                runCount={sourceJobs.length}
                returnTo={returnTo}
              />
            );
          })}
        </ul>
      </section>
    </div>
  );
}
