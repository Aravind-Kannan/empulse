"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { fetchIncidents, updateIncidentStatus } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import type {
  IncidentStatus,
  IncidentSummary,
  InvestigationDiagnostics,
} from "@/lib/types";

import { IncidentHistoryBar } from "./IncidentHistoryBar";
import { InvestigationChatPanel } from "./InvestigationChatPanel";
import { InvestigationContextPanel } from "./InvestigationContextPanel";
import { InvestigationDiagnosticsPanel } from "./InvestigationDiagnosticsPanel";

export function InvestigationDashboard() {
  const { refreshMetrics, notifyIncidentResolved } = useWorkspace();
  const [allIncidents, setAllIncidents] = useState<IncidentSummary[]>([]);
  const [activeFilter, setActiveFilter] = useState<IncidentStatus | "All">(
    "All",
  );
  const [activeIncident, setActiveIncident] = useState<IncidentSummary | null>(
    null,
  );
  const [diagnostics, setDiagnostics] =
    useState<InvestigationDiagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadIncidents = useCallback(async () => {
    const data = await fetchIncidents();
    setAllIncidents(data);
    setActiveIncident((prev) => {
      if (prev) {
        return data.find((item) => item.id === prev.id) ?? data[0] ?? null;
      }
      return (
        data.find((item) => item.status === "Investigating") ??
        data.find((item) => item.status === "Open") ??
        data[0] ??
        null
      );
    });
  }, []);

  useEffect(() => {
    fetchIncidents()
      .then((data) => {
        setAllIncidents(data);
        const initial =
          data.find((item) => item.status === "Investigating") ??
          data.find((item) => item.status === "Open") ??
          data[0] ??
          null;
        setActiveIncident(initial);
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load incidents"),
      )
      .finally(() => setLoading(false));
  }, []);

  const filteredIncidents =
    activeFilter === "All"
      ? allIncidents
      : allIncidents.filter((item) => item.status === activeFilter);

  async function handleStatusChange(status: string) {
    if (!activeIncident) return;
    const previousStatus = activeIncident.status;
    try {
      const updated = await updateIncidentStatus(
        activeIncident.id,
        status as IncidentStatus,
      );
      setActiveIncident(updated);
      await loadIncidents();
      if (
        (status === "Resolved" || status === "Closed") &&
        previousStatus !== "Resolved" &&
        previousStatus !== "Closed"
      ) {
        notifyIncidentResolved();
      } else {
        await refreshMetrics();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Status update failed");
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-zinc-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading investigation workspace…
      </div>
    );
  }

  if (error && allIncidents.length === 0) {
    return (
      <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">
        {error}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100">
          Incident Investigation (II)
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Multi-hop semantic graph workspace for root cause isolation.
        </p>
      </div>

      <IncidentHistoryBar
        incidents={filteredIncidents}
        activeFilter={activeFilter}
        activeIncidentId={activeIncident?.id ?? null}
        onFilterChange={setActiveFilter}
        onSelectIncident={setActiveIncident}
      />

      <div className="grid min-h-[620px] gap-4 xl:grid-cols-3">
        <InvestigationChatPanel
          incidentId={activeIncident?.id ?? null}
          onDiagnostics={setDiagnostics}
        />
        <InvestigationDiagnosticsPanel
          rootCause={diagnostics?.probable_root_cause ?? null}
          confidence={diagnostics?.confidence_score ?? null}
          workaround={diagnostics?.workaround ?? null}
          status={activeIncident?.status ?? "Open"}
          graphHops={diagnostics?.graph_hops ?? []}
          onStatusChange={handleStatusChange}
        />
        <InvestigationContextPanel
          smes={diagnostics?.smes ?? []}
          references={diagnostics?.references ?? []}
        />
      </div>
    </div>
  );
}
