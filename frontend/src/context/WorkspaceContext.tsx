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

import { fetchDashboardMetrics } from "@/lib/api";
import type { DashboardMetrics, DigestSettings } from "@/lib/types";

const DIGEST_STORAGE_KEY = "empulse-digest-settings";

const DEFAULT_DIGEST: DigestSettings = {
  enabled: false,
  cron: "0 9 * * 1",
};

interface WorkspaceContextValue {
  metrics: DashboardMetrics | null;
  digest: DigestSettings;
  loading: boolean;
  operationalRevision: number;
  refreshMetrics: () => Promise<void>;
  refreshOperationalState: () => Promise<void>;
  setDigest: (settings: Partial<DigestSettings>) => void;
  notifyIncidentResolved: () => void;
  notifySpofResolved: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

function loadDigestSettings(): DigestSettings {
  if (typeof window === "undefined") return DEFAULT_DIGEST;
  try {
    const raw = localStorage.getItem(DIGEST_STORAGE_KEY);
    return raw ? { ...DEFAULT_DIGEST, ...JSON.parse(raw) } : DEFAULT_DIGEST;
  } catch {
    return DEFAULT_DIGEST;
  }
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [digest, setDigestState] = useState<DigestSettings>(DEFAULT_DIGEST);
  const [loading, setLoading] = useState(true);
  const [operationalRevision, setOperationalRevision] = useState(0);

  const refreshMetrics = useCallback(async () => {
    try {
      const data = await fetchDashboardMetrics();
      setMetrics(data);
    } catch {
      setMetrics(null);
    }
  }, []);

  const refreshOperationalState = useCallback(async () => {
    await refreshMetrics();
    setOperationalRevision((prev) => prev + 1);
  }, [refreshMetrics]);

  useEffect(() => {
    setDigestState(loadDigestSettings());
    refreshMetrics().finally(() => setLoading(false));
  }, [refreshMetrics]);

  const setDigest = useCallback((settings: Partial<DigestSettings>) => {
    setDigestState((prev) => {
      const next = { ...prev, ...settings };
      localStorage.setItem(DIGEST_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const notifyIncidentResolved = useCallback(() => {
    setMetrics((prev) =>
      prev
        ? {
            ...prev,
            open_incident_count: Math.max(0, prev.open_incident_count - 1),
          }
        : prev,
    );
    void refreshOperationalState();
  }, [refreshOperationalState]);

  const notifySpofResolved = useCallback(() => {
    setMetrics((prev) =>
      prev
        ? {
            ...prev,
            active_spof_count: Math.max(0, prev.active_spof_count - 1),
          }
        : prev,
    );
    void refreshOperationalState();
  }, [refreshOperationalState]);

  const value = useMemo(
    () => ({
      metrics,
      digest,
      loading,
      operationalRevision,
      refreshMetrics,
      refreshOperationalState,
      setDigest,
      notifyIncidentResolved,
      notifySpofResolved,
    }),
    [
      metrics,
      digest,
      loading,
      operationalRevision,
      refreshMetrics,
      refreshOperationalState,
      setDigest,
      notifyIncidentResolved,
      notifySpofResolved,
    ],
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error("useWorkspace must be used within WorkspaceProvider");
  }
  return context;
}
