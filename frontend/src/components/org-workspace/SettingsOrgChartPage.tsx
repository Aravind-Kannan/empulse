"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { OrgWorkspace } from "@/components/org-workspace/OrgWorkspace";
import { fetchOrgChart, ingestOrgChart, updateOrgEmployee } from "@/lib/api";
import { wouldCreateCycle } from "@/lib/org-tree-utils";
import type { Assignment, Employee, OrgChartPayload } from "@/lib/types";
import { useWorkspace } from "@/context/WorkspaceContext";

export function SettingsOrgChartPage() {
  const { refreshOperationalState } = useWorkspace();
  const [orgChart, setOrgChart] = useState<OrgChartPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [savingLabel, setSavingLabel] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);

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
    },
    [],
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

  const handleAddEmployee = useCallback(async (employee: Employee) => {
    setOrgChart((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        employees: [...prev.employees, employee],
      };
    });
  }, []);

  async function handleSave() {
    if (!orgChart) return;
    setIsSaving(true);
    setSavingLabel("Saving org chart…");
    setError(null);
    try {
      await ingestOrgChart(orgChart, {
        onStatus: (status) => {
          if (status.status === "queued" || status.status === "running") {
            setSavingLabel("Syncing to Cognee…");
          }
        },
      });
      await refreshOperationalState();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-zinc-500">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading organization chart…
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
      onAddEmployee={handleAddEmployee}
      onSave={handleSave}
      backHref="/settings"
      backLabel="Back to Settings"
    />
  );
}
