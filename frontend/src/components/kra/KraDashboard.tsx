"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import Link from "next/link";

import { fetchKraFileRisk, fetchKraGraph, fetchKraSummary, fetchOrgChart } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import type {
  KraAnalyticsResponse,
  KraFileRiskResponse,
  KraNode,
  KraSummaryResponse,
  OrgChartPayload,
} from "@/lib/types";

import { FileRiskMatrix } from "./FileRiskMatrix";
import { KraComponentDrawer } from "./KraComponentDrawer";
import { KraGraph } from "./KraGraph";
import { KraKpiStrip } from "./KraKpiStrip";

export function KraDashboard() {
  const searchParams = useSearchParams();
  const highlightId = searchParams.get("highlight");
  const filterParam = searchParams.get("filter");
  const { refreshMetrics, notifySpofResolved, operationalRevision } = useWorkspace();
  const [graph, setGraph] = useState<KraAnalyticsResponse | null>(null);
  const [summary, setSummary] = useState<KraSummaryResponse | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [criticalSpofFilter, setCriticalSpofFilter] = useState(
    filterParam === "spof",
  );
  const [selectedComponent, setSelectedComponent] = useState<KraNode | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const [fileRisk, setFileRisk] = useState<KraFileRiskResponse | null>(null);
  const [fileRiskLoading, setFileRiskLoading] = useState(false);
  const [matrixComponentId, setMatrixComponentId] = useState<string>("");
  const [orgChart, setOrgChart] = useState<OrgChartPayload | null>(null);

  const loadGraph = useCallback(async () => {
    const [graphData, summaryData] = await Promise.all([
      fetchKraGraph(),
      fetchKraSummary(),
    ]);
    setGraph(graphData);
    setSummary(summaryData);
    setSelectedComponent((prev) =>
      prev ? graphData.nodes.find((n) => n.id === prev.id) ?? null : null,
    );
    await refreshMetrics();
  }, [refreshMetrics]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (filterParam === "spof") {
      setCriticalSpofFilter(true);
    }
  }, [filterParam]);

  useEffect(() => {
    if (!mounted) return;

    let cancelled = false;
    setLoading(true);
    setSummaryLoading(true);

    Promise.all([fetchKraGraph(), fetchKraSummary()])
      .then(([graphData, summaryData]) => {
        if (!cancelled) {
          setGraph(graphData);
          setSummary(summaryData);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load KRA graph",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          setSummaryLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [mounted, operationalRevision]);

  useEffect(() => {
    if (!mounted || !graph || graph.nodes.length > 0) {
      setOrgChart(null);
      return;
    }

    let cancelled = false;
    fetchOrgChart()
      .then((data) => {
        if (!cancelled) setOrgChart(data);
      })
      .catch(() => {
        if (!cancelled) setOrgChart(null);
      });

    return () => {
      cancelled = true;
    };
  }, [mounted, graph]);

  useEffect(() => {
    if (!mounted || !graph || !highlightId) return;
    const node = graph.nodes.find(
      (entry) => entry.id === highlightId && entry.type === "component",
    );
    if (node) setSelectedComponent(node);
  }, [mounted, graph, highlightId]);

  const criticalSpofIds = useMemo(() => {
    if (!summary) return new Set<string>();
    return new Set(
      summary.critical_spof.components.map((row) => row.component_id),
    );
  }, [summary]);

  const highlightCriticalSpofIds = useMemo(
    () => (criticalSpofFilter ? criticalSpofIds : null),
    [criticalSpofFilter, criticalSpofIds],
  );

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

  const emptyStateMessage = useMemo(() => {
    if (!orgChart) {
      return {
        title: "No org chart data yet",
        body: "KRA needs system components and ownership assignments in Postgres. Integrations alone do not create the org graph.",
      };
    }

    const employeeCount = orgChart.employees.length;
    const componentCount = orgChart.components.length;
    const assignmentCount = orgChart.assignments.length;

    if (employeeCount > 0 && componentCount === 0) {
      return {
        title: "Employees imported — components missing",
        body: `You have ${employeeCount} employee${employeeCount === 1 ? "" : "s"} but 0 system components. Add components (e.g. Payments API, Auth Service), assign owners, then re-open KRA. GitHub/Notion/Jira syncs enrich metrics but do not replace the org chart.`,
      };
    }

    if (componentCount > 0 && assignmentCount === 0) {
      return {
        title: "Components exist — no ownership links",
        body: `You have ${componentCount} component${componentCount === 1 ? "" : "s"} but no assignments. Link engineers to components in Org workspace so KRA can draw the graph.`,
      };
    }

    if (employeeCount === 0 && componentCount === 0) {
      return {
        title: "Org chart not configured",
        body: "Import employees, components, and assignments under Org workspace. Then connect GitHub for bus factor and Notion for runbooks.",
      };
    }

    return {
      title: "Graph could not be built",
      body: "Org data exists but KRA returned an empty graph. Try refreshing after saving org workspace changes.",
    };
  }, [orgChart]);

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
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100">
          Knowledge Risk Assessment (KRA)
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Topological view of engineering dependencies and ownership silos.
        </p>
      </div>

      <KraKpiStrip
        criticalSpof={summary?.critical_spof ?? null}
        loading={summaryLoading}
        filterActive={criticalSpofFilter}
        onToggleFilter={() => setCriticalSpofFilter((active) => !active)}
      />

      {graph.nodes.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-700 bg-zinc-900/20 px-6 py-12 text-center">
          <p className="text-sm font-medium text-zinc-200">{emptyStateMessage.title}</p>
          <p className="mt-2 text-sm text-zinc-500">{emptyStateMessage.body}</p>
          <Link
            href="/settings/org-chart"
            className="mt-4 inline-block text-sm font-medium text-sky-400 hover:text-sky-300"
          >
            Open Org workspace →
          </Link>
        </div>
      ) : (
        <KraGraph
          graph={graph}
          selectedComponentId={selectedComponent?.id ?? null}
          highlightCriticalSpofIds={highlightCriticalSpofIds}
          onSelectComponent={(node) => {
            setSelectedComponent(node);
            if (node.type === "component") {
              setMatrixComponentId(node.id);
            }
          }}
        />
      )}

      {graph.nodes.length > 0 && (
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
      )}

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
