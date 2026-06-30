"use client";

import { CheckCircle2, Loader2, RefreshCw } from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import { INTEGRATION_CATALOG, isIntegrationConnected } from "@/lib/integrations";

export function GlobalSyncBanner() {
  const { config, syncProgress, triggerGlobalSync } = useIntegrations();
  const connectedCount = INTEGRATION_CATALOG.filter((app) =>
    isIntegrationConnected(app.id, config),
  ).length;

  const progressPct =
    syncProgress.total > 0
      ? Math.round(
          (syncProgress.completed.length / syncProgress.total) * 100,
        )
      : 0;

  return (
    <section className="rounded-2xl border border-zinc-800 bg-gradient-to-r from-zinc-900/90 via-slate-900/90 to-zinc-900/90 p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Knowledge graph
          </p>
          <h2 className="mt-1 text-lg font-semibold text-zinc-100">
            Trigger Global Graph Sync
          </h2>
          <p className="mt-1 max-w-xl text-sm text-zinc-400">
            Ingest metadata from all connected sources into the Cognee knowledge
            graph. {connectedCount} source{connectedCount === 1 ? "" : "s"}{" "}
            ready.
          </p>
        </div>

        <button
          type="button"
          disabled={syncProgress.active || connectedCount === 0}
          onClick={() => void triggerGlobalSync()}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-zinc-100 px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          {syncProgress.active ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Syncing…
            </>
          ) : (
            <>
              <RefreshCw className="h-4 w-4" />
              Sync all sources
            </>
          )}
        </button>
      </div>

      {(syncProgress.active || syncProgress.completed.length > 0) && (
        <div className="mt-5 space-y-3 border-t border-zinc-800 pt-4">
          <div className="flex items-center justify-between text-xs text-zinc-500">
            <span>
              {syncProgress.active && syncProgress.currentSource
                ? `Ingesting ${syncProgress.currentSource}…`
                : syncProgress.active
                  ? "Preparing ingestion pipeline…"
                  : "Sync complete"}
            </span>
            <span>{progressPct}%</span>
          </div>

          <div className="h-2 overflow-hidden rounded-full bg-zinc-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-sky-500 to-emerald-400 transition-all duration-500 ease-out"
              style={{ width: `${progressPct}%` }}
            />
          </div>

          {syncProgress.error && (
            <p className="text-xs text-red-400">{syncProgress.error}</p>
          )}
          <ul className="flex flex-wrap gap-2">
            {INTEGRATION_CATALOG.filter((app) =>
              isIntegrationConnected(app.id, config),
            ).map((app) => {
              const done = syncProgress.completed.includes(app.name);
              const active =
                syncProgress.currentSource === app.name ||
                (syncProgress.currentSource === "GitHub & Jira" &&
                  (app.id === "github" || app.id === "jira") &&
                  syncProgress.active &&
                  !done);

              return (
                <li
                  key={app.id}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${
                    done
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                      : active
                        ? "border-sky-500/30 bg-sky-500/10 text-sky-400"
                        : "border-zinc-800 bg-zinc-900 text-zinc-500"
                  }`}
                >
                  {done ? (
                    <CheckCircle2 className="h-3 w-3" />
                  ) : active ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : null}
                  {app.name}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
