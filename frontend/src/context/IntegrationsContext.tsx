"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  deleteIntegrationConfig,
  fetchIntegrationConfig,
  fetchIntegrationSyncJobs,
  saveAndSyncIntegration,
  syncAllIntegrations,
  syncIntegrationSource,
} from "@/lib/api";
import { formatFetchError } from "@/lib/api-client";
import { formatSyncJobError } from "@/lib/sync-errors";
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
import type { IntegrationSyncJobStatusResponse } from "@/lib/types";

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
  const mergeJira = (): IntegrationConfigMap["jira"] => {
    const merged = {
      ...DEFAULT_INTEGRATION_CONFIG.jira,
      ...local.jira,
      ...remote.jira,
    };
    if (remote.jira.validated) {
      merged.validated = true;
      merged.previouslyConnected = true;
    }
    if (remote.jira.apiToken.trim()) {
      merged.apiToken = remote.jira.apiToken;
    }
    if (remote.jira.siteUrl.trim()) {
      merged.siteUrl = remote.jira.siteUrl;
    }
    if (remote.jira.authEmail.trim()) {
      merged.authEmail = remote.jira.authEmail;
    }
    if (remote.jira.projectKeys.trim()) {
      merged.projectKeys = remote.jira.projectKeys;
    }
    return merged;
  };

  return {
    slack: { ...DEFAULT_INTEGRATION_CONFIG.slack, ...local.slack, ...remote.slack },
    notion: { ...DEFAULT_INTEGRATION_CONFIG.notion, ...local.notion, ...remote.notion },
    github: { ...DEFAULT_INTEGRATION_CONFIG.github, ...local.github, ...remote.github },
    jira: mergeJira(),
  };
}

interface IntegrationsContextValue {
  config: IntegrationConfigMap;
  statuses: Record<IntegrationId, IntegrationStatus>;
  syncJobs: IntegrationSyncJobStatusResponse[];
  syncProgress: SyncProgress;
  syncActionError: string | null;
  pendingSyncSources: ReadonlySet<IntegrationId>;
  globalSyncPending: boolean;
  updateConfig: <K extends IntegrationId>(
    id: K,
    patch: Partial<IntegrationConfigMap[K]>,
  ) => void;
  connect: (id: IntegrationId) => Promise<void>;
  disconnect: (id: IntegrationId) => void;
  getStatus: (id: IntegrationId) => IntegrationStatus;
  triggerGlobalSync: () => Promise<void>;
  triggerSourceSync: (id: IntegrationId) => Promise<void>;
  refreshSyncJobs: () => Promise<void>;
}

const IntegrationsContext = createContext<IntegrationsContextValue | null>(null);

const BACKEND_SYNC_SOURCES = new Set<IntegrationId>(["github", "jira", "notion", "slack"]);
const SYNC_POLL_INTERVAL_MS = 2000;

function sourceDisplayName(source: string): string {
  return (
    INTEGRATION_CATALOG.find((app) => app.id === source)?.name ??
    source.charAt(0).toUpperCase() + source.slice(1)
  );
}

