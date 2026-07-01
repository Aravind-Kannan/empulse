"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AlertTriangle, Loader2 } from "lucide-react";

import { fetchKraFileRisk, fetchKraGraph } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import type { KraAnalyticsResponse, KraFileRiskResponse, KraNode } from "@/lib/types";

import { FileRiskMatrix } from "./FileRiskMatrix";
import { KraComponentDrawer } from "./KraComponentDrawer";
import { KraGraph } from "./KraGraph";

export function KraDashboard() {
  const searchParams = useSearchParams();
  const highlightId = searchParams.get("highlight");
  const { refreshMetrics, notifySpofResolved, operationalRevision } = useWorkspace();
  const [graph, setGraph] = useState<KraAnalyticsResponse | null>(null);
  const [selectedComponent, setSelectedComponent] = useState<KraNode | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const [fileRisk, setFileRisk] = useState<KraFileRiskResponse | null>(null);
  const [fileRiskLoading, setFileRiskLoading] = useState(false);
  const [matrixComponentId, setMatrixComponentId] = useState<string>("");

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

  useEffect(() => {
    if (!mounted || !graph || !highlightId) return;
    const node = graph.nodes.find(
      (entry) => entry.id === highlightId && entry.type === "component",
    );
    if (node) setSelectedComponent(node);
  }, [mounted, graph, highlightId]);

  const componentNodes = useMemo(
    () => graph?.nodes.filter((node) => node.type === "component") ?? [],
    [graph],
  );

  useEffect(() => {
    if (!graph || componentNodes.length === 0) return;
    setMatrixComponentId((current) => {
      if (current && componentNodes.some((node) => node.id === current)) {
        return current;
      }
      if (highlightId && componentNodes.some((node) => node.id === highlightId)) {
        return highlightId;
      }
      if (selectedComponent?.type === "component") {
        return selectedComponent.id;
      }
      return componentNodes[0]?.id ?? "";
    });
  }, [graph, componentNodes, highlightId, selectedComponent]);

  useEffect(() => {
    if (!matrixComponentId) {
      setFileRisk(null);
      return;
    }

    let cancelled = false;
    setFileRiskLoading(true);
    fetchKraFileRisk(matrixComponentId)
      .then((data) => {
        if (!cancelled) setFileRisk(data);
      })
      .catch(() => {
        if (!cancelled) setFileRisk(null);
      })
      .finally(() => {
        if (!cancelled) setFileRiskLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [matrixComponentId, operationalRevision]);

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
        onSelectComponent={(node) => {
          setSelectedComponent(node);
          if (node.type === "component") {
            setMatrixComponentId(node.id);
          }
        }}
      />

      <div className="space-y-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-sm font-medium text-zinc-200">File risk matrix</h2>
          {componentNodes.length > 0 && (
            <select
              value={matrixComponentId}
              onChange={(event) => setMatrixComponentId(event.target.value)}
              className="rounded-md border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-xs text-zinc-300"
            >
              {componentNodes.map((node) => (
                <option key={node.id} value={node.id}>
                  {node.label}
                </option>
              ))}
            </select>
          )}
        </div>
        {fileRiskLoading ? (
          <div className="flex h-32 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/30 text-sm text-zinc-400">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Loading file risk…
          </div>
        ) : (
          <FileRiskMatrix
            files={fileRisk?.files ?? []}
            quadrantCounts={fileRisk?.quadrant_counts}
            crossTrainingPriority={fileRisk?.cross_training_priority}
            title={
              fileRisk?.component_name
                ? `File risk — ${fileRisk.component_name}`
                : "File risk matrix"
            }
          />
        )}
      </div>

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
