"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, FileSpreadsheet, LayoutGrid, Loader2, Network, Sparkles } from "lucide-react";

import { EmployeeEditModal } from "@/components/onboarding/EmployeeEditModal";
import { AddEmployeeModal, type NewEmployeeDraft } from "@/components/org-workspace/AddEmployeeModal";
import { OrgBulkCsvDialog } from "@/components/org-workspace/OrgBulkCsvDialog";
import { OrgHierarchyChartView } from "@/components/org-workspace/OrgHierarchyChartView";
import { OrgListGridView } from "@/components/org-workspace/OrgListGridView";
import { TeamTagBar } from "@/components/org-workspace/TeamTagBar";
import { collectOrgRoles } from "@/lib/org-master-data";
import { generateUniqueEmployeeId } from "@/lib/employee-id";
import type { Assignment, Employee, OrgChartPayload } from "@/lib/types";

type OrgTab = "list" | "chart";

export interface OrgWorkspaceProps {
  mode: "onboarding" | "settings";
  orgChart: OrgChartPayload;
  masterDataSources?: string[] | null;
  hierarchyMode?: "flat" | "structured" | null;
  isSaving?: boolean;
  error?: string | null;
  onReparent: (employeeId: string, managerId: string | null) => void;
  onAssignTeam: (employeeIds: string[], teamName: string) => void;
  onReplaceOrgChart: (orgChart: OrgChartPayload) => void;
  onUpdateEmployee?: (
    employee: Employee,
    assignments: Assignment[],
  ) => void | Promise<void>;
  onAddEmployee?: (employee: Employee) => void | Promise<void>;
  onSave: () => Promise<void>;
  backHref?: string;
  backLabel?: string;
}

