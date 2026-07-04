"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";

import { PanelDataLoader } from "@/components/ui/PanelDataLoader";

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
  InvestigationBaseMetadata,
  InvestigationDiagnostics,
  CachedInvestigationData,
} from "@/lib/types";

import { IncidentHistoryBar } from "./IncidentHistoryBar";
import {
  InvestigationChatPanel,
  type InvestigationChatPanelHandle,
} from "./InvestigationChatPanel";
import { InvestigationContextPanel } from "./InvestigationContextPanel";
import { InvestigationDiagnosticsPanel } from "./InvestigationDiagnosticsPanel";
import {
  createBriefingFetcher,
  defaultWorkspaceChatHistory,
  fallbackBaseMetadata,
  filterIncidentsForBar,
  PREFETCH_CONCURRENCY,
  PREFETCH_SLOT_LIMIT,
  pickFirstBarIncident,
  type IncidentSyncStatus,
} from "./investigation-prefetch";

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
    Record<string, CachedInvestigationData>
  >({});
  const workspaceCacheRef = useRef<Record<string, CachedInvestigationData>>({});
  const fetchGenRef = useRef(0);
  const briefingFetcherRef = useRef(createBriefingFetcher());
  const chatPanelRef = useRef<InvestigationChatPanelHandle>(null);

  const [syncStatus, setSyncStatus] = useState<Record<string, IncidentSyncStatus>>(
    {},
  );
  const prefetchQueueRef = useRef<string[]>([]);
  const prefetchQueuedRef = useRef<Set<string>>(new Set());
  const prefetchRunningRef = useRef(0);
  const prefetchPlanKeyRef = useRef("");
  const foregroundBriefingRef = useRef(false);
  const activeIncidentIdRef = useRef<string | null>(null);
  const allIncidentsRef = useRef<IncidentSummary[]>([]);

  const [chatIncidentId, setChatIncidentId] = useState<string | null>(null);

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
  const [baseMetadata, setBaseMetadata] =
    useState<InvestigationBaseMetadata | null>(null);
  const baseMetadataRef = useRef<Record<string, InvestigationBaseMetadata>>({});

  const writeWorkspaceCache = useCallback(
    (incidentId: string, entry: CachedInvestigationData) => {
      workspaceCacheRef.current = {
        ...workspaceCacheRef.current,
        [incidentId]: entry,
      };
      setWorkspaceCache({ ...workspaceCacheRef.current });
      setSyncStatus((prev) => ({
        ...prev,
        [incidentId]: entry.diagnostics
          ? "ready"
          : prev[incidentId] === "loading"
            ? "loading"
            : (prev[incidentId] ?? "idle"),
      }));
    },
    [],
  );

  const readWorkspaceCache = useCallback(
    (incidentId: string): CachedInvestigationData | undefined =>
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
    (incident: IncidentSummary): "full" | "chat" | false => {
      const cached = readWorkspaceCache(incident.id);
      if (!cached) return false;

      setChatMessages(cached.chatHistory);
      setChatIncidentId(incident.id);
      setBriefingError(null);
      setBriefingStatus(null);

      if (cached.baseMetadata) {
        setBaseMetadata(cached.baseMetadata);
        baseMetadataRef.current[incident.id] = cached.baseMetadata;
      }

      if (!cached.diagnostics) {
        setDiagnostics(null);
        setDiagnosticsIncidentId(null);
        return "chat";
      }

      setDiagnostics(cached.diagnostics);
      setDiagnosticsIncidentId(incident.id);
      setIncidentSyncStatus(incident.id, "ready");
      return "full";
    },
    [readWorkspaceCache, setIncidentSyncStatus],
  );

  const persistActiveWorkspace = useCallback(() => {
    const incidentId = activeIncidentIdRef.current;
    if (!incidentId) return;

    const cached = readWorkspaceCache(incidentId);
    writeWorkspaceCache(incidentId, {
      chatHistory: cached?.chatHistory ?? chatMessages,
      baseMetadata:
        baseMetadataRef.current[incidentId] ??
        cached?.baseMetadata ??
        null,
      diagnostics:
        diagnosticsIncidentId === incidentId
          ? diagnostics
          : (cached?.diagnostics ?? null),
    });
  }, [
    chatMessages,
    diagnostics,
    diagnosticsIncidentId,
    readWorkspaceCache,
    writeWorkspaceCache,
  ]);

  const persistBriefingResult = useCallback(
    (incidentId: string, nextDiagnostics: InvestigationDiagnostics) => {
      const chatHistory = defaultWorkspaceChatHistory(
        incidentId,
        workspaceCacheRef.current,
      );
      writeWorkspaceCache(incidentId, {
        diagnostics: nextDiagnostics,
        chatHistory,
        baseMetadata:
          baseMetadataRef.current[incidentId] ??
          workspaceCacheRef.current[incidentId]?.baseMetadata ??
          null,
      });
      return chatHistory;
    },
    [writeWorkspaceCache],
  );

  const runPrefetch = useCallback(
    async (incidentId: string): Promise<boolean> => {
      if (foregroundBriefingRef.current) {
        return false;
      }
      if (readWorkspaceCache(incidentId)?.diagnostics) {
        setIncidentSyncStatus(incidentId, "ready");
        return true;
      }
      if (briefingFetcherRef.current.isInFlight(incidentId)) {
        return true;
      }

      setIncidentSyncStatus(incidentId, "loading");

      try {
        const nextDiagnostics =
          await briefingFetcherRef.current.fetchBriefing(incidentId);
        if (!nextDiagnostics) {
          setIncidentSyncStatus(incidentId, "error");
          return true;
        }
        persistBriefingResult(incidentId, nextDiagnostics);
        return true;
      } catch {
        setIncidentSyncStatus(incidentId, "error");
        return true;
      }
    },
    [persistBriefingResult, readWorkspaceCache, setIncidentSyncStatus],
  );

  const autoBriefingSlotIds = useCallback((): Set<string> => {
    return new Set(
      filterIncidentsForBar(allIncidentsRef.current, activeFilter)
        .slice(0, PREFETCH_SLOT_LIMIT)
        .map((item) => item.id),
    );
  }, [activeFilter]);

  const drainPrefetchQueue = useCallback(() => {
    if (foregroundBriefingRef.current) {
      return;
    }

    const allowedSlots = autoBriefingSlotIds();

    while (
      prefetchRunningRef.current < PREFETCH_CONCURRENCY &&
      prefetchQueueRef.current.length > 0
    ) {
      const incidentId = prefetchQueueRef.current[0];
      if (!incidentId) break;

      if (!allowedSlots.has(incidentId)) {
        prefetchQueueRef.current.shift();
        prefetchQueuedRef.current.delete(incidentId);
        continue;
      }

      if (incidentId === activeIncidentIdRef.current) {
        prefetchQueueRef.current.shift();
        prefetchQueuedRef.current.delete(incidentId);
        continue;
      }

      if (readWorkspaceCache(incidentId)?.diagnostics) {
        prefetchQueueRef.current.shift();
        prefetchQueuedRef.current.delete(incidentId);
        setIncidentSyncStatus(incidentId, "ready");
        continue;
      }

      if (briefingFetcherRef.current.isInFlight(incidentId)) {
        break;
      }

      prefetchQueueRef.current.shift();
      prefetchQueuedRef.current.delete(incidentId);
      prefetchRunningRef.current += 1;

      void runPrefetch(incidentId).then((completed) => {
        if (!completed) {
          prefetchQueueRef.current.unshift(incidentId);
          prefetchQueuedRef.current.add(incidentId);
        }
      }).finally(() => {
        prefetchRunningRef.current -= 1;
        drainPrefetchQueue();
      });

      break;
    }
  }, [autoBriefingSlotIds, readWorkspaceCache, runPrefetch, setIncidentSyncStatus]);

  const rebuildPrefetchQueue = useCallback(
    (orderedIds: string[], activeId: string | null) => {
      const nextQueue: string[] = [];
      const nextQueued = new Set<string>();
      const slotIds = orderedIds.slice(0, PREFETCH_SLOT_LIMIT);

      for (const id of slotIds) {
        if (id === activeId) continue;
        if (readWorkspaceCache(id)?.diagnostics) {
          setIncidentSyncStatus(id, "ready");
          continue;
        }
        if (nextQueued.has(id)) continue;
        nextQueue.push(id);
        nextQueued.add(id);
      }

      prefetchQueueRef.current = nextQueue;
      prefetchQueuedRef.current = nextQueued;
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

      foregroundBriefingRef.current = true;
      try {
        if (!options?.force) {
          const restored = restoreWorkspaceFromCache(incident);
          if (restored === "full") {
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
          setBaseMetadata(fallbackBaseMetadata(incident));
          setBriefingStatus({
            phase: "searching",
            message: options?.force
              ? "Refreshing knowledge graph context…"
              : "Loading incident analysis…",
          });
        }

        setIncidentSyncStatus(incident.id, "loading");

        const nextDiagnostics = await briefingFetcherRef.current.fetchBriefing(
          incident.id,
          {
            onStatus: (status) => {
              if (fetchGenRef.current === gen) {
                setBriefingStatus(status);
              }
            },
            onBaseMetadata: (metadata) => {
              if (fetchGenRef.current !== gen) return;
              baseMetadataRef.current[incident.id] = metadata;
              setBaseMetadata(metadata);
              setActiveIncident((prev) =>
                prev?.id === incident.id ? metadata.incident : prev,
              );
              const cached = readWorkspaceCache(incident.id);
              writeWorkspaceCache(incident.id, {
                chatHistory:
                  cached?.chatHistory ?? defaultWorkspaceChatHistory(
                    incident.id,
                    workspaceCacheRef.current,
                  ),
                baseMetadata: metadata,
                diagnostics: cached?.diagnostics ?? null,
              });
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
        setChatIncidentId(incident.id);
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
        foregroundBriefingRef.current = false;
        if (fetchGenRef.current === gen) {
          setBriefingStatus(null);
        }
        drainPrefetchQueue();
      }
    },
    [
      drainPrefetchQueue,
      persistBriefingResult,
      readWorkspaceCache,
      restoreWorkspaceFromCache,
      setIncidentSyncStatus,
      writeWorkspaceCache,
    ],
  );

  const applyFeed = useCallback(
    (data: Awaited<ReturnType<typeof fetchIncidents>>) => {
      prefetchQueueRef.current = [];
      prefetchQueuedRef.current.clear();
      prefetchPlanKeyRef.current = "";
      setAllIncidents(data.incidents);
      allIncidentsRef.current = data.incidents;
      setFeedWarnings(data.warnings);
      setSourcesConnected(data.sources_connected);
      setActiveIncident((prev) => {
        if (prev) {
          return (
            data.incidents.find((item) => item.id === prev.id) ??
            pickFirstBarIncident(data.incidents)
          );
        }
        return pickFirstBarIncident(data.incidents);
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
    activeIncidentIdRef.current = activeIncident?.id ?? null;
  }, [activeIncident?.id]);

  useEffect(() => {
    if (!activeIncident) {
      setDiagnostics(null);
      setDiagnosticsIncidentId(null);
      setBaseMetadata(null);
      setChatMessages(defaultChatWelcomeNoIncident());
      setChatIncidentId(null);
      setBriefingStatus(null);
      setBriefingError(null);
      return;
    }

    const restored = restoreWorkspaceFromCache(activeIncident);
    if (restored === "full") {
      return;
    }

    if (restored !== "chat") {
      setChatMessages(defaultChatWelcome());
      setChatIncidentId(activeIncident.id);
    }

    setDiagnostics(null);
    setDiagnosticsIncidentId(null);
    setBriefingStatus(null);
    void loadWorkspaceForIncident(activeIncident);
  }, [activeIncident?.id, loadWorkspaceForIncident, restoreWorkspaceFromCache]);

  const filteredIncidents = filterIncidentsForBar(allIncidents, activeFilter);

  useEffect(() => {
    allIncidentsRef.current = allIncidents;
  }, [allIncidents]);

  useEffect(() => {
    if (loading || !activeIncident || filteredIncidents.length === 0) return;

    const orderedIds = filteredIncidents.map((item) => item.id);
    const planKey = `${activeFilter}:${orderedIds.join("|")}`;
    if (planKey === prefetchPlanKeyRef.current) return;

    prefetchPlanKeyRef.current = planKey;
    rebuildPrefetchQueue(orderedIds, activeIncident.id);
  }, [
    activeFilter,
    activeIncident,
    filteredIncidents,
    loading,
    rebuildPrefetchQueue,
  ]);

  useEffect(() => {
    const activeId = activeIncident?.id;
    if (!activeId) return;

    prefetchQueueRef.current = prefetchQueueRef.current.filter((id) => id !== activeId);
    prefetchQueuedRef.current.delete(activeId);
    drainPrefetchQueue();
  }, [activeIncident?.id, drainPrefetchQueue]);

  function handleFilterChange(filter: IncidentStatus | "All") {
    setActiveFilter(filter);

    const nextFiltered = filterIncidentsForBar(allIncidents, filter);
    if (nextFiltered.length === 0) return;

    const currentActiveId = activeIncidentIdRef.current;
    const nextActive =
      currentActiveId &&
      nextFiltered.some((item) => item.id === currentActiveId)
        ? nextFiltered.find((item) => item.id === currentActiveId)!
        : nextFiltered[0];

    if (nextActive.id !== currentActiveId) {
      leaveActiveIncident();
      fetchGenRef.current += 1;
      setBriefingError(null);
      setBriefingStatus(null);
      setActiveIncident(nextActive);
    }

    const planKey = `${filter}:${nextFiltered.map((item) => item.id).join("|")}`;
    prefetchPlanKeyRef.current = planKey;
    rebuildPrefetchQueue(
      nextFiltered.map((item) => item.id),
      nextActive.id,
    );
  }

  const handleIncidentVisible = useCallback((_incidentId: string) => {
    // Briefings for cards beyond the background prefetch window load on select.
  }, []);

  function leaveActiveIncident() {
    chatPanelRef.current?.finalizeInterruptedStream();
    persistActiveWorkspace();
  }

  function handleSelectIncident(incident: IncidentSummary) {
    if (incident.id === activeIncident?.id) return;

    leaveActiveIncident();
    fetchGenRef.current += 1;
    setBriefingError(null);
    setBriefingStatus(null);

    const cached = readWorkspaceCache(incident.id);
    if (cached?.diagnostics) {
      setBaseMetadata(
        cached.baseMetadata ?? fallbackBaseMetadata(incident),
      );
      setDiagnostics(cached.diagnostics);
      setDiagnosticsIncidentId(incident.id);
      setChatMessages(cached.chatHistory);
      setChatIncidentId(incident.id);
      setActiveIncident(incident);
      return;
    }

    setBaseMetadata(fallbackBaseMetadata(incident));
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

      const cached = readWorkspaceCache(updated.id);
      if (cached) {
        const patchedMetadata = cached.baseMetadata
          ? { ...cached.baseMetadata, incident: updated }
          : fallbackBaseMetadata(updated);
        baseMetadataRef.current[updated.id] = patchedMetadata;
        if (activeIncident.id === updated.id) {
          setBaseMetadata(patchedMetadata);
        }
        writeWorkspaceCache(updated.id, {
          ...cached,
          baseMetadata: patchedMetadata,
        });
      } else if (activeIncident.id === updated.id) {
        setBaseMetadata(fallbackBaseMetadata(updated));
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
    fetchGenRef.current += 1;
    const gen = fetchGenRef.current;
    setRefreshingBriefing(true);
    setBriefingError(null);
    try {
      await loadWorkspaceForIncident(activeIncident, { force: true, gen });
    } finally {
      setRefreshingBriefing(false);
    }
  }

  function handleChatMessagesChange(
    messages: InvestigationChatMessage[],
    forIncidentId: string,
  ) {
    if (!forIncidentId) return;

    if (forIncidentId === activeIncidentIdRef.current) {
      setChatMessages(messages);
      setChatIncidentId(forIncidentId);
    }

    const cached = readWorkspaceCache(forIncidentId);
    writeWorkspaceCache(forIncidentId, {
      chatHistory: messages,
      baseMetadata:
        baseMetadataRef.current[forIncidentId] ??
        cached?.baseMetadata ??
        null,
      diagnostics:
        diagnosticsIncidentId === forIncidentId
          ? diagnostics
          : (cached?.diagnostics ?? null),
    });
  }

  const syncingCount = Object.values(syncStatus).filter(
    (status) => status === "loading",
  ).length;

  if (loading) {
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
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40">
          <PanelDataLoader
            icon={Search}
            label="Loading incidents…"
            sublabel="Pulling open issues from connected Jira and Slack sources."
            steps={[
              "Fetching incident feed",
              "Resolving workspace context",
              "Preparing investigation panels",
            ]}
          />
        </div>
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

  const analyzing = briefingStatus !== null || refreshingBriefing;
  const graphAnalyzing =
    !!activeIncident &&
    analyzing &&
    (!visibleDiagnostics || diagnosticsIncidentId !== activeIncident.id);

  const visibleBaseMetadata =
    activeIncident &&
    (baseMetadata?.incident.id === activeIncident.id
      ? baseMetadata
      : (workspaceCache[activeIncident.id]?.baseMetadata ??
        fallbackBaseMetadata(activeIncident)));

  const visibleChatMessages =
    !activeIncident
      ? defaultChatWelcomeNoIncident()
      : chatIncidentId === activeIncident.id
        ? chatMessages
        : (workspaceCache[activeIncident.id]?.chatHistory ?? defaultChatWelcome());

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
        onFilterChange={handleFilterChange}
        onSelectIncident={handleSelectIncident}
        onIncidentVisible={handleIncidentVisible}
      />

      <div className="grid h-[720px] min-h-0 gap-6 xl:grid-cols-3">
        <InvestigationChatPanel
          ref={chatPanelRef}
          key={activeIncident?.id ?? "no-incident"}
          incidentId={activeIncident?.id ?? null}
          activeIncidentTitle={activeIncident?.title ?? null}
          suggestions={chatSuggestions}
          messages={visibleChatMessages}
          onMessagesChange={handleChatMessagesChange}
        />
        <InvestigationDiagnosticsPanel
          key={`diag-${activeIncident?.id ?? "none"}`}
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
          status={
            visibleBaseMetadata?.incident.status ??
            activeIncident?.status ??
            "Open"
          }
          statusUpdating={statusUpdating}
          analyzing={analyzing}
          graphAnalyzing={graphAnalyzing}
          analysisMessage={briefingStatus?.message ?? null}
          onStatusChange={handleStatusChange}
          onRefresh={activeIncident ? handleRefreshBriefing : undefined}
          refreshing={refreshingBriefing}
        />
        <InvestigationContextPanel
          key={`ctx-${activeIncident?.id ?? "none"}`}
          smes={visibleDiagnostics?.smes ?? []}
          slackThreads={visibleDiagnostics?.slack_threads ?? []}
          jiraTickets={visibleDiagnostics?.jira_tickets ?? []}
          notionPages={visibleDiagnostics?.notion_pages ?? []}
          baseMetadata={visibleBaseMetadata}
          analyzing={analyzing}
          graphAnalyzing={graphAnalyzing}
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
