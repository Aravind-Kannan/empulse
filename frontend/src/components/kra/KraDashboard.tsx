"use client";

import { useEffect, useMemo, useState } from "react";
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
import { KraKpiStrip, KraDocGapPanel } from "./KraKpiStrip";

export function KraDashboard() {
  const searchParams = useSearchParams();
  const highlightId = searchParams.get("highlight");
  const filterParam = searchParams.get("filter");
  const { operationalRevision } = useWorkspace();
  const [graph, setGraph] = useState<KraAnalyticsResponse | null>(null);
  const [summary, setSummary] = useState<KraSummaryResponse | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [criticalSpofFilter, setCriticalSpofFilter] = useState(
    filterParam === "spof",
  );
  const [docGapPanelOpen, setDocGapPanelOpen] = useState(false);
  const [selectedComponent, setSelectedComponent] = useState<KraNode | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const [fileRisk, setFileRisk] = useState<KraFileRiskResponse | null>(null);
  const [fileRiskLoading, setFileRiskLoading] = useState(false);
  const [orgChart, setOrgChart] = useState<OrgChartPayload | null>(null);

  const selectedComponentId =
    selectedComponent?.type === "component" ? selectedComponent.id : null;

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

  useEffect(() => {
    if (!selectedComponentId) {
      setFileRisk(null);
      return;
    }

    let cancelled = false;
    setFileRiskLoading(true);
    fetchKraFileRisk(selectedComponentId)
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
  }, [selectedComponentId, operationalRevision]);

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
        documentationCoverage={summary?.documentation_coverage ?? null}
        loading={summaryLoading}
        filterActive={criticalSpofFilter}
        onToggleFilter={() => setCriticalSpofFilter((active) => !active)}
        gapPanelOpen={docGapPanelOpen}
        onToggleGapPanel={() => setDocGapPanelOpen((open) => !open)}
      />

      <KraDocGapPanel
        covered={summary?.documentation_coverage?.covered_components ?? []}
        gaps={summary?.documentation_coverage?.gap_components ?? []}
        open={docGapPanelOpen}
        onClose={() => setDocGapPanelOpen(false)}
        onSelectComponent={(componentId) => {
          const node = graph.nodes.find(
            (entry) => entry.id === componentId && entry.type === "component",
          );
          if (node) {
            setSelectedComponent(node);
            setDocGapPanelOpen(false);
          }
        }}
      />

      {graph.nodes.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-700 bg-zinc-900/20 px-6 py-12 text-center">
          <p className="text-sm font-medium text-zinc-200">{emptyStateMessage.title}</p>
          <p className="mt-2 text-sm text-zinc-500">{emptyStateMessage.body}</p>
          <Link
            href="/settings/org-chart"
            className="mt-4 inline-block text-sm font-medium text-sky-400 hover:text-sky-300"
          >
            Open Org Hub →
          </Link>
        </div>
      ) : (
        <div
          className={`flex min-h-[420px] items-stretch overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-950/40 shadow-sm ring-1 ring-white/[0.03] ${
            selectedComponent ? "divide-x divide-zinc-800/70" : ""
          }`}
        >
          <div className="min-w-0 flex-1">
            <KraGraph
              graph={graph}
              selectedComponentId={selectedComponent?.id ?? null}
              highlightCriticalSpofIds={highlightCriticalSpofIds}
              detailOpen={!!selectedComponent}
              splitView={!!selectedComponent}
              onSelectComponent={(node) => setSelectedComponent(node)}
            />
          </div>
          {selectedComponent && (
            <KraComponentDrawer
              component={selectedComponent}
              graph={graph}
              onClose={() => setSelectedComponent(null)}
              className="w-[min(100%,400px)] shrink-0"
            />
          )}
        </div>
      )}

      {graph.nodes.length > 0 && selectedComponentId && (
        <div className="space-y-3">
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
                  ? `${fileRisk.component_name} — file ownership`
                  : "File ownership risk"
              }
            />
          )}
        </div>
      )}
    </div>
  );
}
