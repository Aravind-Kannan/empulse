"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";

import { fetchIncidents, updateIncidentStatus } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import {
  defaultChatWelcome,
  defaultChatWelcomeNoIncident,
  type InvestigationChatMessage,
} from "@/hooks/useIncidentInvestigation";
import type {
  IncidentStatus,
  IncidentSummary,
  InvestigationAnalysisStatus,
  InvestigationDiagnostics,
} from "@/lib/types";

import { IncidentHistoryBar } from "./IncidentHistoryBar";
import { InvestigationChatPanel } from "./InvestigationChatPanel";
import { InvestigationContextPanel } from "./InvestigationContextPanel";
import { InvestigationDiagnosticsPanel } from "./InvestigationDiagnosticsPanel";
import {
  createBriefingFetcher,
  defaultWorkspaceChatHistory,
  PREFETCH_CONCURRENCY,
  type CachedWorkspace,
  type IncidentSyncStatus,
} from "./investigation-prefetch";

const INITIAL_PREFETCH_COUNT = 3;

export function InvestigationDashboard() {
  const { refreshMetrics, notifyIncidentResolved } = useWorkspace();
  const [allIncidents, setAllIncidents] = useState<IncidentSummary[]>([]);
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

  const [workspaceCache, setWorkspaceCache] = useState<
    Record<string, CachedWorkspace>
  >({});
  const workspaceCacheRef = useRef<Record<string, CachedWorkspace>>({});
  const fetchGenRef = useRef(0);
  const briefingFetcherRef = useRef(createBriefingFetcher());

  const [syncStatus, setSyncStatus] = useState<Record<string, IncidentSyncStatus>>(
    {},
  );
  const prefetchQueueRef = useRef<string[]>([]);
  const prefetchQueuedRef = useRef<Set<string>>(new Set());
  const prefetchRunningRef = useRef(0);
  const allIncidentsRef = useRef<IncidentSummary[]>([]);

  const [diagnostics, setDiagnostics] =
    useState<InvestigationDiagnostics | null>(null);
  const [diagnosticsIncidentId, setDiagnosticsIncidentId] = useState<string | null>(
    null,
  );
  const [chatMessages, setChatMessages] = useState<InvestigationChatMessage[]>(
    defaultChatWelcomeNoIncident(),
  );
  const [briefingStatus, setBriefingStatus] =
    useState<InvestigationAnalysisStatus | null>(null);
  const [briefingError, setBriefingError] = useState<string | null>(null);

  const writeWorkspaceCache = useCallback(
    (incidentId: string, entry: CachedWorkspace) => {
      workspaceCacheRef.current = {
        ...workspaceCacheRef.current,
        [incidentId]: entry,
      };
      setWorkspaceCache({ ...workspaceCacheRef.current });
      setSyncStatus((prev) => ({ ...prev, [incidentId]: "ready" }));
    },
    [],
  );

  const readWorkspaceCache = useCallback(
    (incidentId: string): CachedWorkspace | undefined =>
      workspaceCacheRef.current[incidentId],
    [],
  );

  const setIncidentSyncStatus = useCallback(
    (incidentId: string, status: IncidentSyncStatus) => {
      setSyncStatus((prev) => ({ ...prev, [incidentId]: status }));
    },
    [],
  );

  const restoreWorkspaceFromCache = useCallback(
    (incident: IncidentSummary): boolean => {
      const cached = readWorkspaceCache(incident.id);
      if (!cached?.diagnostics) return false;
      setDiagnostics(cached.diagnostics);
      setDiagnosticsIncidentId(incident.id);
      setChatMessages(cached.chatHistory);
      setBriefingError(null);
      setBriefingStatus(null);
      setIncidentSyncStatus(incident.id, "ready");
      return true;
    },
    [readWorkspaceCache, setIncidentSyncStatus],
  );

  const persistBriefingResult = useCallback(
    (incidentId: string, nextDiagnostics: InvestigationDiagnostics) => {
      const chatHistory = defaultWorkspaceChatHistory(
        incidentId,
        workspaceCacheRef.current,
      );
      writeWorkspaceCache(incidentId, {
        diagnostics: nextDiagnostics,
        chatHistory,
      });
      return chatHistory;
    },
    [writeWorkspaceCache],
  );

  const runPrefetch = useCallback(
    async (incidentId: string) => {
      if (readWorkspaceCache(incidentId)?.diagnostics) {
        setIncidentSyncStatus(incidentId, "ready");
        return;
      }
      if (briefingFetcherRef.current.isInFlight(incidentId)) {
        return;
      }

      setIncidentSyncStatus(incidentId, "loading");

      try {
        const nextDiagnostics =
          await briefingFetcherRef.current.fetchBriefing(incidentId);
        if (!nextDiagnostics) {
          setIncidentSyncStatus(incidentId, "error");
          return;
        }
        persistBriefingResult(incidentId, nextDiagnostics);
      } catch {
        setIncidentSyncStatus(incidentId, "error");
      }
    },
    [persistBriefingResult, readWorkspaceCache, setIncidentSyncStatus],
  );

  const drainPrefetchQueue = useCallback(() => {
    while (
      prefetchRunningRef.current < PREFETCH_CONCURRENCY &&
      prefetchQueueRef.current.length > 0
    ) {
      const incidentId = prefetchQueueRef.current.shift();
      if (!incidentId) continue;

      prefetchQueuedRef.current.delete(incidentId);

      if (readWorkspaceCache(incidentId)?.diagnostics) {
        setIncidentSyncStatus(incidentId, "ready");
        continue;
      }
      if (briefingFetcherRef.current.isInFlight(incidentId)) {
        continue;
      }

      prefetchRunningRef.current += 1;
      void runPrefetch(incidentId).finally(() => {
        prefetchRunningRef.current -= 1;
        drainPrefetchQueue();
      });
    }
  }, [readWorkspaceCache, runPrefetch, setIncidentSyncStatus]);

  const enqueuePrefetch = useCallback(
    (incidentId: string) => {
      if (!incidentId) return;
      if (readWorkspaceCache(incidentId)?.diagnostics) {
        setIncidentSyncStatus(incidentId, "ready");
        return;
      }
      if (
        briefingFetcherRef.current.isInFlight(incidentId) ||
        prefetchQueuedRef.current.has(incidentId)
      ) {
        return;
      }

      prefetchQueuedRef.current.add(incidentId);
      prefetchQueueRef.current.push(incidentId);
      drainPrefetchQueue();
    },
    [drainPrefetchQueue, readWorkspaceCache, setIncidentSyncStatus],
  );

  const loadWorkspaceForIncident = useCallback(
    async (
      incident: IncidentSummary,
      options?: { force?: boolean; gen?: number },
    ) => {
      const gen = options?.gen ?? fetchGenRef.current;

      if (!options?.force) {
        if (restoreWorkspaceFromCache(incident)) {
          return;
        }
      } else {
        delete workspaceCacheRef.current[incident.id];
        setWorkspaceCache({ ...workspaceCacheRef.current });
      }

      setBriefingError(null);
      if (options?.force || !readWorkspaceCache(incident.id)) {
        setDiagnostics(null);
        setDiagnosticsIncidentId(null);
      }

      setIncidentSyncStatus(incident.id, "loading");

      try {
        const nextDiagnostics = await briefingFetcherRef.current.fetchBriefing(
          incident.id,
          {
            onStatus: (status) => {
              if (fetchGenRef.current === gen) {
                setBriefingStatus(status);
              }
            },
            onDiagnostics: (diag) => {
              if (fetchGenRef.current === gen) {
                setDiagnostics(diag);
                setDiagnosticsIncidentId(incident.id);
              }
            },
          },
          { force: options?.force },
        );

        if (fetchGenRef.current !== gen) return;

        if (!nextDiagnostics) {
          setBriefingError("Failed to load incident analysis.");
          setIncidentSyncStatus(incident.id, "error");
          return;
        }

        const chatHistory = persistBriefingResult(incident.id, nextDiagnostics);
        setDiagnostics(nextDiagnostics);
        setDiagnosticsIncidentId(incident.id);
        setChatMessages(chatHistory);
      } catch (err) {
        if (fetchGenRef.current !== gen) return;
        setBriefingError(
          err instanceof Error ? err.message : "Failed to load incident briefing",
        );
        setIncidentSyncStatus(incident.id, "error");
        if (!readWorkspaceCache(incident.id)) {
          setDiagnostics(null);
          setDiagnosticsIncidentId(null);
        }
      } finally {
        if (fetchGenRef.current === gen) {
          setBriefingStatus(null);
        }
      }
    },
    [
      persistBriefingResult,
      readWorkspaceCache,
      restoreWorkspaceFromCache,
      setIncidentSyncStatus,
    ],
  );

  const applyFeed = useCallback(
    (data: Awaited<ReturnType<typeof fetchIncidents>>) => {
      setAllIncidents(data.incidents);
      allIncidentsRef.current = data.incidents;
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
    [],
  );

  useEffect(() => {
    fetchIncidents()
      .then(applyFeed)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load incidents"),
      )
      .finally(() => setLoading(false));
  }, [applyFeed]);

  useEffect(() => {
    if (!activeIncident) {
      setDiagnostics(null);
      setDiagnosticsIncidentId(null);
      setChatMessages(defaultChatWelcomeNoIncident());
      setBriefingStatus(null);
      setBriefingError(null);
      return;
    }

    if (restoreWorkspaceFromCache(activeIncident)) {
      return;
    }

    setDiagnostics(null);
    setDiagnosticsIncidentId(null);
    setBriefingStatus(null);
    setChatMessages(defaultChatWelcome());
    void loadWorkspaceForIncident(activeIncident);
  }, [activeIncident?.id, loadWorkspaceForIncident, restoreWorkspaceFromCache]);

  const filteredIncidents =
    activeFilter === "All"
      ? allIncidents
      : allIncidents.filter((item) => item.status === activeFilter);

  useEffect(() => {
    allIncidentsRef.current = allIncidents;
  }, [allIncidents]);

  useEffect(() => {
    if (loading) return;

    const filtered =
      activeFilter === "All"
        ? allIncidents
        : allIncidents.filter((item) => item.status === activeFilter);

    const seedIds = new Set<string>();
    filtered.slice(0, INITIAL_PREFETCH_COUNT).forEach((incident) => {
      seedIds.add(incident.id);
    });
    if (activeIncident) {
      seedIds.add(activeIncident.id);
    }
    seedIds.forEach((id) => enqueuePrefetch(id));
  }, [activeIncident?.id, activeFilter, allIncidents, loading, enqueuePrefetch]);

  const handleIncidentVisible = useCallback(
    (incidentId: string) => {
      enqueuePrefetch(incidentId);
    },
    [enqueuePrefetch],
  );

  function handleSelectIncident(incident: IncidentSummary) {
    if (incident.id === activeIncident?.id) return;
    fetchGenRef.current += 1;
    setBriefingError(null);
    setDiagnostics(null);
    setDiagnosticsIncidentId(null);
    setBriefingStatus(null);
    setActiveIncident(incident);
  }

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
      setActiveIncident(updated);
      setAllIncidents((prev) =>
        prev.map((item) => (item.id === updated.id ? updated : item)),
      );

      delete workspaceCacheRef.current[updated.id];
      setWorkspaceCache({ ...workspaceCacheRef.current });
      setIncidentSyncStatus(updated.id, "idle");
      enqueuePrefetch(updated.id);

      if (activeIncident.id === updated.id) {
        void loadWorkspaceForIncident(updated, { force: true });
      }

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
    try {
      await loadWorkspaceForIncident(activeIncident, { force: true });
    } finally {
      setRefreshingBriefing(false);
    }
  }

  function handleChatMessagesChange(messages: InvestigationChatMessage[]) {
    if (!activeIncident) return;
    setChatMessages(messages);
    const cached = readWorkspaceCache(activeIncident.id);
    writeWorkspaceCache(activeIncident.id, {
      chatHistory: messages,
      diagnostics: cached?.diagnostics ?? diagnostics,
    });
  }

  const syncingCount = Object.values(syncStatus).filter(
    (status) => status === "loading",
  ).length;

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

  const chatSuggestions = buildChatSuggestions(allIncidents, activeIncident);

  const visibleDiagnostics =
    activeIncident && diagnosticsIncidentId === activeIncident.id
      ? diagnostics
      : null;

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
        syncStatus={syncStatus}
        syncingCount={syncingCount}
        sourcesConnected={sourcesConnected}
        warnings={feedWarnings}
        onFilterChange={setActiveFilter}
        onSelectIncident={handleSelectIncident}
        onIncidentVisible={handleIncidentVisible}
      />

      <div className="grid h-[720px] gap-6 xl:grid-cols-3">
        <InvestigationChatPanel
          incidentId={activeIncident?.id ?? null}
          activeIncidentTitle={activeIncident?.title ?? null}
          suggestions={chatSuggestions}
          messages={chatMessages}
          onMessagesChange={handleChatMessagesChange}
        />
        <InvestigationDiagnosticsPanel
          rootCause={visibleDiagnostics?.probable_root_cause ?? null}
          confidence={visibleDiagnostics?.confidence_score ?? null}
          workaround={visibleDiagnostics?.workaround ?? null}
          workaroundAvailable={
            visibleDiagnostics
              ? (visibleDiagnostics.workaround_available ??
                (!visibleDiagnostics.workaround.startsWith(
                  "No workaround or solution",
                ) &&
                  !visibleDiagnostics.workaround.startsWith(
                    "No explicit workaround",
                  )))
              : false
          }
          status={activeIncident?.status ?? "Open"}
          statusUpdating={statusUpdating}
          analyzing={briefingStatus !== null || refreshingBriefing}
          analysisMessage={briefingStatus?.message ?? null}
          onStatusChange={handleStatusChange}
          onRefresh={activeIncident ? handleRefreshBriefing : undefined}
          refreshing={refreshingBriefing}
        />
        <InvestigationContextPanel
          smes={visibleDiagnostics?.smes ?? []}
          slackThreads={visibleDiagnostics?.slack_threads ?? []}
          jiraTickets={visibleDiagnostics?.jira_tickets ?? []}
          notionPages={visibleDiagnostics?.notion_pages ?? []}
          analyzing={briefingStatus !== null || refreshingBriefing}
          analysisMessage={briefingStatus?.message ?? null}
        />
      </div>
    </div>
  );
}

