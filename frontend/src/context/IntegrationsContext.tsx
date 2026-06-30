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
  saveAndSyncIntegration,
  syncAllIntegrations,
  syncIntegrationSource,
} from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import {
  DEFAULT_INTEGRATION_CONFIG,
  INTEGRATION_CATALOG,
  isIntegrationConnected,
  isIntegrationDraft,
  wasPreviouslyConnected,
  type IntegrationConfigMap,
  type IntegrationId,
  type IntegrationStatus,
} from "@/lib/integrations";

const STORAGE_KEY = "empulse-integrations-config";

interface SyncProgress {
  active: boolean;
  currentSource: string | null;
  completed: string[];
  total: number;
  error: string | null;
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

function loadConfig(): IntegrationConfigMap {
  if (typeof window === "undefined") return DEFAULT_INTEGRATION_CONFIG;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_INTEGRATION_CONFIG;
    return { ...DEFAULT_INTEGRATION_CONFIG, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_INTEGRATION_CONFIG;
  }
}

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
    setConfig(loadConfig());
  }, []);

  const persist = useCallback((next: IntegrationConfigMap) => {
    setConfig(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }, []);

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
          jira: ["siteUrl", "apiToken", "projectKeys"],
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
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        return next;
      });
    },
    [],
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
    (id: IntegrationId) => {
      const cleared = {
        ...DEFAULT_INTEGRATION_CONFIG[id],
        previouslyConnected: true,
      };
      persist({ ...config, [id]: cleared });
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

    const backendSources = connected.filter((app) =>
      BACKEND_SYNC_SOURCES.has(app.id),
    );
    const localOnly = connected.filter(
      (app) => !BACKEND_SYNC_SOURCES.has(app.id),
    );

    setSyncProgress({
      active: true,
      currentSource: null,
      completed: [],
      total: connected.length,
      error: null,
    });
    setSyncingIds(new Set(connected.map((app) => app.id)));

    try {
      if (backendSources.length > 0) {
        setSyncProgress((prev) => ({
          ...prev,
          currentSource: "GitHub & Jira",
        }));

        if (backendSources.length === 2) {
          const result = await syncAllIntegrations();
          setSyncProgress((prev) => ({
            ...prev,
            completed: result.results.map((item) => {
              const app = INTEGRATION_CATALOG.find((entry) => entry.id === item.source);
              return app?.name ?? item.source;
            }),
          }));
        } else {
          const source = backendSources[0]!.id as "github" | "jira";
          await syncIntegrationSource(source);
          setSyncProgress((prev) => ({
            ...prev,
            completed: [
              ...prev.completed,
              backendSources[0]!.name,
            ],
          }));
        }
      }

      for (const app of localOnly) {
        setSyncProgress((prev) => ({
          ...prev,
          currentSource: app.name,
        }));
        await new Promise((resolve) => setTimeout(resolve, 600));
        setSyncProgress((prev) => ({
          ...prev,
          completed: [...prev.completed, app.name],
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
  }, [config, refreshOperationalState]);

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
