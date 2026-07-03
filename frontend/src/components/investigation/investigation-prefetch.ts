import { streamIncidentBriefing } from "@/lib/api"
import {
  defaultChatWelcome,
  type InvestigationChatMessage
} from "@/hooks/useIncidentInvestigation"
import type {
  CachedInvestigationData,
  IncidentStatus,
  IncidentSummary,
  InvestigationAnalysisStatus,
  InvestigationBaseMetadata,
  InvestigationDiagnostics
} from "@/lib/types"

export type IncidentSyncStatus = "idle" | "loading" | "ready" | "error"

/** @deprecated Use CachedInvestigationData */
export type CachedWorkspace = CachedInvestigationData

export const PREFETCH_CONCURRENCY = 1
/** Max incident cards in the bar that auto-load briefings (including the active card). */
export const PREFETCH_SLOT_LIMIT = 3

export interface BriefingFetchCallbacks {
  onStatus?: (status: InvestigationAnalysisStatus) => void
  onBaseMetadata?: (metadata: InvestigationBaseMetadata) => void
  onDiagnostics?: (diagnostics: InvestigationDiagnostics) => void
}

interface CallbackRegistry {
  onStatus: Set<(status: InvestigationAnalysisStatus) => void>
  onBaseMetadata: Set<(metadata: InvestigationBaseMetadata) => void>
  onDiagnostics: Set<(diagnostics: InvestigationDiagnostics) => void>
}

export function createBriefingFetcher() {
  const inFlight = new Map<string, Promise<InvestigationDiagnostics | null>>()
  const callbacks = new Map<string, CallbackRegistry>()

  function ensureRegistry(incidentId: string): CallbackRegistry {
    const existing = callbacks.get(incidentId)
    if (existing) return existing
    const registry: CallbackRegistry = {
      onStatus: new Set(),
      onBaseMetadata: new Set(),
      onDiagnostics: new Set()
    }
    callbacks.set(incidentId, registry)
    return registry
  }

  function registerCallbacks(
    incidentId: string,
    next?: BriefingFetchCallbacks
  ): void {
    if (!next) return
    const registry = ensureRegistry(incidentId)
    if (next.onStatus) registry.onStatus.add(next.onStatus)
    if (next.onBaseMetadata) registry.onBaseMetadata.add(next.onBaseMetadata)
    if (next.onDiagnostics) registry.onDiagnostics.add(next.onDiagnostics)
  }

  async function fetchBriefing(
    incidentId: string,
    nextCallbacks?: BriefingFetchCallbacks,
    options?: { force?: boolean }
  ): Promise<InvestigationDiagnostics | null> {
    if (options?.force) {
      inFlight.delete(incidentId)
      callbacks.delete(incidentId)
    }

    registerCallbacks(incidentId, nextCallbacks)

    const existing = inFlight.get(incidentId)
    if (existing) return existing

    const promise = (async () => {
      let diagnostics: InvestigationDiagnostics | null = null
      const registry = ensureRegistry(incidentId)

      await streamIncidentBriefing(
        incidentId,
        (status) => {
          registry.onStatus.forEach((handler) => handler(status))
        },
        (diag) => {
          diagnostics = diag
          registry.onDiagnostics.forEach((handler) => handler(diag))
        },
        {
          force: options?.force,
          onBaseMetadata: (metadata) => {
            registry.onBaseMetadata.forEach((handler) => handler(metadata))
          }
        }
      )

      return diagnostics
    })().finally(() => {
      inFlight.delete(incidentId)
      callbacks.delete(incidentId)
    })

    inFlight.set(incidentId, promise)
    return promise
  }

  function isInFlight(incidentId: string): boolean {
    return inFlight.has(incidentId)
  }

  return { fetchBriefing, isInFlight }
}

export function defaultWorkspaceChatHistory(
  incidentId: string,
  cache: Record<string, CachedInvestigationData>
): InvestigationChatMessage[] {
  return cache[incidentId]?.chatHistory ?? defaultChatWelcome()
}

export function filterIncidentsForBar(
  incidents: IncidentSummary[],
  filter: IncidentStatus | "All"
): IncidentSummary[] {
  return filter === "All"
    ? incidents
    : incidents.filter((item) => item.status === filter)
}

export function pickFirstBarIncident(
  incidents: IncidentSummary[]
): IncidentSummary | null {
  return incidents[0] ?? null
}

export function fallbackBaseMetadata(
  incident: IncidentSummary
): InvestigationBaseMetadata {
  return {
    incident,
    assignments: [],
    scope_owners: []
  }
}
