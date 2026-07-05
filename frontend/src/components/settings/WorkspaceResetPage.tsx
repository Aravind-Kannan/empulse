"use client";

import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  Loader2,
  Radar,
  RotateCcw,
  ShieldAlert,
  Trash2,
  Users,
} from "lucide-react";

import { TenantSwitcher } from "@/components/settings/TenantSwitcher";
import { useIntegrations } from "@/context/IntegrationsContext";
import { useWorkspace } from "@/context/WorkspaceContext";
import { resetCogneeDataset, wipeWorkspaceOperationalData } from "@/lib/api";
import type {
  CogneeDatasetResetResponse,
  WorkspaceWipeResponse,
} from "@/lib/types";

type GraphResetOption = {
  id: "memoryOnly" | "clearLedger" | "clearTelemetry";
  label: string;
  description: string;
  icon: typeof Database;
  recommended?: boolean;
};

const GRAPH_RESET_OPTIONS: GraphResetOption[] = [
  {
    id: "memoryOnly",
    label: "Memory only",
    description:
      "Remove graph nodes and embeddings while keeping raw dataset files for re-cognify.",
    icon: Database,
  },
  {
    id: "clearLedger",
    label: "Clear sync ledger",
    description: "Force the next sync to re-ingest every item from connected sources.",
    icon: RotateCcw,
    recommended: true,
  },
  {
    id: "clearTelemetry",
    label: "Clear telemetry",
    description:
      "Also wipe DOA snapshots, ownership telemetry, and in-memory integration metrics.",
    icon: Radar,
  },
];

