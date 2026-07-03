"use client";

import { useState } from "react";
import { AlertTriangle, Loader2, Trash2 } from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import { resetCogneeDataset } from "@/lib/api";
import type { CogneeDatasetResetResponse } from "@/lib/types";

export function CogneeDatasetResetPanel() {
  const { syncProgress, globalSyncPending, refreshSyncJobs } = useIntegrations();

  const [memoryOnly, setMemoryOnly] = useState(false);
  const [clearLedger, setClearLedger] = useState(true);
  const [clearTelemetry, setClearTelemetry] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CogneeDatasetResetResponse | null>(null);

  const syncActive = syncProgress.active || globalSyncPending;

  async function handleReset() {
    setPending(true);
    setError(null);
    setResult(null);
    try {
      const response = await resetCogneeDataset({
        memory_only: memoryOnly,
        clear_ledger: clearLedger,
        clear_telemetry: clearTelemetry,
      });
      setResult(response);
      setConfirmOpen(false);
      await refreshSyncJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="rounded-xl border border-red-500/20 bg-red-500/5">
      <div className="border-b border-red-500/20 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-medium text-red-300">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Knowledge graph reset
        </div>
        <p className="mt-1 text-xs text-zinc-400">
          Wipes the tenant Cognee dataset (graph + vectors). Disconnecting an
          integration only removes its ledger-tracked nodes — use this for a full
          clean slate before re-ingest.
        </p>
      </div>

      <div className="space-y-3 px-4 py-4">
        <label className="flex cursor-pointer items-start gap-2 text-sm text-zinc-300">
          <input
            type="checkbox"
            className="mt-0.5 rounded border-zinc-600 bg-zinc-900"
            checked={memoryOnly}
            onChange={(e) => setMemoryOnly(e.target.checked)}
            disabled={pending || syncActive}
          />
          <span>
            <span className="font-medium">Memory only</span>
            <span className="mt-0.5 block text-xs text-zinc-500">
              Delete graph nodes and embeddings only; raw dataset files stay for
              re-cognify.
            </span>
          </span>
        </label>

        <label className="flex cursor-pointer items-start gap-2 text-sm text-zinc-300">
          <input
            type="checkbox"
            className="mt-0.5 rounded border-zinc-600 bg-zinc-900"
            checked={clearLedger}
            onChange={(e) => setClearLedger(e.target.checked)}
            disabled={pending || syncActive}
          />
          <span>
            <span className="font-medium">Clear sync ledger</span>
            <span className="mt-0.5 block text-xs text-zinc-500">
              Next sync re-ingests all items (recommended).
            </span>
          </span>
        </label>

        <label className="flex cursor-pointer items-start gap-2 text-sm text-zinc-300">
          <input
            type="checkbox"
            className="mt-0.5 rounded border-zinc-600 bg-zinc-900"
            checked={clearTelemetry}
            onChange={(e) => setClearTelemetry(e.target.checked)}
            disabled={pending || syncActive}
          />
          <span>
            <span className="font-medium">Clear telemetry</span>
            <span className="mt-0.5 block text-xs text-zinc-500">
              Also clears DOA/ownership snapshots and in-memory integration
              telemetry.
            </span>
          </span>
        </label>

        {error && (
          <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
            {error}
          </p>
        )}

        {result && (
          <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300">
            {result.message}
            {result.ledger_rows_removed > 0 && (
              <span className="mt-1 block text-emerald-400/80">
                Ledger rows removed: {result.ledger_rows_removed}
              </span>
            )}
          </p>
        )}

        {!confirmOpen ? (
          <button
            type="button"
            disabled={pending || syncActive}
            onClick={() => setConfirmOpen(true)}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-red-500/40 px-4 py-2.5 text-sm text-red-400 transition hover:bg-red-500/10 disabled:opacity-50"
          >
            <Trash2 className="h-4 w-4" />
            Reset Cognee dataset
          </button>
        ) : (
          <div className="space-y-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
            <p className="text-xs text-red-300">
              This cannot be undone. All Cognee graph memory for this tenant will
              be deleted
              {clearTelemetry ? " and telemetry will be cleared" : ""}.
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={pending}
                onClick={() => void handleReset()}
                className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-red-500 disabled:opacity-50"
              >
                {pending && <Loader2 className="h-4 w-4 animate-spin" />}
                Yes, reset now
              </button>
              <button
                type="button"
                disabled={pending}
                onClick={() => setConfirmOpen(false)}
                className="rounded-lg border border-zinc-700 px-3 py-2 text-sm text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {syncActive && (
          <p className="text-xs text-zinc-500">
            Wait for active sync jobs to finish before resetting.
          </p>
        )}
      </div>
    </section>
  );
}
