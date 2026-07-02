"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";

import { fetchIncidents, updateIncidentStatus } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { useIncidentInvestigation } from "@/hooks/useIncidentInvestigation";
import type { IncidentStatus, IncidentSummary } from "@/lib/types";

import { IncidentHistoryBar } from "./IncidentHistoryBar";
import { InvestigationChatPanel } from "./InvestigationChatPanel";
import { InvestigationContextPanel } from "./InvestigationContextPanel";
import { InvestigationDiagnosticsPanel } from "./InvestigationDiagnosticsPanel";

export function InvestigationDashboard() {
  const { refreshMetrics, notifyIncidentResolved } = useWorkspace();
  const [allIncidents, setAllIncidents] = useState<IncidentSummary[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [feedWarnings, setFeedWarnings] = useState<string[]>([]);
  const [sourcesConnected, setSourcesConnected] = useState<Record<string, boolean>>(
    {},
  );
  const [activeFilter, setActiveFilter] = useState<IncidentStatus | "All">("All");
  const [activeIncident, setActiveIncident] = useState<IncidentSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [refreshingBriefing, setRefreshingBriefing] = useState(false);

  const {
    diagnostics,
    briefingStatus,
    chatMessages,
    briefingError,
    loadBriefing,
    invalidateIncident,
    syncCacheFromFeed,
    updateChatMessages,
  } = useIncidentInvestigation(activeIncident);

  const applyFeed = useCallback(
    (data: Awaited<ReturnType<typeof fetchIncidents>>) => {
      syncCacheFromFeed(data.incidents);
      setAllIncidents(data.incidents);
      setSuggestions(
        buildSuggestionsForIncident(data.suggestions, data.incidents, null),
      );
      setFeedWarnings(data.warnings);
      setSourcesConnected(data.sources_connected);
      setActiveIncident((prev) => {
        if (prev) {
          return (
            data.incidents.find((item) => item.id === prev.id) ??
            data.incidents[0] ??
            null
          );
        }
        return (
          data.incidents.find((item) => item.status === "Investigating") ??
          data.incidents.find((item) => item.status === "Open") ??
          data.incidents[0] ??
          null
        );
      });
    },
    [syncCacheFromFeed],
  );

  const loadIncidents = useCallback(async () => {
    const data = await fetchIncidents();
    applyFeed(data);
  }, [applyFeed]);

  useEffect(() => {
    fetchIncidents()
      .then(applyFeed)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load incidents"),
      )
      .finally(() => setLoading(false));
  }, [applyFeed]);

  const filteredIncidents =
    activeFilter === "All"
      ? allIncidents
      : allIncidents.filter((item) => item.status === activeFilter);

  async function handleStatusChange(status: string) {
    if (!activeIncident || statusUpdating) return;
    const previousStatus = activeIncident.status;
    setStatusUpdating(true);
    setError(null);
    try {
      const updated = await updateIncidentStatus(
        activeIncident.id,
        status as IncidentStatus,
      );
      invalidateIncident(activeIncident.id);
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
    } finally {
      setStatusUpdating(false);
    }
  }

  async function handleRefreshBriefing() {
    if (!activeIncident || refreshingBriefing) return;
    setRefreshingBriefing(true);
    invalidateIncident(activeIncident.id);
    try {
      await loadBriefing(activeIncident, { force: true });
    } finally {
      setRefreshingBriefing(false);
    }
  }

  function handleSelectIncident(incident: IncidentSummary) {
    setActiveIncident(incident);
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-zinc-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading incidents…
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

  const chatSuggestions = buildSuggestionsForIncident(
    suggestions,
    allIncidents,
    activeIncident,
  );

  const panelError = error ?? briefingError;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100">
          Incident Investigation
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Active issues from Jira and Slack incident channels.
        </p>
      </div>

      {panelError && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {panelError}
        </div>
      )}

      <IncidentHistoryBar
        incidents={filteredIncidents}
        activeFilter={activeFilter}
        activeIncidentId={activeIncident?.id ?? null}
        sourcesConnected={sourcesConnected}
        warnings={feedWarnings}
        onFilterChange={setActiveFilter}
        onSelectIncident={handleSelectIncident}
      />

      <div className="grid min-h-[620px] gap-4 xl:grid-cols-3">
        <InvestigationChatPanel
          incidentId={activeIncident?.id ?? null}
          activeIncidentTitle={activeIncident?.title ?? null}
          suggestions={chatSuggestions}
          messages={chatMessages}
          onMessagesChange={(messages) => {
            if (activeIncident) {
              updateChatMessages(activeIncident.id, messages);
            }
          }}
        />
        <InvestigationDiagnosticsPanel
          rootCause={diagnostics?.probable_root_cause ?? null}
          confidence={diagnostics?.confidence_score ?? null}
          workaround={diagnostics?.workaround ?? null}
          status={activeIncident?.status ?? "Open"}
          graphHops={diagnostics?.graph_hops ?? []}
          statusUpdating={statusUpdating}
          analyzing={briefingStatus !== null || refreshingBriefing}
          analysisMessage={briefingStatus?.message ?? null}
          onStatusChange={handleStatusChange}
          onRefresh={activeIncident ? handleRefreshBriefing : undefined}
          refreshing={refreshingBriefing}
        />
        <InvestigationContextPanel
          smes={diagnostics?.smes ?? []}
          slackThreads={diagnostics?.slack_threads ?? []}
          jiraTickets={diagnostics?.jira_tickets ?? []}
          notionPages={diagnostics?.notion_pages ?? []}
          analyzing={briefingStatus !== null || refreshingBriefing}
          analysisMessage={briefingStatus?.message ?? null}
        />
      </div>
    </div>
  );
}

function buildSuggestionsForIncident(
  base: string[],
  incidents: IncidentSummary[],
  active: IncidentSummary | null,
): string[] {
  if (active) {
    const scoped: string[] = [];
    if (active.source === "jira" && active.jira_id) {
      scoped.push(`What is the root cause of ${active.jira_id}?`);
      scoped.push(`Who should own ${active.jira_id}?`);
      scoped.push(`What is the workaround for ${active.title}?`);
    } else if (active.source === "slack" && active.channel_name) {
      scoped.push(`What is happening in #${active.channel_name}?`);
      scoped.push(`Who was paged for this thread?`);
    }
    scoped.push(`Summarize impact for: ${active.title}`);
    return [...new Set([...scoped, ...base])].slice(0, 6);
  }
  return base.slice(0, 6);
}
