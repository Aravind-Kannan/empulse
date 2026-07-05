"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";

import { fetchEraMetrics } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import type { EraAnalyticsResponse, EraAlertItem, EraDimensionKey } from "@/lib/types";

import { EraAlertsSettingsDrawer } from "./EraAlertsSettingsDrawer";
import { EraCommandHeader } from "./EraCommandHeader";
import { EraNotificationsDrawer } from "./EraNotificationsDrawer";
import { EraOpenP1Drawer } from "./EraOpenP1Drawer";
import { EraDetailDrawer } from "./EraDetailDrawer";
import { EraEvidenceFeed } from "./EraEvidenceFeed";
import { EraKpiStrip } from "./EraKpiStrip";
import { EraRiskHeatmap } from "./EraRiskHeatmap";
import { EraTeamComposition } from "./EraTeamComposition";
import {
  buildTeamEvidenceFeed,
  totalUnmappedCount,
} from "./era-utils";

export function EraCommandCenter() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { operationalRevision } = useWorkspace();
  const [data, setData] = useState<EraAnalyticsResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerEmployeeId, setDrawerEmployeeId] = useState<string | null>(null);
  const [drawerDimensionFilter, setDrawerDimensionFilter] =
    useState<EraDimensionKey | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [alertsSettingsOpen, setAlertsSettingsOpen] = useState(false);
  const [openP1DrawerOpen, setOpenP1DrawerOpen] = useState(false);
  const [alertsRefreshKey, setAlertsRefreshKey] = useState(0);

  const openDrawer = useCallback(
    (employeeId: string, dimension: EraDimensionKey | null = null) => {
      setDrawerEmployeeId(employeeId);
      setDrawerDimensionFilter(dimension);
      setSelectedId(employeeId);
      const params = new URLSearchParams(searchParams.toString());
      params.set("employee", employeeId);
      router.replace(`/era?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  const closeDrawer = useCallback(() => {
    setDrawerEmployeeId(null);
    setDrawerDimensionFilter(null);
    const params = new URLSearchParams(searchParams.toString());
    params.delete("employee");
    const query = params.toString();
    router.replace(query ? `/era?${query}` : "/era", { scroll: false });
  }, [router, searchParams]);

  const closeAlertsSettings = useCallback(() => {
    setAlertsSettingsOpen(false);
    if (searchParams.get("configureAlerts") === "1") {
      const params = new URLSearchParams(searchParams.toString());
      params.delete("configureAlerts");
      const query = params.toString();
      router.replace(query ? `/era?${query}` : "/era", { scroll: false });
    }
  }, [router, searchParams]);

  const handleViewAlert = useCallback(
    (alert: EraAlertItem) => {
      setNotificationsOpen(false);
      if (alert.rule_id === "critical_file" && alert.employee_id) {
        openDrawer(alert.employee_id, "knowledge");
        return;
      }
      if (alert.rule_id === "unassigned_p1") {
        setOpenP1DrawerOpen(true);
        return;
      }
      if (alert.rule_id === "spof_tier1") {
        return;
      }
    },
    [openDrawer],
  );

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const response = await fetchEraMetrics();
      setData(response);
      setAlertsRefreshKey((key) => key + 1);
      setSelectedId((current) => {
        if (
          current &&
          response.employees.some((employee) => employee.employee_id === current)
        ) {
          return current;
        }
        const sorted = [...response.employees]
          .filter((employee) => !employee.excluded)
          .sort((a, b) => b.risk_factor_score - a.risk_factor_score);
        return sorted[0]?.employee_id ?? null;
      });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load metrics. Is the backend running on port 8000?",
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const deepLinked = searchParams.get("employee");
    if (deepLinked) {
      setDrawerEmployeeId(deepLinked);
      setSelectedId((current) => current ?? deepLinked);
    }
  }, [searchParams]);

  useEffect(() => {
    if (searchParams.get("configureAlerts") === "1") {
      setAlertsSettingsOpen(true);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!mounted) return;
    void load();
  }, [mounted, operationalRevision, load]);

  const employees = data?.employees ?? [];
  const activeEmployees = useMemo(
    () => employees.filter((employee) => !employee.excluded),
    [employees],
  );

  const teamEvidence = useMemo(
    () => buildTeamEvidenceFeed(activeEmployees, data?.team_evidence ?? []),
    [activeEmployees, data?.team_evidence],
  );

  if (!mounted || loading) {
    return (
      <div className="space-y-6">
        <div className="h-16 animate-pulse rounded-xl bg-zinc-900/50" />
        <EraKpiStrip
          summary={{
            avg_risk_score: 0,
            high_risk_count: 0,
            medium_risk_count: 0,
            low_risk_count: 0,
            spof_component_count: 0,
            open_p1_count: 0,
            undocumented_incident_count: 0,
            top_risk_driver: "knowledge",
            estimated_recovery_weeks: { min: 0, max: 0 },
            data_health_pct: 0,
            org_health_score: 0,
            orphan_file_count: 0,
            orphan_delta_90d: 0,
          }}
          loading
        />
        <EraRiskHeatmap
          employees={[]}
          selectedId={null}
          onSelect={() => {}}
          loading
        />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-zinc-100">ERA Command Center</h1>
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">
          {error ?? "Failed to load ERA metrics."}
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 hover:bg-white"
        >
          Retry
        </button>
      </div>
    );
  }

  if (activeEmployees.length === 0) {
    return (
      <div className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/30 p-8 text-center">
        <h1 className="text-2xl font-semibold text-zinc-100">ERA Command Center</h1>
        <p className="text-sm text-zinc-400">
          No employees in scope yet. Import your org chart to begin continuity risk
          assessment.
        </p>
        <Link
          href="/onboarding"
          className="inline-flex rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 hover:bg-white"
        >
          Import org chart
        </Link>
      </div>
    );
  }

  const unmappedCount = totalUnmappedCount(data.unmapped_activity);

  return (
    <div
      className={`space-y-6 ${
        data.demo_mode
          ? "rounded-xl border-l-4 border-amber-500/80 pl-4"
          : ""
      }`}
      title={data.demo_mode ? "Demo data — connect integrations" : undefined}
    >
      {data.demo_mode && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
          Demo data — connect integrations for live continuity signals.
        </div>
      )}

      <EraCommandHeader
        recovery={data.team_summary.estimated_recovery_weeks}
        syncFreshness={data.sync_freshness}
        warnings={data.warnings}
        unmappedCount={unmappedCount}
        alertsRefreshKey={alertsRefreshKey}
        employees={activeEmployees}
        highRiskCount={data.team_summary.high_risk_count}
        refreshing={refreshing}
        onRefresh={() => void load(true)}
        onOpenNotifications={() => setNotificationsOpen(true)}
        onOpenAlertsSettings={() => setAlertsSettingsOpen(true)}
      />

      <EraKpiStrip
        summary={data.team_summary}
        teamHistory={data.team_risk_history_30d ?? []}
        onOpenP1Issues={() => setOpenP1DrawerOpen(true)}
      />

      <EraRiskHeatmap
        employees={employees}
        selectedId={selectedId}
        onSelect={(employeeId) => {
          setSelectedId(employeeId);
          openDrawer(employeeId);
        }}
        onOpenDetailWithDimension={(employeeId, dimension) => {
          openDrawer(employeeId, dimension);
        }}
      />

      <div className="grid gap-6 xl:grid-cols-2 xl:items-stretch">
        <EraTeamComposition
          employees={employees}
          summary={data.team_summary}
          teamHistory={data.team_risk_history_30d ?? []}
          onSelectEmployee={(employeeId) => openDrawer(employeeId)}
        />
        <EraEvidenceFeed
          items={teamEvidence}
          selectedId={selectedId}
          onSelectEmployee={(employeeId) => {
            setSelectedId(employeeId);
            openDrawer(employeeId);
          }}
        />
      </div>

      {openP1DrawerOpen && (
        <EraOpenP1Drawer
          open={openP1DrawerOpen}
          onClose={() => setOpenP1DrawerOpen(false)}
        />
      )}

      {notificationsOpen && (
        <EraNotificationsDrawer
          open={notificationsOpen}
          onClose={() => setNotificationsOpen(false)}
          warnings={data.warnings}
          unmappedCount={unmappedCount}
          onOpenAlertsSettings={() => {
            setNotificationsOpen(false);
            setAlertsSettingsOpen(true);
          }}
          onViewAlert={handleViewAlert}
          onUpdated={() => {
            void load(true);
            setAlertsRefreshKey((key) => key + 1);
          }}
        />
      )}

      {alertsSettingsOpen && (
        <EraAlertsSettingsDrawer
          open={alertsSettingsOpen}
          onClose={closeAlertsSettings}
          demoMode={data.demo_mode}
        />
      )}

      {drawerEmployeeId && data && (
        <EraDetailDrawer
          employeeId={drawerEmployeeId}
          syncFreshness={data.sync_freshness}
          demoMode={data.demo_mode}
          initialDimensionFilter={drawerDimensionFilter}
          onClose={closeDrawer}
        />
      )}

      <p className="text-xs text-zinc-600">
        Directors and leadership roles are excluded from ERA scoring.
      </p>
    </div>
  );
}
