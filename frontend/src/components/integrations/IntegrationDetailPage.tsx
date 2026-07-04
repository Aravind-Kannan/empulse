"use client";

import { useCallback, useMemo } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  ChevronRight,
  GitBranch,
  History,
  LayoutDashboard,
  Loader2,
  RefreshCw,
  Settings2,
  Unplug,
} from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import {
  INTEGRATION_CATALOG,
  githubRepoSyncBranchLabel,
  isIntegrationConnected,
  type IntegrationId,
} from "@/lib/integrations";
import {
  integrationDetailPath,
  integrationListPath,
  parseIntegrationDetailTab,
  type IntegrationDetailTab,
} from "@/lib/integration-routes";
import { apiDateToEpochMs } from "@/lib/datetime";
import { jobsForIntegration } from "@/lib/sync-jobs";

import { GitHubRepoSyncPanel } from "./GitHubRepoSyncPanel";
import { IntegrationConfigPanel } from "./IntegrationConfigPanel";
import { IntegrationLogo } from "./IntegrationLogos";
import { IntegrationOverviewTab } from "./IntegrationOverviewTab";
import { IntegrationStatusBadge } from "./IntegrationStatusBadge";
import { SyncJobsPanel } from "./SyncJobsPanel";

interface IntegrationDetailPageProps {
  integrationId: IntegrationId;
}

