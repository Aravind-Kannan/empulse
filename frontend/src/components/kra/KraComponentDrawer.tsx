"use client";

import { useMemo, useState } from "react";
import { Loader2, X } from "lucide-react";

import { assignKraBackup } from "@/lib/api";
import type { KraAnalyticsResponse, KraNode } from "@/lib/types";

interface KraComponentDrawerProps {
  component: KraNode;
  graph: KraAnalyticsResponse;
  onClose: () => void;
  onAssigned: (spofResolved: boolean) => void;
}

export function KraComponentDrawer({
  component,
  graph,
  onClose,
  onAssigned,
}: KraComponentDrawerProps) {
  const [backupEngineerId, setBackupEngineerId] = useState("");
  const [sharePct, setSharePct] = useState(20);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const linkedEngineerIds = useMemo(
    () =>
      new Set(
        graph.links
          .filter((link) => link.target === component.id)
          .map((link) => link.source),
      ),
    [graph.links, component.id],
  );

  const linkedEngineers = graph.nodes.filter(
    (node) => node.type === "engineer" && linkedEngineerIds.has(node.id),
  );

  const backupCandidates = graph.nodes.filter(
    (node) => node.type === "engineer" && !linkedEngineerIds.has(node.id),
  );

  async function handleAssign() {
    if (!backupEngineerId) return;
    setSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await assignKraBackup({
        component_id: component.id,
        employee_id: backupEngineerId,
        codebase_share_pct: sharePct,
      });
      setSuccess(
        result.is_spof_resolved
          ? "Backup engineer assigned. SPOF resolved."
          : "Backup engineer assigned.",
      );
      onAssigned(result.is_spof_resolved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Assignment failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label="Close drawer"
        className="fixed inset-0 z-40 bg-black/50"
        onClick={onClose}
      />
      <aside
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-zinc-800 bg-slate-950 shadow-2xl transition-transform duration-300 ease-out`}
      >
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-zinc-500">
              System Component
            </p>
            <h2 className="text-lg font-semibold text-zinc-100">
              {component.label}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-800"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto p-5">
          {component.is_spof && (
            <div className="rounded-lg border border-orange-500/40 bg-orange-500/10 px-4 py-3 text-sm text-orange-200">
              This component is a Single Point of Failure — only one engineer
              owns it. Assign a backup to reduce operational silo risk.
            </div>
          )}

          <section>
            <h3 className="mb-2 text-sm font-medium text-zinc-200">
              Description
            </h3>
            <p className="text-sm leading-relaxed text-zinc-400">
              {component.description || "No description available."}
            </p>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-medium text-zinc-200">
              Documentation
            </h3>
            <ul className="space-y-2">
              {(component.documentation_sources ?? []).map((source) => (
                <li
                  key={source}
                  className="rounded-lg border border-zinc-800 bg-zinc-900/50 px-3 py-2 text-sm text-zinc-300"
                >
                  {source}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-medium text-zinc-200">
              Current owners
            </h3>
            <ul className="space-y-1 text-sm text-zinc-400">
              {linkedEngineers.map((engineer) => (
                <li key={engineer.id}>
                  {engineer.label}
                  {engineer.role ? ` (${engineer.role})` : ""}
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
            <h3 className="mb-3 text-sm font-medium text-zinc-200">
              Assign backup engineer
            </h3>
            <div className="space-y-3">
              <select
                value={backupEngineerId}
                onChange={(e) => setBackupEngineerId(e.target.value)}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
              >
                <option value="">Select engineer…</option>
                {backupCandidates.map((engineer) => (
                  <option key={engineer.id} value={engineer.id}>
                    {engineer.label} ({engineer.role})
                  </option>
                ))}
              </select>
              <div>
                <label className="mb-1 block text-xs text-zinc-500">
                  Codebase share ({sharePct}%)
                </label>
                <input
                  type="range"
                  min={5}
                  max={50}
                  value={sharePct}
                  onChange={(e) => setSharePct(Number(e.target.value))}
                  className="w-full"
                />
              </div>
              {error && <p className="text-sm text-red-300">{error}</p>}
              {success && <p className="text-sm text-emerald-300">{success}</p>}
              <button
                type="button"
                disabled={!backupEngineerId || submitting}
                onClick={handleAssign}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-orange-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-orange-400 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                Map backup &amp; break silo
              </button>
            </div>
          </section>
        </div>
      </aside>
    </>
  );
}
