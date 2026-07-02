"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { streamIncidentBriefing } from "@/lib/api";
import type {
  IncidentSummary,
  InvestigationAnalysisStatus,
  InvestigationDiagnostics,
} from "@/lib/types";

export interface InvestigationChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export interface IncidentInvestigationCacheEntry {
  diagnostics: InvestigationDiagnostics;
  chatMessages: InvestigationChatMessage[];
  incidentUpdatedAt: string;
  cachedAt: number;
}

const CACHE_TTL_MS = 10 * 60 * 1000;

export function defaultChatWelcome(
  title: string | null,
): InvestigationChatMessage[] {
  return [
    {
      id: "welcome",
      role: "assistant",
      content: title
        ? `Incident briefing is in the center and right panels. Ask follow-up questions about "${title}" below.`
        : "Select an incident above to load its briefing.",
    },
  ];
}

function isCacheFresh(entry: IncidentInvestigationCacheEntry): boolean {
  return Date.now() - entry.cachedAt < CACHE_TTL_MS;
}

export function useIncidentInvestigation(activeIncident: IncidentSummary | null) {
  const cacheRef = useRef<Map<string, IncidentInvestigationCacheEntry>>(
    new Map(),
  );
  const fetchGenRef = useRef(0);
  const activeIncidentIdRef = useRef<string | null>(null);

  const [diagnostics, setDiagnostics] =
    useState<InvestigationDiagnostics | null>(null);
  const [briefingStatus, setBriefingStatus] =
    useState<InvestigationAnalysisStatus | null>(null);
  const [chatMessages, setChatMessages] = useState<InvestigationChatMessage[]>(
    defaultChatWelcome(null),
  );
  const [briefingError, setBriefingError] = useState<string | null>(null);

  const applyCachedEntry = useCallback((incident: IncidentSummary) => {
    const cached = cacheRef.current.get(incident.id);
    if (!cached) return false;
    setDiagnostics(cached.diagnostics);
    setChatMessages(cached.chatMessages);
    setBriefingError(null);
    setBriefingStatus(null);
    return true;
  }, []);

  const saveToCache = useCallback(
    (
      incident: IncidentSummary,
      nextDiagnostics: InvestigationDiagnostics,
      messages?: InvestigationChatMessage[],
    ) => {
      const existing = cacheRef.current.get(incident.id);
      cacheRef.current.set(incident.id, {
        diagnostics: nextDiagnostics,
        chatMessages:
          messages ??
          existing?.chatMessages ??
          defaultChatWelcome(incident.title),
        incidentUpdatedAt: incident.updated_at,
        cachedAt: Date.now(),
      });
    },
    [],
  );

  const loadBriefing = useCallback(
    async (
      incident: IncidentSummary,
      options?: { background?: boolean; force?: boolean },
    ) => {
      const cached = cacheRef.current.get(incident.id);
      if (
        !options?.force &&
        cached &&
        isCacheFresh(cached) &&
        !options?.background
      ) {
        applyCachedEntry(incident);
        return;
      }

      const gen = ++fetchGenRef.current;

      if (!options?.background) {
        setBriefingError(null);
        if (!cached || options?.force) {
          setDiagnostics(null);
        }
      }

      try {
        let nextDiagnostics: InvestigationDiagnostics | null = null;

        await streamIncidentBriefing(
          incident.id,
          (status) => {
            if (fetchGenRef.current === gen && !options?.background) {
              setBriefingStatus(status);
            }
          },
          (diag) => {
            nextDiagnostics = diag;
          },
        );

        if (fetchGenRef.current !== gen || !nextDiagnostics) return;

        saveToCache(incident, nextDiagnostics);

        if (!options?.background && activeIncidentIdRef.current === incident.id) {
          setDiagnostics(nextDiagnostics);
          const entry = cacheRef.current.get(incident.id);
          setChatMessages(
            entry?.chatMessages ?? defaultChatWelcome(incident.title),
          );
        }
      } catch (err) {
        if (fetchGenRef.current !== gen) return;
        if (!options?.background) {
          setBriefingError(
            err instanceof Error ? err.message : "Failed to load incident briefing",
          );
          if (!cached) setDiagnostics(null);
        }
      } finally {
        if (fetchGenRef.current === gen && !options?.background) {
          setBriefingStatus(null);
        }
      }
    },
    [applyCachedEntry, saveToCache],
  );

  const invalidateIncident = useCallback((incidentId: string) => {
    cacheRef.current.delete(incidentId);
  }, []);

  const syncCacheFromFeed = useCallback((_incidents: IncidentSummary[]) => {
    // Keep per-incident briefing cache across feed refreshes; explicit invalidation only.
  }, []);

  const updateChatMessages = useCallback(
    (incidentId: string, messages: InvestigationChatMessage[]) => {
      setChatMessages(messages);
      const entry = cacheRef.current.get(incidentId);
      if (entry) {
        cacheRef.current.set(incidentId, {
          ...entry,
          chatMessages: messages,
        });
      }
    },
    [],
  );

  const restoreFromCache = useCallback(
    (incident: IncidentSummary): boolean => {
      const cached = cacheRef.current.get(incident.id);
      if (!cached || !isCacheFresh(cached)) return false;
      return applyCachedEntry(incident);
    },
    [applyCachedEntry],
  );

  useEffect(() => {
    activeIncidentIdRef.current = activeIncident?.id ?? null;

    if (!activeIncident) {
      setDiagnostics(null);
      setChatMessages(defaultChatWelcome(null));
      setBriefingStatus(null);
      setBriefingError(null);
      return;
    }

    if (restoreFromCache(activeIncident)) {
      return;
    }

    void loadBriefing(activeIncident);
  }, [activeIncident?.id, loadBriefing, restoreFromCache]);

  return {
    diagnostics,
    briefingStatus,
    chatMessages,
    briefingError,
    loadBriefing,
    invalidateIncident,
    syncCacheFromFeed,
    updateChatMessages,
  };
}