export function WorkspaceResetPage() {
  const { syncProgress, globalSyncPending, refreshSyncJobs } = useIntegrations();
  const { refreshOperationalState } = useWorkspace();

  const [memoryOnly, setMemoryOnly] = useState(false);
  const [clearLedger, setClearLedger] = useState(true);
  const [clearTelemetry, setClearTelemetry] = useState(false);
  const [graphConfirmOpen, setGraphConfirmOpen] = useState(false);
  const [wipeConfirmOpen, setWipeConfirmOpen] = useState(false);
  const [graphPending, setGraphPending] = useState(false);
  const [wipePending, setWipePending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [graphResult, setGraphResult] = useState<CogneeDatasetResetResponse | null>(
    null,
  );
  const [wipeResult, setWipeResult] = useState<WorkspaceWipeResponse | null>(null);

  const syncActive = syncProgress.active || globalSyncPending;
  const disabled = graphPending || wipePending || syncActive;

  const graphOptionState = {
    memoryOnly,
    clearLedger,
    clearTelemetry,
  } as const;

  function setGraphOption(id: GraphResetOption["id"], value: boolean) {
    if (id === "memoryOnly") setMemoryOnly(value);
    if (id === "clearLedger") setClearLedger(value);
    if (id === "clearTelemetry") setClearTelemetry(value);
  }

  async function handleGraphReset() {
    setGraphPending(true);
    setError(null);
    setGraphResult(null);
    try {
      const response = await resetCogneeDataset({
        memory_only: memoryOnly,
        clear_ledger: clearLedger,
        clear_telemetry: clearTelemetry,
      });
      setGraphResult(response);
      setGraphConfirmOpen(false);
      await refreshSyncJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Knowledge graph reset failed");
    } finally {
      setGraphPending(false);
    }
  }

  async function handleOperationalWipe() {
    setWipePending(true);
    setError(null);
    setWipeResult(null);
    try {
      const response = await wipeWorkspaceOperationalData();
      setWipeResult(response);
      setWipeConfirmOpen(false);
      await refreshOperationalState();
      await refreshSyncJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Workspace wipe failed");
    } finally {
      setWipePending(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div className="relative overflow-hidden rounded-2xl border border-red-500/15 bg-gradient-to-br from-red-950/30 via-zinc-950 to-slate-950 p-8 shadow-2xl shadow-red-950/20">
        <div
          className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-red-500/10 blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -bottom-20 -left-10 h-56 w-56 rounded-full bg-violet-500/10 blur-3xl"
          aria-hidden
        />

        <div className="relative flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-red-500/20 bg-red-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-red-300">
              <ShieldAlert className="h-3.5 w-3.5" />
              Danger zone
            </div>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-zinc-50">
                Workspace reset &amp; data wipe
              </h1>
              <p className="mt-2 max-w-xl text-sm leading-relaxed text-zinc-400">
                Irreversible actions for this tenant. Reset the Cognee knowledge
                graph, or wipe all operational workspace data — employees,
                components, incidents, and analytics snapshots. Integration
                credentials are preserved unless you disconnect them separately.
              </p>
            </div>
          </div>

          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-red-500/20 bg-red-500/10 shadow-inner shadow-red-950/40">
            <AlertTriangle className="h-6 w-6 text-red-300" />
          </div>
        </div>
      </div>

      <TenantSwitcher />

      {syncActive ? (
        <p className="rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-sm text-amber-200/90">
          Active sync in progress. Wait for jobs to finish before resetting or
          wiping data.
        </p>
      ) : null}

      {error ? (
        <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </p>
      ) : null}

      <section className="space-y-4 rounded-2xl border border-zinc-800/80 bg-zinc-900/20 p-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500">
            Knowledge graph reset
          </p>
          <p className="mt-1 text-sm text-zinc-400">
            Wipe Cognee graph memory and vectors for this tenant. Use before a
            full re-ingest from connected integrations.
          </p>
        </div>

        <div className="space-y-3">
          {GRAPH_RESET_OPTIONS.map((option) => {
            const Icon = option.icon;
            const checked = graphOptionState[option.id];

            return (
              <button
                key={option.id}
                type="button"
                disabled={disabled}
                onClick={() => setGraphOption(option.id, !checked)}
                className={`group flex w-full items-start gap-4 rounded-xl border px-4 py-4 text-left transition ${
                  checked
                    ? "border-red-500/30 bg-red-500/5 shadow-inner shadow-red-950/20"
                    : "border-zinc-800/80 bg-zinc-900/30 hover:border-zinc-700 hover:bg-zinc-900/50"
                } disabled:cursor-not-allowed disabled:opacity-50`}
              >
                <span
                  className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border transition ${
                    checked
                      ? "border-red-500/30 bg-red-500/10 text-red-300"
                      : "border-zinc-800 bg-zinc-950/60 text-zinc-500 group-hover:text-zinc-300"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-zinc-100">
                      {option.label}
                    </span>
                    {option.recommended ? (
                      <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300">
                        Recommended
                      </span>
                    ) : null}
                  </span>
                  <span className="mt-1 block text-sm leading-relaxed text-zinc-500">
                    {option.description}
                  </span>
                </span>
                <span
                  className={`mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition ${
                    checked
                      ? "border-red-400 bg-red-500 text-white"
                      : "border-zinc-700 bg-zinc-950"
                  }`}
                >
                  {checked ? <CheckCircle2 className="h-3.5 w-3.5" /> : null}
                </span>
              </button>
            );
          })}
        </div>

        {graphResult ? (
          <p className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
            {graphResult.message}
          </p>
        ) : null}

        {!graphConfirmOpen ? (
          <button
            type="button"
            disabled={disabled}
            onClick={() => setGraphConfirmOpen(true)}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-3 text-sm font-semibold text-red-200 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Trash2 className="h-4 w-4" />
            Reset knowledge graph
          </button>
        ) : (
          <div className="space-y-4 rounded-2xl border border-red-500/25 bg-red-500/5 p-5">
            <p className="text-sm leading-relaxed text-red-200/90">
              This cannot be undone. All Cognee graph memory for this tenant will
              be deleted
              {clearTelemetry ? " and telemetry will be cleared" : ""}.
            </p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                disabled={graphPending}
                onClick={() => void handleGraphReset()}
                className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-red-500 disabled:opacity-50"
              >
                {graphPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Yes, reset graph
              </button>
              <button
                type="button"
                disabled={graphPending}
                onClick={() => setGraphConfirmOpen(false)}
                className="rounded-xl border border-zinc-700 bg-zinc-950/60 px-4 py-3 text-sm font-medium text-zinc-300 transition hover:bg-zinc-900 disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="space-y-4 rounded-2xl border border-red-500/20 bg-red-950/10 p-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-red-400/80">
            Operational data wipe
          </p>
          <p className="mt-1 text-sm text-zinc-400">
            Permanently delete all workspace records: employees, components,
            assignments, identity mappings, incidents, ERA/KRA snapshots, sync
            job history, and ingest history. Integration API tokens are kept.
          </p>
        </div>

        <ul className="space-y-2 text-sm text-zinc-500">
          <li className="flex items-start gap-2">
            <Users className="mt-0.5 h-4 w-4 shrink-0 text-red-400/80" />
            Org chart roster and component catalog removed from Postgres
          </li>
          <li className="flex items-start gap-2">
            <Trash2 className="mt-0.5 h-4 w-4 shrink-0 text-red-400/80" />
            Investigation incidents and unmapped activity quarantine cleared
          </li>
          <li className="flex items-start gap-2">
            <Radar className="mt-0.5 h-4 w-4 shrink-0 text-red-400/80" />
            ERA alerts, risk snapshots, and ownership telemetry deleted
          </li>
        </ul>

        {wipeResult ? (
          <p className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
            {wipeResult.message}
            <span className="mt-1 block text-emerald-400/80">
              Total rows removed: {wipeResult.total_rows_removed}
            </span>
          </p>
        ) : null}

        {!wipeConfirmOpen ? (
          <button
            type="button"
            disabled={disabled}
            onClick={() => setWipeConfirmOpen(true)}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-red-700 to-red-600 px-5 py-3.5 text-sm font-semibold text-white shadow-lg shadow-red-950/30 transition hover:from-red-600 hover:to-red-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Trash2 className="h-4 w-4" />
            Wipe all workspace data
          </button>
        ) : (
          <div className="space-y-4 rounded-2xl border border-red-500/30 bg-red-500/10 p-5">
            <p className="text-sm leading-relaxed text-red-100">
              This permanently deletes every employee, component, incident, and
              analytics snapshot for this workspace. You will need to re-import
              your org chart and re-sync integrations afterward.
            </p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                disabled={wipePending}
                onClick={() => void handleOperationalWipe()}
                className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-red-700 px-4 py-3 text-sm font-semibold text-white transition hover:bg-red-600 disabled:opacity-50"
              >
                {wipePending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Yes, wipe everything
              </button>
              <button
                type="button"
                disabled={wipePending}
                onClick={() => setWipeConfirmOpen(false)}
                className="rounded-xl border border-zinc-700 bg-zinc-950/60 px-4 py-3 text-sm font-medium text-zinc-300 transition hover:bg-zinc-900 disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
