import { streamIncidentBriefing } from "@/lib/api";
import {
  defaultChatWelcome,
  type InvestigationChatMessage,
} from "@/hooks/useIncidentInvestigation";
import type {
  IncidentStatus,
  IncidentSummary,
  InvestigationAnalysisStatus,
  InvestigationDiagnostics,
} from "@/lib/types";

export type IncidentSyncStatus = "idle" | "loading" | "ready" | "error";

export interface CachedWorkspace {
  chatHistory: InvestigationChatMessage[];
  diagnostics: InvestigationDiagnostics | null;
}

export const PREFETCH_CONCURRENCY = 1;

export interface BriefingFetchCallbacks {
  onStatus?: (status: InvestigationAnalysisStatus) => void;
  onDiagnostics?: (diagnostics: InvestigationDiagnostics) => void;
}

interface CallbackRegistry {
  onStatus: Set<(status: InvestigationAnalysisStatus) => void>;
  onDiagnostics: Set<(diagnostics: InvestigationDiagnostics) => void>;
}

export function createBriefingFetcher() {
  const inFlight = new Map<string, Promise<InvestigationDiagnostics | null>>();
  const callbacks = new Map<string, CallbackRegistry>();

  function ensureRegistry(incidentId: string): CallbackRegistry {
    const existing = callbacks.get(incidentId);
    if (existing) return existing;
    const registry: CallbackRegistry = {
      onStatus: new Set(),
      onDiagnostics: new Set(),
    };
    callbacks.set(incidentId, registry);
    return registry;
  }

  function registerCallbacks(
    incidentId: string,
    next?: BriefingFetchCallbacks,
  ): void {
    if (!next) return;
    const registry = ensureRegistry(incidentId);
    if (next.onStatus) registry.onStatus.add(next.onStatus);
    if (next.onDiagnostics) registry.onDiagnostics.add(next.onDiagnostics);
  }

  async function fetchBriefing(
    incidentId: string,
    nextCallbacks?: BriefingFetchCallbacks,
    options?: { force?: boolean },
  ): Promise<InvestigationDiagnostics | null> {
    if (options?.force) {
      inFlight.delete(incidentId);
      callbacks.delete(incidentId);
    }

    registerCallbacks(incidentId, nextCallbacks);

    const existing = inFlight.get(incidentId);
    if (existing) return existing;

    const promise = (async () => {
      let diagnostics: InvestigationDiagnostics | null = null;
      const registry = ensureRegistry(incidentId);

      await streamIncidentBriefing(
        incidentId,
        (status) => {
          registry.onStatus.forEach((handler) => handler(status));
        },
        (diag) => {
          diagnostics = diag;
          registry.onDiagnostics.forEach((handler) => handler(diag));
        },
        { force: options?.force },
      );

      return diagnostics;
    })().finally(() => {
      inFlight.delete(incidentId);
      callbacks.delete(incidentId);
    });

    inFlight.set(incidentId, promise);
    return promise;
  }

  function isInFlight(incidentId: string): boolean {
    return inFlight.has(incidentId);
  }

  return { fetchBriefing, isInFlight };
}

export function defaultWorkspaceChatHistory(
  incidentId: string,
  cache: Record<string, CachedWorkspace>,
): InvestigationChatMessage[] {
  return cache[incidentId]?.chatHistory ?? defaultChatWelcome();
}

export function filterIncidentsForBar(
  incidents: IncidentSummary[],
  filter: IncidentStatus | "All",
): IncidentSummary[] {
  return filter === "All"
    ? incidents
    : incidents.filter((item) => item.status === filter);
}

export function pickFirstBarIncident(
  incidents: IncidentSummary[],
): IncidentSummary | null {
  return incidents[0] ?? null;
}
