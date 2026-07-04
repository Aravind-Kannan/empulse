"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { GitBranch } from "lucide-react";

import { OrgWorkspace, type OrgMainTab } from "@/components/org-workspace/OrgWorkspace";
import { PanelDataLoader } from "@/components/ui/PanelDataLoader";
import { WorkspacePageHeader } from "@/components/ui/WorkspacePageHeader";
import { consolidateOrgComponents, deleteOrgEmployee, deleteOrgComponent, fetchOrgChart, ingestOrgChart, updateOrgComponent, updateOrgEmployee } from "@/lib/api";
import { mergeOrgChartForSave, removeEmployeeFromOrgChart, wouldCreateCycle } from "@/lib/org-tree-utils";
import type { Assignment, Employee, OrgChartPayload } from "@/lib/types";
import { useWorkspace } from "@/context/WorkspaceContext";

function parseMainTab(value: string | null): OrgMainTab {
  if (value === "components" || value === "identity") {
    return value;
  }
  return "people";
}

export function SettingsOrgChartPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialTab = parseMainTab(searchParams.get("tab"));
  const focusIdentityEmployeeId = searchParams.get("employee");
  const { refreshOperationalState } = useWorkspace();
  const [orgChart, setOrgChart] = useState<OrgChartPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [savingLabel, setSavingLabel] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSavingComponent, setIsSavingComponent] = useState(false);
  const [isDeletingComponent, setIsDeletingComponent] = useState(false);
  const dirtyReportingEmployeeIds = useRef(new Set<string>());
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  const markDirty = useCallback((employeeIds: string | string[]) => {
    const ids = Array.isArray(employeeIds) ? employeeIds : [employeeIds];
    for (const id of ids) {
      dirtyReportingEmployeeIds.current.add(id);
    }
    setHasUnsavedChanges(true);
  }, []);

  const discardUnsavedChanges = useCallback(async () => {
    try {
      const fresh = await fetchOrgChart();
      setOrgChart(fresh);
      dirtyReportingEmployeeIds.current.clear();
      setHasUnsavedChanges(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reload org chart");
    }
  }, []);

  const handleTabChange = useCallback(
    (tab: OrgMainTab, employeeId?: string | null) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("tab", tab);
      if (tab === "identity" && employeeId) {
        params.set("employee", employeeId);
      } else {
        params.delete("employee");
      }
      const query = params.toString();
      router.replace(
        query ? `/settings/org-chart?${query}` : "/settings/org-chart",
        { scroll: false },
      );
    },
    [router, searchParams],
  );

  const reloadOrgChart = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await consolidateOrgComponents();
      const fresh = await fetchOrgChart();
      setOrgChart(fresh);
      dirtyReportingEmployeeIds.current.clear();
      setHasUnsavedChanges(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh org chart");
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void fetchOrgChart()
      .then(setOrgChart)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load org chart"),
      )
      .finally(() => setIsLoading(false));
  }, []);

  const reparentEmployee = useCallback(
    (employeeId: string, managerId: string | null) => {
      setOrgChart((prev) => {
        if (!prev || wouldCreateCycle(prev.employees, employeeId, managerId)) {
          return prev;
        }
        dirtyReportingEmployeeIds.current.add(employeeId);
        setHasUnsavedChanges(true);
        return {
          ...prev,
          employees: prev.employees.map((employee) =>
            employee.id === employeeId
              ? { ...employee, manager_id: managerId }
              : employee,
          ),
        };
      });
    },
    [],
  );

  const assignTeamTag = useCallback(
    (employeeIds: string[], teamName: string) => {
      const trimmed = teamName.trim();
      setOrgChart((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          employees: prev.employees.map((employee) =>
            employeeIds.includes(employee.id)
              ? { ...employee, team_name: trimmed || null }
              : employee,
          ),
        };
      });
      markDirty(employeeIds);
    },
    [markDirty],
  );

  const handleUpdateEmployee = useCallback(
    async (employee: Employee, assignments: Assignment[]) => {
      await updateOrgEmployee(employee.id, {
        name: employee.name,
        role: employee.role,
        email: employee.email,
        tenure_years: employee.tenure_years,
        manager_id: employee.manager_id,
        team_name: employee.team_name ?? null,
        assignments: {
          component_ids: assignments.map((item) => item.component_id),
        },
      });

      dirtyReportingEmployeeIds.current.delete(employee.id);

      setOrgChart((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          employees: prev.employees.map((item) =>
            item.id === employee.id ? employee : item,
          ),
          assignments: [
            ...prev.assignments.filter((item) => item.employee_id !== employee.id),
            ...assignments,
          ],
        };
      });

      await refreshOperationalState();
    },
    [refreshOperationalState],
  );

  const handleDeleteEmployee = useCallback(
    async (employeeId: string) => {
      await deleteOrgEmployee(employeeId);

      setOrgChart((prev) =>
        prev ? removeEmployeeFromOrgChart(prev, employeeId) : prev,
      );

      await refreshOperationalState();
    },
    [refreshOperationalState],
  );

  const handleAddEmployee = useCallback(async (employee: Employee) => {
    setOrgChart((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        employees: [...prev.employees, employee],
      };
    });
  }, []);

  const handleUpdateComponent = useCallback(
    async (
      componentId: string,
      payload: {
        name: string;
        tags: string;
        criticality: "tier1_revenue" | "tier2_core" | "tier3_support";
      },
    ) => {
      setIsSavingComponent(true);
      try {
        await updateOrgComponent(componentId, payload);
        setOrgChart((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            components: prev.components.map((component) =>
              component.id === componentId
                ? { ...component, ...payload }
                : component,
            ),
          };
        });
        await refreshOperationalState();
      } finally {
        setIsSavingComponent(false);
      }
    },
    [refreshOperationalState],
  );

  const handleDeleteComponent = useCallback(
    async (componentId: string) => {
      setIsDeletingComponent(true);
      try {
        await deleteOrgComponent(componentId);
        setOrgChart((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            components: prev.components.filter(
              (component) => component.id !== componentId,
            ),
            assignments: prev.assignments.filter(
              (assignment) => assignment.component_id !== componentId,
            ),
          };
        });
        await refreshOperationalState();
      } finally {
        setIsDeletingComponent(false);
      }
    },
    [refreshOperationalState],
  );

  async function handleSave() {
    if (!orgChart) return;
    setIsSaving(true);
    setSavingLabel("Saving people…");
    setError(null);
    try {
      const fresh = await fetchOrgChart();
      const payload = mergeOrgChartForSave(
        orgChart,
        fresh,
        dirtyReportingEmployeeIds.current,
      );
      await ingestOrgChart(payload, {
        onStatus: (status) => {
          if (status.status === "queued" || status.status === "running") {
            setSavingLabel("Updating org graph…");
          }
        },
      });
      const saved = await fetchOrgChart();
      setOrgChart(saved);
      dirtyReportingEmployeeIds.current.clear();
      setHasUnsavedChanges(false);
      await refreshOperationalState();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <WorkspacePageHeader
          title="Organization Hub"
          subtitle="People, components, and identity mappings — your workspace command center."
        />
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40">
          <PanelDataLoader
            icon={GitBranch}
            label="Loading organization chart…"
            sublabel="Fetching employees, reporting lines, and component assignments."
            steps={[
              "Loading employee roster",
              "Building hierarchy",
              "Resolving component ownership",
            ]}
          />
        </div>
      </div>
    );
  }

  if (!orgChart) {
    return (
      <div className="p-8 text-sm text-red-300">
        {error ?? "Unable to load org chart."}
      </div>
    );
  }

  return (
    <OrgWorkspace
      mode="settings"
      orgChart={orgChart}
      initialTab={initialTab}
      focusIdentityEmployeeId={focusIdentityEmployeeId}
      onTabChange={handleTabChange}
      isSaving={isSaving}
      savingLabel={savingLabel}
      error={error}
      onReparent={reparentEmployee}
      onAssignTeam={assignTeamTag}
      onReplaceOrgChart={(next) => {
        setOrgChart(next);
        void refreshOperationalState();
      }}
      onUpdateEmployee={handleUpdateEmployee}
      onDeleteEmployee={handleDeleteEmployee}
      onAddEmployee={handleAddEmployee}
      onSave={handleSave}
      onRefreshOrgChart={reloadOrgChart}
      isRefreshingOrgChart={isRefreshing}
      onUpdateComponent={handleUpdateComponent}
      onDeleteComponent={handleDeleteComponent}
      isSavingComponent={isSavingComponent}
      isDeletingComponent={isDeletingComponent}
      hasUnsavedChanges={hasUnsavedChanges}
      onDiscardUnsavedChanges={() => void discardUnsavedChanges()}
    />
  );
}
