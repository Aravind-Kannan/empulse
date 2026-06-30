"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Loader2, Play, Terminal } from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import { streamNotionSimulation } from "@/lib/api";
import type { SimulationGraphResult, SimulationLogEntry } from "@/lib/types";

import { SimulationGraphMap } from "./SimulationGraphMap";

export function GraphDebuggerPage() {
  const { config } = useIntegrations();
  const [logs, setLogs] = useState<SimulationLogEntry[]>([]);
  const [running, setRunning] = useState(false);
  const [graph, setGraph] = useState<SimulationGraphResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRunSimulation() {
    setRunning(true);
    setError(null);
    setLogs([]);
    setGraph(null);

    const databaseId = config.notion.databaseIds.split(",")[0]?.trim() ?? "";

    try {
      await streamNotionSimulation(
        {
          notion_integration_token: config.notion.integrationToken,
          notion_database_id: databaseId,
          ollama_model: "llama3.2",
        },
        (entry) => {
          if (entry.type === "log") {
            setLogs((prev) => [...prev, entry]);
          } else if (entry.type === "result") {
            setGraph({
              nodes: entry.nodes ?? [],
              edges: entry.edges ?? [],
              cognee_dataset: entry.cognee_dataset ?? "",
              documents_generated: entry.documents_generated ?? 0,
              notion_pages_written: entry.notion_pages_written ?? 0,
              success: entry.success ?? false,
            });
          }
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8 p-8">
      <header className="space-y-4">
        <Link
          href="/settings"
          className="inline-flex items-center gap-1.5 text-sm text-zinc-500 transition hover:text-zinc-300"
        >
          <ArrowLeft className="h-4 w-4" />
          Settings
        </Link>
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900">
            <Terminal className="h-6 w-6 text-zinc-300" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-zinc-100">
              Graph Debugger
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-zinc-400">
              End-to-end Notion simulation: Ollama document generation, Notion
              sync, and Cognee graph extraction with live pipeline tracing.
            </p>
          </div>
        </div>
      </header>

      <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
        <button
          type="button"
          disabled={running}
          onClick={() => void handleRunSimulation()}
          className="inline-flex items-center gap-2 rounded-lg bg-zinc-100 px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white disabled:opacity-50"
        >
          {running ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          Run End-to-End Notion → Cognee Simulation Pipeline
        </button>
        {!config.notion.integrationToken && (
          <p className="mt-3 text-xs text-amber-400">
            No Notion token configured — pipeline will use a local mock Notion
            store. Add a token under Settings → Integrations for live API writes.
          </p>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
          Pipeline log
        </h2>
        <div className="min-h-48 rounded-xl border border-zinc-800 bg-black/80 p-4 font-mono text-xs text-zinc-300">
          {logs.length === 0 && !running && (
            <p className="text-zinc-600">
              Waiting to run simulation…
            </p>
          )}
          {logs.map((entry, index) => (
            <p
              key={`${entry.message}-${index}`}
              className={
                entry.status === "error"
                  ? "text-red-400"
                  : entry.status === "success"
                    ? "text-emerald-400"
                    : entry.status === "running"
                      ? "text-sky-400"
                      : "text-zinc-300"
              }
            >
              {entry.message}
            </p>
          ))}
          {running && (
            <p className="mt-2 animate-pulse text-sky-400">▌ processing…</p>
          )}
        </div>
        {error && (
          <p className="text-sm text-red-400">{error}</p>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
            Extracted graph
          </h2>
          {graph?.cognee_dataset && (
            <p className="text-xs text-zinc-500">
              Dataset: {graph.cognee_dataset} · {graph.nodes.length} nodes ·{" "}
              {graph.edges.length} edges
            </p>
          )}
        </div>
        <SimulationGraphMap
          nodes={graph?.nodes ?? []}
          edges={graph?.edges ?? []}
        />
        {graph && graph.edges.length > 0 && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-950/50 p-4">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
              Triple preview
            </p>
            <ul className="space-y-1 font-mono text-xs text-zinc-400">
              {graph.edges.slice(0, 12).map((edge, index) => {
                const source =
                  graph.nodes.find((node) => node.id === edge.source)?.label ??
                  edge.source;
                const target =
                  graph.nodes.find((node) => node.id === edge.target)?.label ??
                  edge.target;
                return (
                  <li key={`${edge.source}-${edge.target}-${index}`}>
                    {source} → {edge.relationship} → {target}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}
