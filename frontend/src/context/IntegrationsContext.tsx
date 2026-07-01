"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  deleteIntegrationConfig,
  fetchIntegrationConfig,
  saveAndSyncIntegration,
  syncAllIntegrations,
  syncIntegrationSource,
  syncMemberRoster,
} from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useWorkspace } from "@/context/WorkspaceContext";
import {
  DEFAULT_INTEGRATION_CONFIG,
  getConnectedMemberImportSources,
  INTEGRATION_CATALOG,
  isIntegrationConnected,
  isIntegrationDraft,
  wasPreviouslyConnected,
  type IntegrationConfigMap,
  type IntegrationId,
  type IntegrationStatus,
} from "@/lib/integrations";


function integrationsStorageKey(tenantId: string | null | undefined): string | null {
  if (!tenantId) return null;
  return `empulse-integrations-config:${tenantId}`;
}

function loadConfig(tenantId: string | null | undefined): IntegrationConfigMap {
  if (typeof window === "undefined") return DEFAULT_INTEGRATION_CONFIG;

  const key = integrationsStorageKey(tenantId);
  if (!key) return DEFAULT_INTEGRATION_CONFIG;

  try {
    const raw = localStorage.getItem(key);
    if (raw) {
      return { ...DEFAULT_INTEGRATION_CONFIG, ...JSON.parse(raw) };
    }
    return DEFAULT_INTEGRATION_CONFIG;
  } catch {
    return DEFAULT_INTEGRATION_CONFIG;
  }
}

function saveConfig(tenantId: string | null | undefined, config: IntegrationConfigMap) {
  const key = integrationsStorageKey(tenantId);
  if (!key) return;
  localStorage.setItem(key, JSON.stringify(config));
}

interface SyncProgress {
  active: boolean;
  currentSource: string | null;
  completed: string[];
  total: number;
  error: string | null;
}

function mergeIntegrationConfig(
  local: IntegrationConfigMap,
  remote: IntegrationConfigMap,
): IntegrationConfigMap {
  return {
    slack: { ...DEFAULT_INTEGRATION_CONFIG.slack, ...local.slack, ...remote.slack },
    notion: { ...DEFAULT_INTEGRATION_CONFIG.notion, ...local.notion, ...remote.notion },
    github: { ...DEFAULT_INTEGRATION_CONFIG.github, ...local.github, ...remote.github },
    jira: { ...DEFAULT_INTEGRATION_CONFIG.jira, ...local.jira, ...remote.jira },
  };
}

interface IntegrationsContextValue {
  config: IntegrationConfigMap;
  statuses: Record<IntegrationId, IntegrationStatus>;
  syncProgress: SyncProgress;
  updateConfig: <K extends IntegrationId>(
    id: K,
    patch: Partial<IntegrationConfigMap[K]>,
  ) => void;
  connect: (id: IntegrationId) => Promise<void>;
  disconnect: (id: IntegrationId) => void;
  getStatus: (id: IntegrationId) => IntegrationStatus;
  triggerGlobalSync: () => Promise<void>;
}

const IntegrationsContext = createContext<IntegrationsContextValue | null>(null);

const BACKEND_SYNC_SOURCES = new Set<IntegrationId>(["github", "jira"]);

function deriveStatuses(
  config: IntegrationConfigMap,
  syncingIds: Set<IntegrationId>,
): Record<IntegrationId, IntegrationStatus> {
  const statuses = {} as Record<IntegrationId, IntegrationStatus>;
  for (const app of INTEGRATION_CATALOG) {
    if (syncingIds.has(app.id)) {
      statuses[app.id] = "syncing";
    } else if (isIntegrationConnected(app.id, config)) {
      statuses[app.id] = "connected";
    } else if (isIntegrationDraft(app.id, config)) {
      statuses[app.id] = "pending";
    } else if (wasPreviouslyConnected(app.id, config)) {
      statuses[app.id] = "disconnected";
    } else {
      statuses[app.id] = "available";
    }
  }
  return statuses;
}

