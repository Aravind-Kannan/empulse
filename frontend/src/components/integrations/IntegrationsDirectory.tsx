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

          {syncActionError && (
            <p className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {syncActionError}
            </p>
          )}

          {(syncProgress.active || globalSyncPending) && (
            <GlobalSyncProgressBar
              progress={syncProgress}
              currentJob={syncProgress.currentJob}
              compact
            />
          )}
        </>
      )}

      <section>
        <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
              Data sources
            </h2>
            <p className="mt-1 text-sm text-zinc-400">
              Connect engineering tools and keep your workspace data in sync.
            </p>
          </div>
          {showSyncToolbar ? (
            <button
              type="button"
              disabled={isGlobalBusy || connectedCount === 0}
              onClick={() => void triggerGlobalSync()}
              className="inline-flex shrink-0 items-center justify-center gap-2 self-end rounded-lg bg-zinc-100 px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-40 sm:self-auto"
            >
              {isGlobalBusy ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Syncing…
                </>
              ) : (
                <>
                  <RefreshCw className="h-4 w-4" />
                  Sync all
                </>
              )}
            </button>
          ) : null}
        </div>

        <ul className="grid gap-5 sm:grid-cols-2">
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
