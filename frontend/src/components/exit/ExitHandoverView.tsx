"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Copy, Download, Loader2 } from "lucide-react";

import { fetchExitEmployees, fetchHandover } from "@/lib/api";
import type { EmployeeOption, HandoverResponse } from "@/lib/types";

function ExitHandoverContent() {
  const searchParams = useSearchParams();
  const employeeParam = searchParams.get("employee");
  const prefillEra = searchParams.get("prefill") === "era";

  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [handover, setHandover] = useState<HandoverResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchExitEmployees()
      .then((data) => {
        setEmployees(data);
        if (employeeParam && data.some((emp) => emp.id === employeeParam)) {
          setSelectedId(employeeParam);
        } else if (data[0]) {
          setSelectedId(data[0].id);
        }
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load employees"),
      )
      .finally(() => setLoading(false));
  }, [employeeParam]);

  useEffect(() => {
    if (!selectedId) return;

    setGenerating(true);
    setError(null);
    fetchHandover(selectedId, { prefillEra })
      .then(setHandover)
      .catch((err) => {
        setHandover(null);
        setError(err instanceof Error ? err.message : "Handover failed");
      })
      .finally(() => setGenerating(false));
  }, [selectedId, prefillEra]);

  async function handleCopy() {
    if (!handover) return;
    await navigator.clipboard.writeText(handover.markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDownload() {
    if (!handover) return;
    const blob = new Blob([handover.markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = handover.filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-zinc-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading employees…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100">
          Employee Exit (EE)
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Generate a Cognee-powered handover asset pack for departing engineers.
        </p>
      </div>

      {prefillEra ? (
        <div className="rounded-lg border border-violet-500/40 bg-violet-500/10 p-4 text-sm text-violet-100">
          <p className="font-medium">Pre-filled from ERA risk assessment</p>
          {handover?.era_computed_at ? (
            <p className="mt-1 text-xs text-violet-200/80">
              ERA data computed at{" "}
              {new Date(handover.era_computed_at).toLocaleString()}
              {handover.era_risk_score != null
                ? ` — risk score ${Math.round(handover.era_risk_score)}%`
                : ""}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label className="mb-1.5 block text-sm text-zinc-400">
            Select engineer
          </label>
          <select
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
          >
            {employees.map((emp) => (
              <option key={emp.id} value={emp.id}>
                {emp.name} ({emp.role})
              </option>
            ))}
          </select>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleCopy}
            disabled={!handover || generating}
            className="flex items-center gap-2 rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 transition hover:bg-zinc-900 disabled:opacity-50"
          >
            <Copy className="h-4 w-4" />
            {copied ? "Copied!" : "Copy"}
          </button>
          <button
            type="button"
            onClick={handleDownload}
            disabled={!handover || generating}
            className="flex items-center gap-2 rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-white disabled:opacity-50"
          >
            <Download className="h-4 w-4" />
            Download pack
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/30">
        <div className="border-b border-zinc-800 px-4 py-3 text-xs text-zinc-500">
          {generating
            ? "Querying Cognee knowledge graph…"
            : handover
              ? `Preview — ${handover.filename}`
              : "Select an employee to generate handover"}
        </div>
        <pre className="max-h-[520px] overflow-auto p-5 text-sm leading-relaxed text-zinc-300 whitespace-pre-wrap font-mono">
          {generating ? "Loading…" : handover?.markdown ?? ""}
        </pre>
      </div>
    </div>
  );
}

function ExitHandoverFallback() {
  return (
    <div className="flex h-64 items-center justify-center text-zinc-400">
      <Loader2 className="mr-2 h-5 w-5 animate-spin" />
      Loading exit handover…
    </div>
  );
}

export function ExitHandoverView() {
  return (
    <Suspense fallback={<ExitHandoverFallback />}>
      <ExitHandoverContent />
    </Suspense>
  );
}