function deriveStatuses(
  config: IntegrationConfigMap,
  syncJobs: IntegrationSyncJobStatusResponse[],
  pendingSources: ReadonlySet<IntegrationId>,
): Record<IntegrationId, IntegrationStatus> {
  const activeSources = new Set(
    syncJobs
      .filter((job) => job.status === "queued" || job.status === "running")
      .map((job) => job.source as IntegrationId),
  );

  const statuses = {} as Record<IntegrationId, IntegrationStatus>;
  for (const app of INTEGRATION_CATALOG) {
    if (activeSources.has(app.id) || pendingSources.has(app.id)) {
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

function deriveSyncProgress(
  syncJobs: IntegrationSyncJobStatusResponse[],
): SyncProgress {
  const activeJobs = syncJobs.filter(
    (job) => job.status === "queued" || job.status === "running",
  );
  const completed = syncJobs
    .filter((job) => job.status === "completed")
    .map((job) => sourceDisplayName(job.source));
  const failedJob = syncJobs.find((job) => job.status === "failed");

  const currentJob = activeJobs[0];
  const relevantJobs = syncJobs.filter(
    (job) =>
      job.status === "queued" ||
      job.status === "running" ||
      job.status === "completed" ||
      job.status === "failed",
  );
  const total = Math.max(
    relevantJobs.length,
    completed.length + activeJobs.length,
  );

  return {
    active: activeJobs.length > 0,
    currentSource: currentJob ? sourceDisplayName(currentJob.source) : null,
    completed,
    total,
    error: failedJob?.error ?? null,
  };
}

export function IntegrationsProvider({ children }: { children: ReactNode }) {
  const { activeTenant } = useAuth();
  const tenantId = activeTenant?.id ?? null;
  const { refreshOperationalState } = useWorkspace();
  const [config, setConfig] = useState<IntegrationConfigMap>(
    DEFAULT_INTEGRATION_CONFIG,
  );
  const [syncJobs, setSyncJobs] = useState<IntegrationSyncJobStatusResponse[]>([]);
  const [pendingSyncSources, setPendingSyncSources] = useState<Set<IntegrationId>>(
    () => new Set(),
  );
  const [globalSyncPending, setGlobalSyncPending] = useState(false);
  const [syncActionError, setSyncActionError] = useState<string | null>(null);
  const hadActiveSyncJobs = useRef(false);

  const refreshSyncJobs = useCallback(async () => {
    if (!tenantId) {
      setSyncJobs([]);
      return;
    }
    try {
      const response = await fetchIntegrationSyncJobs({ limit: 50 });
      setSyncJobs(response.jobs);
    } catch {
      // Keep last known jobs if polling fails briefly.
    }
  }, [tenantId]);

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
    void refreshSyncJobs();

    return () => {
      cancelled = true;
    };
  }, [tenantId, refreshSyncJobs]);

  const syncProgress = useMemo(
    () => deriveSyncProgress(syncJobs),
    [syncJobs],
  );

  const hasActiveSyncJobs = useMemo(
    () =>
      syncJobs.some(
        (job) => job.status === "queued" || job.status === "running",
      ),
    [syncJobs],
  );

  useEffect(() => {
    if (!tenantId || !hasActiveSyncJobs) return;

    const interval = window.setInterval(() => {
      void refreshSyncJobs();
    }, SYNC_POLL_INTERVAL_MS);

    return () => window.clearInterval(interval);
  }, [tenantId, refreshSyncJobs, hasActiveSyncJobs]);

  useEffect(() => {
    if (hadActiveSyncJobs.current && !hasActiveSyncJobs) {
      void refreshOperationalState();
    }
    hadActiveSyncJobs.current = hasActiveSyncJobs;
  }, [hasActiveSyncJobs, refreshOperationalState]);

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
            "repositoryUrls",
            "personalAccessToken",
            "oauthConnected",
            "branchTarget",
            "branchTargets",
            "syncAllBranches",
          ],
          jira: ["siteUrl", "apiToken", "projectKeys", "authEmail"],
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

      try {
        if (BACKEND_SYNC_SOURCES.has(id)) {
          await saveAndSyncIntegration(id, config);
          await refreshSyncJobs();
        } else {
          await new Promise((resolve) => setTimeout(resolve, 800));
        }
      } catch (err) {
        throw err;
      }
    },
    [config, refreshSyncJobs],
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
    () => deriveStatuses(config, syncJobs, pendingSyncSources),
    [config, syncJobs, pendingSyncSources],
  );

  const getStatus = useCallback(
    (id: IntegrationId) => statuses[id],
    [statuses],
  );

  const triggerSourceSync = useCallback(
    async (id: IntegrationId) => {
      if (!BACKEND_SYNC_SOURCES.has(id)) return;
      if (!isIntegrationConnected(id, config)) return;

      setSyncActionError(null);
      setPendingSyncSources((prev) => new Set(prev).add(id));

      try {
        await syncIntegrationSource(id);
        await refreshSyncJobs();
      } catch (err) {
        setSyncActionError(formatSyncJobError(formatFetchError(err, `${id} sync failed`)));
      } finally {
        setPendingSyncSources((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }
    },
    [config, refreshSyncJobs],
  );

  const triggerGlobalSync = useCallback(async () => {
    const connected = INTEGRATION_CATALOG.filter((app) =>
      isIntegrationConnected(app.id, config),
    );
    if (connected.length === 0) return;

    const backendSources = connected.filter((app) =>
      BACKEND_SYNC_SOURCES.has(app.id),
    );
    if (backendSources.length === 0) return;

    setSyncActionError(null);
    setGlobalSyncPending(true);
    setPendingSyncSources(
      () => new Set(backendSources.map((app) => app.id)),
    );

    try {
      await syncAllIntegrations();
      await refreshSyncJobs();
    } catch (err) {
      setSyncActionError(formatSyncJobError(formatFetchError(err, "Global sync failed")));
    } finally {
      setGlobalSyncPending(false);
      setPendingSyncSources(new Set());
    }
  }, [config, refreshSyncJobs]);

  const value = useMemo(
    () => ({
      config,
      statuses,
      syncJobs,
      syncProgress,
      syncActionError,
      pendingSyncSources,
      globalSyncPending,
      updateConfig,
      connect,
      disconnect,
      getStatus,
      triggerGlobalSync,
      triggerSourceSync,
      refreshSyncJobs,
    }),
    [
      config,
      statuses,
      syncJobs,
      syncProgress,
      syncActionError,
      pendingSyncSources,
      globalSyncPending,
      updateConfig,
      connect,
      disconnect,
      getStatus,
      triggerGlobalSync,
      triggerSourceSync,
      refreshSyncJobs,
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