function buildChatSuggestions(
  incidents: IncidentSummary[],
  active: IncidentSummary | null,
): string[] {
  if (active) {
    return buildActiveIncidentSuggestions(active);
  }
  if (incidents.length === 0) {
    return [
      "What open incidents need attention right now?",
      "Which component is most at risk this week?",
      "Who are the on-call experts for the latest outage?",
    ];
  }
  const preferred =
    incidents.find((item) => item.status === "Investigating") ??
    incidents.find((item) => item.status === "Open") ??
    incidents[0];
  return buildActiveIncidentSuggestions(preferred);
}

function buildActiveIncidentSuggestions(active: IncidentSummary): string[] {
  const scoped: string[] = [];

  if (active.source === "jira" && active.jira_id) {
    scoped.push(`What is the root cause of ${active.jira_id}?`);
    scoped.push(`Who should own ${active.jira_id}?`);
    scoped.push(`What is the workaround for ${active.jira_id}?`);
  } else if (active.source === "slack") {
    const channel =
      active.channel_name?.replace(/^#/, "") || active.system_scope || "incidents";
    scoped.push(`What is happening in #${channel}?`);
    scoped.push(`Who was paged for the #${channel} thread?`);
  } else if (active.jira_id) {
    scoped.push(`What is the root cause of ${active.jira_id}?`);
    scoped.push(`Who should own ${active.jira_id}?`);
  }

  scoped.push(`Summarize impact for: ${active.title}`);
  return [...new Set(scoped)].slice(0, 6);
}