function DetailTabButton({
  active,
  onClick,
  icon: Icon,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  count?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
        active
          ? "bg-gradient-to-br from-zinc-100 to-zinc-200 text-slate-950 shadow-lg shadow-black/20"
          : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200"
      }`}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {label}
      {count !== undefined && count > 0 ? (
        <span
          className={`rounded-full px-1.5 py-0.5 text-[11px] font-semibold tabular-nums ${
            active ? "bg-slate-900/10 text-slate-800" : "bg-zinc-800 text-zinc-400"
          }`}
        >
          {count}
        </span>
      ) : null}
    </button>
  );
}

export function IntegrationDetailPage({ integrationId }: IntegrationDetailPageProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeTab = parseIntegrationDetailTab(searchParams.get("tab"));
  const returnTo = searchParams.get("returnTo");

  const app = INTEGRATION_CATALOG.find((entry) => entry.id === integrationId);
  const {
    config,
    syncJobs,
    disconnectingSources,
    getStatus,
    triggerSourceSync,
    triggerGitHubRepoSync,
    cancelSyncJob,
    disconnect,
  } = useIntegrations();

  const status = getStatus(integrationId);
  const connected = isIntegrationConnected(integrationId, config);
  const syncing = status === "syncing";
  const sourceJobs = useMemo(
    () => jobsForIntegration(syncJobs, integrationId),
    [syncJobs, integrationId],
  );
  const latestJob = useMemo(() => {
    const sorted = [...sourceJobs].sort(
      (a, b) => apiDateToEpochMs(b.created_at) - apiDateToEpochMs(a.created_at),
    );
    return sorted[0] ?? null;
  }, [sourceJobs]);
  const isActive =
    syncing || latestJob?.status === "running" || latestJob?.status === "queued";
  const disconnecting = disconnectingSources.has(integrationId);

  const githubRepositoryUrls =
    integrationId === "github"
      ? config.github.repositoryUrls.length > 0
        ? config.github.repositoryUrls
        : config.github.repositoryUrl
          ? [config.github.repositoryUrl]
          : []
      : [];

  const switchTab = useCallback(
    (tab: IntegrationDetailTab) => {
      router.replace(
        integrationDetailPath(integrationId, { tab, returnTo: returnTo ?? undefined }),
        { scroll: false },
      );
    },
    [integrationId, returnTo, router],
  );

  if (!app) {
    return null;
  }

  const backHref = returnTo ?? integrationListPath();
  const backLabel = returnTo?.includes("onboarding")
    ? "Back to onboarding"
    : "All integrations";

  const tabs: {
    id: IntegrationDetailTab;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    count?: number;
    hidden?: boolean;
  }[] = [
    { id: "overview", label: "Overview", icon: LayoutDashboard },
    { id: "configuration", label: "Configuration", icon: Settings2 },
    { id: "runs", label: "Runs", icon: History, count: sourceJobs.length },
    {
      id: "repositories",
      label: "Repositories",
      icon: GitBranch,
      hidden: integrationId !== "github" || !connected || githubRepositoryUrls.length === 0,
    },
  ];

  const visibleTabs = tabs.filter((tab) => !tab.hidden);

  return (
    <div className="space-y-6">
      <nav className="flex flex-wrap items-center gap-1.5 text-sm text-zinc-500">
        <Link
          href={backHref}
          className="inline-flex items-center gap-1 transition hover:text-zinc-300"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {backLabel}
        </Link>
        <ChevronRight className="h-3.5 w-3.5 text-zinc-700" />
        <span className="text-zinc-300">{app.name}</span>
      </nav>

      <header className="overflow-hidden rounded-2xl border border-zinc-800/80 bg-gradient-to-br from-zinc-900/90 via-zinc-950/95 to-zinc-950 p-6 shadow-xl shadow-black/10">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex min-w-0 items-start gap-4">
            <div
              className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl shadow-inner ${app.accentBg}`}
            >
              <IntegrationLogo
                id={app.id}
                className={`h-7 w-7 ${app.iconClassName}`}
              />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-semibold text-zinc-100">{app.name}</h1>
                <IntegrationStatusBadge status={status} size="md" />
              </div>
              <p className="mt-1 max-w-2xl text-sm text-zinc-400">{app.description}</p>
            </div>
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {connected && (
              <>
                <button
                  type="button"
                  disabled={!connected || isActive || disconnecting}
                  onClick={() => void triggerSourceSync(integrationId)}
                  className="inline-flex items-center justify-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900/80 px-4 py-2.5 text-sm font-medium text-zinc-100 backdrop-blur-sm transition hover:border-zinc-600 hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {isActive ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Syncing…
                    </>
                  ) : (
                    <>
                      <RefreshCw className="h-4 w-4" />
                      Sync now
                    </>
                  )}
                </button>
                <button
                  type="button"
                  disabled={disconnecting || isActive}
                  onClick={() => void disconnect(integrationId)}
                  className="inline-flex items-center justify-center gap-2 rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-2.5 text-sm font-medium text-red-300 transition hover:border-red-500/50 hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {disconnecting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Disconnecting…
                    </>
                  ) : (
                    <>
                      <Unplug className="h-4 w-4" />
                      Disconnect
                    </>
                  )}
                </button>
              </>
            )}
            {!connected && (
              <button
                type="button"
                onClick={() => switchTab("configuration")}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-100 px-4 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white"
              >
                Connect {app.name}
              </button>
            )}
          </div>
        </div>
      </header>

      <div className="rounded-xl border border-zinc-800/80 bg-zinc-950/40 p-1 backdrop-blur-sm">
        <div className="flex flex-wrap gap-1">
          {visibleTabs.map((tab) => (
            <DetailTabButton
              key={tab.id}
              active={activeTab === tab.id}
              onClick={() => switchTab(tab.id)}
              icon={tab.icon}
              label={tab.label}
              count={tab.count}
            />
          ))}
        </div>
      </div>

      <div className="min-h-[320px]">
        {activeTab === "overview" && (
          <IntegrationOverviewTab
            app={app}
            connected={connected}
            syncing={syncing}
            latestJob={latestJob}
            sourceJobs={sourceJobs}
            onOpenConfiguration={() => switchTab("configuration")}
          />
        )}

        {activeTab === "configuration" && (
          <IntegrationConfigPanel app={app} variant="page" />
        )}

        {activeTab === "runs" && (
          <SyncJobsPanel
            jobs={sourceJobs}
            sourceFilter={integrationId}
            onRetrySource={() => void triggerSourceSync(integrationId)}
            onCancelJob={(jobId) => void cancelSyncJob(jobId)}
          />
        )}

        {activeTab === "repositories" &&
          integrationId === "github" &&
          connected &&
          githubRepositoryUrls.length > 0 && (
            <section className="overflow-hidden rounded-2xl border border-zinc-800/80 bg-zinc-950/30">
              <div className="border-b border-zinc-800/80 px-5 py-4">
                <h2 className="text-sm font-medium text-zinc-200">
                  Repository code sync
                </h2>
                <p className="mt-1 text-xs text-zinc-500">
                  Full tree walk on{" "}
                  <span className="text-zinc-400">
                    {githubRepoSyncBranchLabel(config.github)}
                  </span>{" "}
                  — code ownership and blame metadata. One job per repo.
                </p>
              </div>
              <GitHubRepoSyncPanel
                repositoryUrls={githubRepositoryUrls}
                branchScopeLabel={githubRepoSyncBranchLabel(config.github)}
                syncJobs={sourceJobs}
                showHeader={false}
                embedded
                onSyncRepo={(repositoryUrl) => {
                  void triggerGitHubRepoSync(repositoryUrl);
                }}
              />
            </section>
          )}
      </div>
    </div>
  );
}