export function OrgWorkspace({
  mode,
  orgChart,
  masterDataSources,
  hierarchyMode,
  isSaving = false,
  error,
  onReparent,
  onAssignTeam,
  onReplaceOrgChart,
  onUpdateEmployee,
  onAddEmployee,
  onSave,
  backHref,
  backLabel = "Back",
}: OrgWorkspaceProps) {
  const router = useRouter();
  const [tab, setTab] = useState<OrgTab>("list");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [bulkCsvOpen, setBulkCsvOpen] = useState(false);
  const [addEmployeeOpen, setAddEmployeeOpen] = useState(false);
  const [isAddingEmployee, setIsAddingEmployee] = useState(false);
  const [focusEmployeeId, setFocusEmployeeId] = useState<string | null>(null);

  const availableRoles = useMemo(
    () => collectOrgRoles(orgChart.employees),
    [orgChart.employees],
  );

  function toggleSelect(employeeId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(employeeId)) next.delete(employeeId);
      else next.add(employeeId);
      return next;
    });
  }

  function handleAssignTeam(teamName: string) {
    onAssignTeam([...selectedIds], teamName);
    setSelectedIds(new Set());
  }

  async function handleEmployeeSave(
    employee: Employee,
    assignments: Assignment[],
  ) {
    if (!onUpdateEmployee) return;
    setIsEditing(true);
    try {
      await onUpdateEmployee(employee, assignments);
      setEditingEmployee(null);
    } finally {
      setIsEditing(false);
    }
  }

  async function handleAddEmployeeSave(draft: NewEmployeeDraft) {
    if (!onAddEmployee) return;

    const employee: Employee = {
      id: generateUniqueEmployeeId(draft.email, orgChart.employees),
      name: draft.name,
      email: draft.email,
      role: draft.role,
      team_name: draft.team_name,
      manager_id: draft.manager_id,
      tenure_years: 0,
    };

    setIsAddingEmployee(true);
    try {
      await onAddEmployee(employee);
      setFocusEmployeeId(employee.id);
      setAddEmployeeOpen(false);
    } finally {
      setIsAddingEmployee(false);
    }
  }

  const title =
    mode === "onboarding" ? "Org Chart Setup" : "Organization Chart";
  const subtitle =
    mode === "onboarding"
      ? "Drag to re-parent employees, assign team tags, then ingest to Cognee."
      : "Manage reporting lines and team groupings for your workspace.";

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6 sm:p-8">
      <header className="space-y-4">
        {backHref && (
          <Link
            href={backHref}
            className="inline-flex items-center gap-2 text-sm text-zinc-500 transition hover:text-zinc-300"
          >
            <ArrowLeft className="h-4 w-4" />
            {backLabel}
          </Link>
        )}
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">{title}</h1>
          <p className="mt-1 text-sm text-zinc-500">{subtitle}</p>
        </div>
      </header>

      {masterDataSources && masterDataSources.length > 0 && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
          Imported {orgChart.employees.length} member
          {orgChart.employees.length === 1 ? "" : "s"} from{" "}
          {masterDataSources.join(", ")}
          {hierarchyMode === "flat"
            ? " as a flat roster — no reporting lines found in your sources. Use Chart view to assign managers."
            : " with reporting lines from your connected sources."}
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-1 gap-2 rounded-lg border border-zinc-800 bg-zinc-900/50 p-1">
          <button
            type="button"
            onClick={() => setTab("list")}
            className={`flex flex-1 items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm transition ${
              tab === "list"
                ? "bg-zinc-100 text-slate-950"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <LayoutGrid className="h-4 w-4" />
            List Grid View
          </button>
          <button
            type="button"
            onClick={() => setTab("chart")}
            className={`flex flex-1 items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm transition ${
              tab === "chart"
                ? "bg-zinc-100 text-slate-950"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Network className="h-4 w-4" />
            Hierarchical Chart View
          </button>
        </div>
        <button
          type="button"
          onClick={() => setBulkCsvOpen(true)}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg border border-zinc-700 px-4 py-2.5 text-sm text-zinc-300 transition hover:bg-zinc-900"
        >
          <FileSpreadsheet className="h-4 w-4" />
          CSV Import / Export
        </button>
      </div>

      <TeamTagBar
        selectedCount={selectedIds.size}
        onAssign={handleAssignTeam}
        onClearSelection={() => setSelectedIds(new Set())}
      />

      {tab === "list" ? (
        <OrgListGridView
          employees={orgChart.employees}
          selectedIds={selectedIds}
          onToggleSelect={toggleSelect}
          onReparent={onReparent}
          onEditEmployee={onUpdateEmployee ? setEditingEmployee : undefined}
          onAddEmployee={onAddEmployee ? () => setAddEmployeeOpen(true) : undefined}
        />
      ) : (
        <OrgHierarchyChartView
          employees={orgChart.employees}
          selectedIds={selectedIds}
          onToggleSelect={toggleSelect}
          onReparent={onReparent}
          onEditEmployee={onUpdateEmployee ? setEditingEmployee : undefined}
          onAddEmployee={onAddEmployee ? () => setAddEmployeeOpen(true) : undefined}
          focusEmployeeId={focusEmployeeId}
          onFocusHandled={() => setFocusEmployeeId(null)}
        />
      )}

      {bulkCsvOpen && (
        <OrgBulkCsvDialog
          orgChart={orgChart}
          applyLocally={mode === "onboarding"}
          onApplied={onReplaceOrgChart}
          onClose={() => setBulkCsvOpen(false)}
        />
      )}

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {editingEmployee && onUpdateEmployee && (
        <EmployeeEditModal
          employee={editingEmployee}
          orgChart={orgChart}
          availableRoles={availableRoles}
          isSaving={isEditing}
          onClose={() => setEditingEmployee(null)}
          onSave={handleEmployeeSave}
        />
      )}

      {addEmployeeOpen && onAddEmployee && (
        <AddEmployeeModal
          employees={orgChart.employees}
          availableRoles={availableRoles}
          isSaving={isAddingEmployee}
          onClose={() => setAddEmployeeOpen(false)}
          onSave={handleAddEmployeeSave}
        />
      )}

      <div className="flex flex-col gap-3 sm:flex-row">
        {mode === "onboarding" && (
          <button
            type="button"
            onClick={() => router.push("/onboarding")}
            disabled={isSaving}
            className="rounded-lg border border-zinc-700 px-4 py-2.5 text-sm text-zinc-300 transition hover:bg-zinc-900 disabled:opacity-50"
          >
            Back to Integrations
          </button>
        )}
        <button
          type="button"
          onClick={() => void onSave()}
          disabled={isSaving}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSaving ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              {mode === "onboarding" ? "Ingesting to Cognee…" : "Saving…"}
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              {mode === "onboarding"
                ? "Confirm & Ingest to Cognee"
                : "Save & Sync to Cognee"}
            </>
          )}
        </button>
      </div>
    </div>
  );
}
