"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Loader2, Sparkles, Zap } from "lucide-react";

import { GlobalSyncProgressBar } from "@/components/integrations/GlobalSyncProgressBar";
import { useIntegrations } from "@/context/IntegrationsContext";
import {
  getConnectedIntegrationIds,
  INTEGRATION_CATALOG,
  isIntegrationConnected,
  workspaceRequiresIntegrations,
} from "@/lib/integrations";
import { integrationsNeverSynced } from "@/lib/sync-jobs";

interface KnowledgeIngestionGateProps {
  children: React.ReactNode;
}

/**
 * Blur + overlay for ERA, KRA, and Investigation while integrations are missing,
 * Cognee ingestion runs, or sync has not yet completed.
 */
export function KnowledgeIngestionGate({ children }: KnowledgeIngestionGateProps) {
  const pathname = usePathname();
  const {
    config,
    syncJobs,
    isSyncing,
    isSyncComplete,
    syncProgress,
    globalSyncPending,
    syncActionError,
    triggerGlobalSync,
  } = useIntegrations();
  const connectedCount = getConnectedIntegrationIds(config).length;

  const required = workspaceRequiresIntegrations(pathname);
  const missingRequired =
    required.length > 0 &&
    !required.some((id) => isIntegrationConnected(id, config));
  const syncNotStarted =
    connectedCount > 0 &&
    !isSyncComplete &&
    !isSyncing &&
    integrationsNeverSynced(config, syncJobs);
  const awaitingSync = connectedCount > 0 && (isSyncing || !isSyncComplete);
  const gated = missingRequired || awaitingSync;
  const showProgress = isSyncing || globalSyncPending || syncProgress.total > 0;

  const requiredNames = required
    .map((id) => INTEGRATION_CATALOG.find((app) => app.id === id)?.name ?? id)
    .join(" or ");

  return (
    <div className="relative">
      <div
        className={
          gated
            ? "pointer-events-none select-none blur-md transition-[filter] duration-500"
            : "transition-[filter] duration-500"
        }
        aria-hidden={gated}
      >
        {children}
      </div>

      {gated && (
        <div className="pointer-events-none fixed inset-y-0 right-0 left-[var(--sidebar-width,17.75rem)] z-20 flex items-center justify-center p-6">
          <div className="pointer-events-auto w-full max-w-lg rounded-2xl border border-zinc-700/80 bg-zinc-950/90 p-6 shadow-2xl shadow-black/40 backdrop-blur-md">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-amber-500/30 bg-amber-500/10">
                {isSyncing || globalSyncPending ? (
                  <Loader2 className="h-5 w-5 animate-spin text-amber-300" />
                ) : (
                  <Zap className="h-5 w-5 text-amber-300" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-base font-semibold text-zinc-100">
                  {missingRequired
                    ? "Integration Setup Required"
                    : syncNotStarted
                      ? "Knowledge Graph Sync Required"
                      : "Asynchronous Knowledge Ingestion in Progress"}
                </p>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                  {missingRequired ? (
                    <>
                      Connect {requiredNames} to populate this view. The layout
                      below is preview-only until credentials are verified.
                    </>
                  ) : syncNotStarted ? (
                    <>
                      Connected integrations are saved, but organizational
                      memory graph compilation has not started yet. Start sync
                      to unlock this view.
                    </>
                  ) : (
                    <>
                      Your organizational memory graph is being built from
                      configured integrations. This view unlocks automatically
                      when processing completes.
                    </>
                  )}
                </p>
              </div>
            </div>

            {!missingRequired && showProgress && (
              <div className="mt-5">
                <GlobalSyncProgressBar
                  progress={syncProgress}
                  currentJob={syncProgress.currentJob}
                  compact
                />
              </div>
            )}

            {syncActionError && (
              <p className="mt-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                {syncActionError}
              </p>
            )}

            {missingRequired ? (
              <Link
                href="/settings/integrations"
                className="mt-5 inline-flex rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-white"
              >
                Open integrations
              </Link>
            ) : syncNotStarted ? (
              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => void triggerGlobalSync()}
                  className="inline-flex items-center gap-2 rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-white"
                >
                  <Sparkles className="h-4 w-4" />
                  Sync all engines
                </button>
                <Link
                  href="/dashboard"
                  className="inline-flex items-center rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-100"
                >
                  Open dashboard
                </Link>
              </div>
            ) : !isSyncing && !globalSyncPending ? (
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => void triggerGlobalSync()}
                  className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-100"
                >
                  <Sparkles className="h-4 w-4" />
                  Retry sync
                </button>
                <Link
                  href="/settings/integrations"
                  className="text-xs leading-6 text-zinc-500 transition hover:text-zinc-300"
                >
                  Or run per-integration pipelines under Settings → Integrations
                </Link>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
