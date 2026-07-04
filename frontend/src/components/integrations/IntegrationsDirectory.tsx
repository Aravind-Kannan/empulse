"use client";

import { useMemo } from "react";
import { Loader2, RefreshCw } from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import {
  INTEGRATION_CATALOG,
  getConnectedIntegrationIds,
  githubRepoSyncBranchLabel,
  isIntegrationConnected,
} from "@/lib/integrations";
import { jobsForIntegration, latestJobPerSource } from "@/lib/sync-jobs";

import { IntegrationRow } from "./IntegrationRow";
import { GlobalSyncProgressBar } from "./GlobalSyncProgressBar";
import {
  IntegrationConfigDrawer,
  useSelectedIntegration,
} from "./IntegrationConfigDrawer";

interface IntegrationsDirectoryProps {
  showSyncToolbar?: boolean;
  className?: string;
}

export function IntegrationsDirectory({
  showSyncToolbar = false,
  className = "",
}: IntegrationsDirectoryProps) {
  const {
    config,
    syncJobs,
    syncProgress,
    syncActionError,
    globalSyncPending,
    disconnectingSources,
    getStatus,
    triggerGlobalSync,
    triggerSourceSync,
    triggerGitHubRepoSync,
    cancelSyncJob,
    disconnect,
  } = useIntegrations();
  const { selectedApp, open, close } = useSelectedIntegration();

  const latestBySource = useMemo(() => latestJobPerSource(syncJobs), [syncJobs]);
  const connectedCount = getConnectedIntegrationIds(config).length;
  const isGlobalBusy = syncProgress.active || globalSyncPending;

  return (
    <>
      <div className={`space-y-6 ${className}`}>
        {showSyncToolbar && (
          <div className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm text-zinc-400">
                  {connectedCount === 0
                    ? "Connect a source below to start syncing into your knowledge graph."
                    : `${connectedCount} source${connectedCount === 1 ? "" : "s"} connected. Sync pulls metadata into Cognee — unchanged items are skipped.`}
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
          </div>
        )}

        <section>
          <div className="mb-4">
            <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
              Integrations
            </h2>
            <p className="mt-1 text-sm text-zinc-400">
              Connect, configure, and sync each source from one place.
            </p>
          </div>

          <ul className="space-y-2">
            {INTEGRATION_CATALOG.map((app) => {
              const status = getStatus(app.id);
              const connected = isIntegrationConnected(app.id, config);

              return (
                <IntegrationRow
                  key={app.id}
                  app={app}
                  status={status}
                  connected={connected}
                  syncing={status === "syncing"}
                  disconnecting={disconnectingSources.has(app.id)}
                  latestJob={latestBySource.get(app.id) ?? null}
                  sourceJobs={jobsForIntegration(syncJobs, app.id)}
                  onConfigure={() => open(app.id)}
                  onSync={() => {
                    void triggerSourceSync(app.id);
                  }}
                  onDisconnect={() => {
                    void disconnect(app.id);
                  }}
                  githubRepositoryUrls={
                    app.id === "github"
                      ? config.github.repositoryUrls.length > 0
                        ? config.github.repositoryUrls
                        : config.github.repositoryUrl
                          ? [config.github.repositoryUrl]
                          : []
                      : undefined
                  }
                  githubBranchScopeLabel={githubRepoSyncBranchLabel(config.github)}
                  onSyncGitHubRepo={
                    app.id === "github"
                      ? (repositoryUrl) => {
                          void triggerGitHubRepoSync(repositoryUrl);
                        }
                      : undefined
                  }
                  onCancelSyncJob={(jobId) => {
                    void cancelSyncJob(jobId);
                  }}
                />
              );
            })}
          </ul>
        </section>
      </div>

      {selectedApp && (
        <IntegrationConfigDrawer app={selectedApp} onClose={close} />
      )}
    </>
  );
}