export function IntegrationsProvider({ children }: { children: ReactNode }) {
  const { activeTenant, session } = useAuth();
  const tenantId = activeTenant?.id ?? null;
  const { refreshOperationalState } = useWorkspace();
  const [config, setConfig] = useState<IntegrationConfigMap>(
    DEFAULT_INTEGRATION_CONFIG,
  );
  const [syncingIds, setSyncingIds] = useState<Set<IntegrationId>>(new Set());
  const [syncProgress, setSyncProgress] = useState<SyncProgress>({
    active: false,
    currentSource: null,
    completed: [],
    total: 0,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function hydrate() {
      const local = loadConfig(tenantId);
      if (!tenantId) {
        if (!cancelled) setConfig(local);
        return;
      }

      try {
        const remote = await fetchIntegrationConfig();
        const merged = mergeIntegrationConfig(local, remote);
        if (!cancelled) {
          setConfig(merged);
          saveConfig(tenantId, merged);
        }
      } catch {
        if (!cancelled) setConfig(local);
      }
    }

    void hydrate();
    setSyncingIds(new Set());
    setSyncProgress({
      active: false,
      currentSource: null,
      completed: [],
      total: 0,
      error: null,
    });

    return () => {
      cancelled = true;
    };
  }, [tenantId]);

  const persist = useCallback(
    (next: IntegrationConfigMap) => {
      setConfig(next);
      saveConfig(tenantId, next);
    },
    [tenantId],
  );

  const updateConfig = useCallback(
    <K extends IntegrationId>(
      id: K,
      patch: Partial<IntegrationConfigMap[K]>,
    ) => {
      setConfig((prev) => {
        const credentialFields: Record<IntegrationId, string[]> = {
          slack: ["botToken", "workspaceUrl", "channelIds"],
          notion: ["integrationToken"],
          github: [
            "repositoryUrl",
            "personalAccessToken",
            "oauthConnected",
            "branchTarget",
          ],
          jira: ["siteUrl", "apiToken", "projectKeys", "accountEmail"],
        };
        const touchesCredentials = credentialFields[id].some(
          (field) => field in patch,
        );
        const merged = {
          ...prev[id],
          ...patch,
          ...(touchesCredentials && !("validated" in patch)
            ? { validated: false }
            : {}),
        } as IntegrationConfigMap[K];
        const next = {
          ...prev,
          [id]: merged,
        };
        saveConfig(tenantId, next);
        return next;
      });
    },
    [tenantId],
  );

  const connect = useCallback(
    async (id: IntegrationId) => {
      if (!isIntegrationConnected(id, config)) return;

      setSyncingIds((prev) => new Set(prev).add(id));
      setSyncProgress((prev) => ({ ...prev, error: null }));

      try {
        if (BACKEND_SYNC_SOURCES.has(id)) {
          await saveAndSyncIntegration(id, config);
        } else {
          await new Promise((resolve) => setTimeout(resolve, 800));
        }
        await refreshOperationalState();
      } catch (err) {
        setSyncProgress((prev) => ({
          ...prev,
          error: err instanceof Error ? err.message : "Sync failed",
        }));
        throw err;
      } finally {
        setSyncingIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }
    },
    [config, refreshOperationalState],
  );

  const disconnect = useCallback(
    async (id: IntegrationId) => {
      const cleared = {
        ...DEFAULT_INTEGRATION_CONFIG[id],
        previouslyConnected: true,
      };
      persist({ ...config, [id]: cleared });
      try {
        await deleteIntegrationConfig(id);
      } catch {
        // Local disconnect still applies if backend removal fails.
      }
    },
    [config, persist],
  );

  const statuses = useMemo(
    () => deriveStatuses(config, syncingIds),
    [config, syncingIds],
  );

  const getStatus = useCallback(
    (id: IntegrationId) => statuses[id],
    [statuses],
  );

  const triggerGlobalSync = useCallback(async () => {
    const connected = INTEGRATION_CATALOG.filter((app) =>
      isIntegrationConnected(app.id, config),
    );
    if (connected.length === 0) return;

    const memberSources = getConnectedMemberImportSources(config);
    const backendSources = connected.filter((app) =>
      BACKEND_SYNC_SOURCES.has(app.id),
    );

    const company =
      activeTenant?.companyName ?? session?.company ?? "My Company";

    setSyncProgress({
      active: true,
      currentSource: null,
      completed: [],
      total: connected.length,
      error: null,
    });
    setSyncingIds(new Set(connected.map((app) => app.id)));

    const completedNames = new Set<string>();

    try {
      if (memberSources.length > 0) {
        setSyncProgress((prev) => ({
          ...prev,
          currentSource: "Member roster",
        }));

        const result = await syncMemberRoster(memberSources, company, config);

        if (result.source_errors?.length) {
          setSyncProgress((prev) => ({
            ...prev,
            error: result.source_errors!.join(" "),
          }));
        }

        for (const source of result.sources) {
          const app = INTEGRATION_CATALOG.find((entry) => entry.id === source);
          if (app) completedNames.add(app.name);
        }

        setSyncProgress((prev) => ({
          ...prev,
          completed: [...completedNames],
        }));
      }

      if (backendSources.length > 0) {
        setSyncProgress((prev) => ({
          ...prev,
          currentSource: "GitHub & Jira",
        }));

        if (backendSources.length === 2) {
          const result = await syncAllIntegrations();
          for (const item of result.results) {
            const app = INTEGRATION_CATALOG.find(
              (entry) => entry.id === item.source,
            );
            if (app) completedNames.add(app.name);
          }
        } else {
          const source = backendSources[0]!.id as "github" | "jira";
          await syncIntegrationSource(source);
          completedNames.add(backendSources[0]!.name);
        }

        setSyncProgress((prev) => ({
          ...prev,
          completed: [...completedNames],
        }));
      }

      await refreshOperationalState();
    } catch (err) {
      setSyncProgress((prev) => ({
        ...prev,
        error: err instanceof Error ? err.message : "Global sync failed",
      }));
    } finally {
      setSyncingIds(new Set());
      setSyncProgress((prev) => ({
        ...prev,
        active: false,
        currentSource: null,
      }));
    }
  }, [activeTenant?.companyName, config, refreshOperationalState, session?.company]);

  const value = useMemo(
    () => ({
      config,
      statuses,
      syncProgress,
      updateConfig,
      connect,
      disconnect,
      getStatus,
      triggerGlobalSync,
    }),
    [
      config,
      statuses,
      syncProgress,
      updateConfig,
      connect,
      disconnect,
      getStatus,
      triggerGlobalSync,
    ],
  );

  return (
    <IntegrationsContext.Provider value={value}>
      {children}
    </IntegrationsContext.Provider>
  );
}

export function useIntegrations() {
  const context = useContext(IntegrationsContext);
  if (!context) {
    throw new Error("useIntegrations must be used within IntegrationsProvider");
  }
  return context;
}
