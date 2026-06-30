"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";

import { fetchKraGraph } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import type { KraAnalyticsResponse, KraNode } from "@/lib/types";

import { KraComponentDrawer } from "./KraComponentDrawer";
import { KraGraph } from "./KraGraph";

export function KraDashboard() {
  const { refreshMetrics, notifySpofResolved, operationalRevision } = useWorkspace();
  const [graph, setGraph] = useState<KraAnalyticsResponse | null>(null);
  const [selectedComponent, setSelectedComponent] = useState<KraNode | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  const loadGraph = useCallback(async () => {
    const data = await fetchKraGraph();
    setGraph(data);
    setSelectedComponent((prev) =>
      prev ? data.nodes.find((n) => n.id === prev.id) ?? null : null,
    );
    await refreshMetrics();
  }, [refreshMetrics]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;

    let cancelled = false;
    setLoading(true);
    fetchKraGraph()
      .then((data) => {
        if (!cancelled) setGraph(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load KRA graph",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [mounted, operationalRevision]);

  const spofCount = useMemo(
    () => graph?.nodes.filter((n) => n.type === "component" && n.is_spof).length ?? 0,
    [graph],
  );

  if (!mounted || loading) {
    return (
      <div className="flex h-64 items-center justify-center text-zinc-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading knowledge graph…
      </div>
    );
  }

  if (error || !graph) {
    return (
      <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">
        {error ?? "No graph data available"}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">
            Knowledge Risk Assessment (KRA)
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Topological view of engineering dependencies and ownership silos.
          </p>
        </div>
        {spofCount > 0 && (
          <div className="inline-flex items-center gap-2 rounded-lg border border-orange-500/40 bg-orange-500/10 px-3 py-2 text-sm text-orange-200">
            <AlertTriangle className="h-4 w-4" />
            {spofCount} SPOF component{spofCount === 1 ? "" : "s"} detected
          </div>
        )}
      </div>

      <KraGraph
        graph={graph}
        selectedComponentId={selectedComponent?.id ?? null}
        onSelectComponent={setSelectedComponent}
      />

      {selectedComponent && (
        <KraComponentDrawer
          component={selectedComponent}
          graph={graph}
          onClose={() => setSelectedComponent(null)}
          onAssigned={(spofResolved) => {
            if (spofResolved) notifySpofResolved();
            void loadGraph();
          }}
        />
      )}
    </div>
  );
}
