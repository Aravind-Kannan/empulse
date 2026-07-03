"use client";

import { Loader2, RefreshCw } from "lucide-react";

import { apiDateToEpochMs } from "@/lib/datetime";
import type { IntegrationSyncJobStatusResponse } from "@/lib/types";

import { RepoSyncProgress } from "./RepoSyncProgress";
import { SyncDuration } from "./SyncDuration";

function repoLabel(repositoryUrl: string): string {
  try {
    const parts = new URL(repositoryUrl).pathname.split("/").filter(Boolean);
    if (parts.length >= 2) {
      return `${parts[0]}/${parts[1]}`;
    }
  } catch {
    // fall through
  }
  return repositoryUrl.replace(/^https?:\/\//, "");
}

function isRepoJobActive(
  repositoryUrl: string,
  jobs: IntegrationSyncJobStatusResponse[],
): boolean {
  const normalized = repositoryUrl.trim().replace(/\/$/, "");
  return jobs.some(
    (job) =>
      job.job_kind === "github_repo" &&
      job.repository_url?.trim().replace(/\/$/, "") === normalized &&
      (job.status === "queued" || job.status === "running"),
  );
}

function latestRepoJob(
  repositoryUrl: string,
  jobs: IntegrationSyncJobStatusResponse[],
): IntegrationSyncJobStatusResponse | undefined {
  const normalized = repositoryUrl.trim().replace(/\/$/, "");
  const matches = jobs.filter(
    (job) =>
      job.job_kind === "github_repo" &&
      job.repository_url?.trim().replace(/\/$/, "") === normalized,
  );
  if (matches.length === 0) return undefined;
  return [...matches].sort(
    (a, b) => apiDateToEpochMs(b.created_at) - apiDateToEpochMs(a.created_at),
  )[0];
}

interface GitHubRepoSyncPanelProps {
  repositoryUrls: string[];
  branchScopeLabel: string;
  syncJobs: IntegrationSyncJobStatusResponse[];
  onSyncRepo: (repositoryUrl: string) => void;
}

export function GitHubRepoSyncPanel({
  repositoryUrls,
  branchScopeLabel,
  syncJobs,
  onSyncRepo,
}: GitHubRepoSyncPanelProps) {
  const urls = repositoryUrls.filter((url) => url.trim());
  if (urls.length === 0) {
    return null;
  }

  return (
    <div className="border-t border-zinc-800/80 bg-zinc-950/50 px-4 py-3 sm:px-5">
      <div className="mb-2">
        <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
          Repository code sync
        </p>
        <p className="mt-0.5 text-[11px] text-zinc-600">
          Walk full tree on{" "}
          <span className="text-zinc-500">{branchScopeLabel}</span> — blame metadata
          into Cognee (file bodies optional). One job per repo.
        </p>
      </div>

      <ul className="space-y-1.5">
        {urls.map((repositoryUrl) => {
          const active = isRepoJobActive(repositoryUrl, syncJobs);
          const job = latestRepoJob(repositoryUrl, syncJobs);

          return (
            <li
              key={repositoryUrl}
              className="flex flex-col gap-2 rounded-lg border border-zinc-800/80 bg-zinc-950/40 px-3 py-2 sm:flex-row sm:items-start sm:justify-between"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium text-zinc-200">
                  {repoLabel(repositoryUrl)}
                </p>

                {active && <RepoSyncProgress job={job} compact />}

                {!active && job?.status === "completed" && (
                  <p className="mt-0.5 text-[10px] text-emerald-400/80">
                    {job.result?.graph_nodes_created ?? 0} nodes ·{" "}
                    {job.result?.files_discovered ?? 0} files ·{" "}
                    {job.result?.branches_total ?? job.result?.branches_synced?.length ?? 1}{" "}
                    branch
                    {(job.result?.branches_total ?? 1) === 1 ? "" : "es"}
                    {" · "}
                    <SyncDuration job={job} className="inline text-emerald-400/60" />
                  </p>
                )}
                {!active && job?.status === "failed" && (
                  <p className="mt-0.5 text-[10px] text-red-400">
                    Last sync failed
                    {" · "}
                    <SyncDuration job={job} className="inline text-red-400/70" />
                  </p>
                )}
              </div>

              <button
                type="button"
                disabled={active}
                onClick={() => onSyncRepo(repositoryUrl)}
                className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-[11px] font-medium text-zinc-100 transition hover:border-zinc-600 hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {active ? (
                  <>
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Syncing…
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-3 w-3" />
                    Sync repo
                  </>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
