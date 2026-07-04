"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Boxes,
  FileSpreadsheet,
  Fingerprint,
  LayoutGrid,
  Loader2,
  Network,
  Sparkles,
  Users,
} from "lucide-react";

import { IdentityMappingPanel } from "@/components/identity-mapping/IdentityMappingPanel";
import { EmployeeEditModal } from "@/components/onboarding/EmployeeEditModal";
import { AddEmployeeModal, type NewEmployeeDraft } from "@/components/org-workspace/AddEmployeeModal";
import { OrgBulkCsvDialog } from "@/components/org-workspace/OrgBulkCsvDialog";
import { OrgComponentsPanel } from "@/components/org-workspace/OrgComponentsPanel";
import { OrgHierarchyChartView } from "@/components/org-workspace/OrgHierarchyChartView";
import { OrgListGridView } from "@/components/org-workspace/OrgListGridView";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { WorkspacePageHeader } from "@/components/ui/WorkspacePageHeader";
import { collectOrgRoles } from "@/lib/org-master-data";
import { generateUniqueEmployeeId } from "@/lib/employee-id";
import type { Assignment, Employee, OrgChartPayload } from "@/lib/types";

export type OrgMainTab = "people" | "components" | "identity";
type PeopleView = "list" | "chart";

export interface OrgWorkspaceProps {
  mode: "onboarding" | "settings";
  orgChart: OrgChartPayload;
  masterDataSources?: string[] | null;
  hierarchyMode?: "flat" | "structured" | null;
  isSaving?: boolean;
  savingLabel?: string;
  error?: string | null;
  initialTab?: OrgMainTab;
  focusIdentityEmployeeId?: string | null;
  onReparent: (employeeId: string, managerId: string | null) => void;
  onAssignTeam: (employeeIds: string[], teamName: string) => void;
  onReplaceOrgChart: (orgChart: OrgChartPayload) => void;
  onUpdateEmployee?: (
    employee: Employee,
    assignments: Assignment[],
  ) => void | Promise<void>;
  onDeleteEmployee?: (employeeId: string) => void | Promise<void>;
  onAddEmployee?: (employee: Employee) => void | Promise<void>;
  onSave: () => Promise<void>;
  backHref?: string;
  backLabel?: string;
  onRefreshOrgChart?: () => void | Promise<void>;
  isRefreshingOrgChart?: boolean;
  onUpdateComponent?: (
    componentId: string,
    payload: {
      name: string;
      tags: string;
      criticality: "tier1_revenue" | "tier2_core" | "tier3_support";
    },
  ) => void | Promise<void>;
  onDeleteComponent?: (componentId: string) => void | Promise<void>;
  isSavingComponent?: boolean;
  isDeletingComponent?: boolean;
  onTabChange?: (tab: OrgMainTab, employeeId?: string | null) => void;
  hasUnsavedChanges?: boolean;
  onDiscardUnsavedChanges?: () => void;
}

function StatPill({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent: string;
}) {
  return (
    <div
      className={`rounded-xl border px-3 py-2 backdrop-blur-sm ${accent}`}
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-500">
        {label}
      </p>
      <p className="mt-0.5 text-lg font-semibold tabular-nums text-zinc-100">
        {value}
      </p>
    </div>
  );
}

function MainTabButton({
  active,
  onClick,
  icon: Icon,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  count?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex h-10 min-w-0 flex-1 items-center justify-center gap-2 rounded-lg px-3 text-sm font-medium transition ${
        active
          ? "bg-zinc-100 text-slate-950"
          : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200"
      }`}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span className="truncate">{label}</span>
      {count !== undefined ? (
        <span
          className={`shrink-0 rounded-full px-1.5 py-0.5 text-[11px] font-semibold tabular-nums ${
            active ? "bg-slate-900/10 text-slate-800" : "bg-zinc-800 text-zinc-400"
          }`}
        >
          {count}
        </span>
      ) : null}
    </button>
  );
}

function PeopleViewToggle({
  view,
  onChange,
}: {
  view: PeopleView;
  onChange: (view: PeopleView) => void;
}) {
  return (
    <div className="inline-flex h-10 rounded-xl border border-zinc-800/80 bg-zinc-950/70 p-1 shadow-inner shadow-black/20">
      <button
        type="button"
        onClick={() => onChange("chart")}
        className={`inline-flex h-8 items-center gap-2 rounded-lg px-3 text-sm font-medium transition ${
          view === "chart"
            ? "bg-gradient-to-br from-emerald-500/20 to-teal-500/10 text-emerald-200 ring-1 ring-emerald-500/30"
            : "text-zinc-500 hover:text-zinc-300"
        }`}
      >
        <Network className="h-4 w-4" />
        Chart view
      </button>
      <button
        type="button"
        onClick={() => onChange("list")}
        className={`inline-flex h-8 items-center gap-2 rounded-lg px-3 text-sm font-medium transition ${
          view === "list"
            ? "bg-gradient-to-br from-violet-500/20 to-indigo-500/10 text-violet-200 ring-1 ring-violet-500/30"
            : "text-zinc-500 hover:text-zinc-300"
        }`}
      >
        <LayoutGrid className="h-4 w-4" />
        List view
      </button>
    </div>
  );
}

export function OrgWorkspace({
  mode,
  orgChart,
  masterDataSources,
  hierarchyMode,
  isSaving = false,
  savingLabel,
  error,
  initialTab = "people",
  focusIdentityEmployeeId = null,
  onReparent,
  onAssignTeam,
  onReplaceOrgChart,
  onUpdateEmployee,
  onDeleteEmployee,
  onAddEmployee,
  onSave,
  backHref,
  backLabel = "Back",
  onRefreshOrgChart,
  isRefreshingOrgChart = false,
  onUpdateComponent,
  onDeleteComponent,
  isSavingComponent = false,
  isDeletingComponent = false,
  onTabChange,
  hasUnsavedChanges = false,
  onDiscardUnsavedChanges,
}: OrgWorkspaceProps) {
  const router = useRouter();
  const [mainTab, setMainTab] = useState<OrgMainTab>(initialTab);
  const [peopleView, setPeopleView] = useState<PeopleView>("chart");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isDeletingEmployee, setIsDeletingEmployee] = useState(false);
  const [deletingEmployeeId, setDeletingEmployeeId] = useState<string | null>(null);
  const [bulkCsvOpen, setBulkCsvOpen] = useState(false);
  const [addEmployeeOpen, setAddEmployeeOpen] = useState(false);
  const [isAddingEmployee, setIsAddingEmployee] = useState(false);
  const [focusEmployeeId, setFocusEmployeeId] = useState<string | null>(null);
  const [identityFocusEmployeeId, setIdentityFocusEmployeeId] = useState<
    string | null
  >(focusIdentityEmployeeId);
  const [pendingTabSwitch, setPendingTabSwitch] = useState<{
    tab: OrgMainTab;
    employeeId?: string | null;
  } | null>(null);
  const [hasUnsavedIdentityChanges, setHasUnsavedIdentityChanges] = useState(false);
  const [pendingDeleteEmployeeId, setPendingDeleteEmployeeId] = useState<string | null>(
    null,
  );

  useEffect(() => {
    setMainTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    setIdentityFocusEmployeeId(focusIdentityEmployeeId);
  }, [focusIdentityEmployeeId]);

  const availableRoles = useMemo(
    () => collectOrgRoles(orgChart.employees),
    [orgChart.employees],
  );

  const teamCount = useMemo(
    () =>
      new Set(
        orgChart.employees
          .map((employee) => employee.team_name?.trim())
          .filter(Boolean),
      ).size,
    [orgChart.employees],
  );


  function applyTabSwitch(tab: OrgMainTab, employeeId?: string | null) {
    if (hasUnsavedChanges && mode === "settings" && mainTab === "people") {
      onDiscardUnsavedChanges?.();
    }
    if (hasUnsavedIdentityChanges && mainTab === "identity") {
      setHasUnsavedIdentityChanges(false);
    }
    setMainTab(tab);
    onTabChange?.(tab, employeeId ?? null);
    if (tab === "components" && onRefreshOrgChart) {
      void onRefreshOrgChart();
    }
  }

  function attemptSwitchTab(tab: OrgMainTab, employeeId?: string | null) {
    if (tab === mainTab) return;
    const orgPeopleDirty =
      hasUnsavedChanges && mode === "settings" && mainTab === "people";
    const identityDirty = hasUnsavedIdentityChanges && mainTab === "identity";
    if (orgPeopleDirty || identityDirty) {
      setPendingTabSwitch({ tab, employeeId });
      return;
    }
    applyTabSwitch(tab, employeeId);
  }

  function switchTab(tab: OrgMainTab, employeeId?: string | null) {
    attemptSwitchTab(tab, employeeId);
  }

  function toggleSelect(employeeId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(employeeId)) {
        next.delete(employeeId);
        setFocusEmployeeId((current) =>
          current === employeeId ? null : current,
        );
      } else {
        next.add(employeeId);
      }
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

  async function handleEmployeeDelete(employeeId: string) {
    if (!onDeleteEmployee) return;
    setIsDeletingEmployee(true);
    setDeletingEmployeeId(employeeId);
    try {
      await onDeleteEmployee(employeeId);
      setEditingEmployee(null);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(employeeId);
        return next;
      });
    } finally {
      setIsDeletingEmployee(false);
      setDeletingEmployeeId(null);
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
      setSelectedIds(new Set([employee.id]));
      setAddEmployeeOpen(false);
      setPeopleView("chart");
    } finally {
      setIsAddingEmployee(false);
    }
  }


  const title = mode === "onboarding" ? "Org Chart Setup" : "Organization Hub";
  const subtitle =
    mode === "onboarding"
      ? "Drag to re-parent employees, assign team tags, then save your org chart."
      : "People, components, and identity mappings — your workspace command center.";
  const isSettings = mode === "settings";
  const panelClassName =
    "overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/40";
  const tabBarClassName =
    "flex h-12 shrink-0 gap-1 rounded-xl border border-zinc-800 bg-zinc-900/40 p-1";

  const saveButtonLabel =
    mode === "onboarding" ? "Confirm & save people" : "Save people";

  const saveButton = (
    <button
      type="button"
      onClick={() => void onSave()}
      disabled={isSaving || (isSettings && !hasUnsavedChanges)}
      className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 px-4 py-2 text-sm font-medium text-white shadow-md shadow-emerald-900/20 transition hover:from-emerald-500 hover:to-teal-500 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {isSaving ? (
        <>
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          {savingLabel ?? "Saving people…"}
        </>
      ) : (
        <>
          <Sparkles className="h-3.5 w-3.5" />
          {saveButtonLabel}
        </>
      )}
    </button>
  );

  const peopleSaveFooter = isSettings ? (
    <div className="flex shrink-0 items-center justify-end gap-3 border-t border-zinc-800/80 bg-zinc-950/50 px-4 py-3">
      {hasUnsavedChanges ? (
        <span className="mr-auto text-xs font-medium text-amber-300">
          Unsaved people changes
        </span>
      ) : null}
      {saveButton}
    </div>
  ) : null;

  const listView = (
    <OrgListGridView
      embedded
      employees={orgChart.employees}
      components={orgChart.components}
      assignments={orgChart.assignments}
      selectedIds={selectedIds}
      onToggleSelect={toggleSelect}
      onReparent={onReparent}
      onAssignTeam={handleAssignTeam}
      onClearSelection={() => setSelectedIds(new Set())}
      onEditEmployee={onUpdateEmployee ? setEditingEmployee : undefined}
      onDeleteEmployee={onDeleteEmployee ? setPendingDeleteEmployeeId : undefined}
      deletingEmployeeId={deletingEmployeeId}
      onAddEmployee={onAddEmployee ? () => setAddEmployeeOpen(true) : undefined}
    />
  );

  const chartView = (
    <OrgHierarchyChartView
      embedded
      employees={orgChart.employees}
      selectedIds={selectedIds}
      onToggleSelect={toggleSelect}
      onReparent={onReparent}
      onAssignTeam={handleAssignTeam}
      onClearSelection={() => setSelectedIds(new Set())}
      onEditEmployee={onUpdateEmployee ? setEditingEmployee : undefined}
      onDeleteEmployee={
        onDeleteEmployee
          ? (employeeId) => setPendingDeleteEmployeeId(employeeId)
          : undefined
      }
      onAddEmployee={onAddEmployee ? () => setAddEmployeeOpen(true) : undefined}
      focusEmployeeId={focusEmployeeId}
      onFocusHandled={() => setFocusEmployeeId(null)}
    />
  );

  return (
    <div
      className={
        isSettings
          ? "flex min-h-[calc(100vh-10rem)] flex-col space-y-6"
          : "relative mx-auto flex min-h-[calc(100vh-10rem)] max-w-7xl flex-col space-y-6"
      }
    >
      {!isSettings && mode !== "onboarding" ? (
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-56 bg-gradient-to-b from-emerald-500/[0.07] via-violet-500/[0.04] to-transparent"
          aria-hidden
        />
      ) : null}

      <header className={isSettings ? "space-y-4" : "relative space-y-5"}>
        {backHref ? (
          <Link
            href={backHref}
            className="inline-flex items-center gap-2 text-sm text-zinc-500 transition hover:text-zinc-300"
          >
            <ArrowLeft className="h-4 w-4" />
            {backLabel}
          </Link>
        ) : null}

        <WorkspacePageHeader title={title} subtitle={subtitle} />

        {isSettings ? (
          <div className="grid max-w-md grid-cols-3 gap-3">
            <StatPill
              label="People"
              value={orgChart.employees.length}
              accent="border-zinc-800 bg-zinc-900/40"
            />
            <StatPill
              label="Components"
              value={orgChart.components.length}
              accent="border-zinc-800 bg-zinc-900/40"
            />
            <StatPill
              label="Teams"
              value={teamCount}
              accent="border-zinc-800 bg-zinc-900/40"
            />
          </div>
        ) : null}
      </header>

      {masterDataSources && masterDataSources.length > 0 ? (
        <div className="relative rounded-2xl border border-emerald-500/25 bg-gradient-to-r from-emerald-500/10 via-emerald-500/5 to-transparent px-4 py-3.5 text-sm text-emerald-100">
          Imported {orgChart.employees.length} member
          {orgChart.employees.length === 1 ? "" : "s"} from{" "}
          <span className="font-medium">{masterDataSources.join(", ")}</span>
          {hierarchyMode === "flat"
            ? " as a flat roster — use Chart view to assign managers."
            : " with reporting lines from your connected sources."}
        </div>
      ) : null}

      <div className="flex flex-1 flex-col space-y-6">
      <div className={tabBarClassName}>
          <MainTabButton
            active={mainTab === "people"}
            onClick={() => switchTab("people")}
            icon={Users}
            label="People"
            count={orgChart.employees.length}
          />
          <MainTabButton
            active={mainTab === "components"}
            onClick={() => switchTab("components")}
            icon={Boxes}
            label="Components"
            count={orgChart.components.length}
          />
          {mode === "settings" ? (
            <MainTabButton
              active={mainTab === "identity"}
              onClick={() => switchTab("identity")}
              icon={Fingerprint}
              label="Identity Mapping"
            />
          ) : null}
        </div>

      {mainTab === "people" ? (
        <div className="relative flex flex-col gap-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <PeopleViewToggle view={peopleView} onChange={setPeopleView} />
            <button
              type="button"
              onClick={() => setBulkCsvOpen(true)}
              className="inline-flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:border-zinc-600 hover:text-zinc-100"
            >
              <FileSpreadsheet className="h-3.5 w-3.5" />
              CSV Import / Export
            </button>
          </div>

          <div className={`${panelClassName} flex flex-col`}>
            <div className="min-h-0 flex-1">
              {peopleView === "chart" ? chartView : listView}
            </div>
            {peopleSaveFooter}
          </div>
        </div>
      ) : null}

      {mainTab === "components" ? (
        <div className={`relative ${panelClassName} p-4 sm:p-5`}>
          <OrgComponentsPanel
            orgChart={orgChart}
            isRefreshing={isRefreshingOrgChart}
            onRefresh={onRefreshOrgChart}
            onUpdateComponent={onUpdateComponent}
            onDeleteComponent={onDeleteComponent}
            isSavingComponent={isSavingComponent}
            isDeletingComponent={isDeletingComponent}
          />
        </div>
      ) : null}

      {mode === "settings" && mainTab === "identity" ? (
        <div className={`relative ${panelClassName} p-4 sm:p-5`}>
          <IdentityMappingPanel
            focusEmployeeId={identityFocusEmployeeId}
            onDirtyChange={setHasUnsavedIdentityChanges}
          />
        </div>
      ) : null}

      {bulkCsvOpen ? (
        <OrgBulkCsvDialog
          orgChart={orgChart}
          applyLocally={mode === "onboarding"}
          onApplied={onReplaceOrgChart}
          onClose={() => setBulkCsvOpen(false)}
        />
      ) : null}

      {error ? (
        <div className="rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      ) : null}

      {editingEmployee && onUpdateEmployee ? (
        <EmployeeEditModal
          employee={editingEmployee}
          orgChart={orgChart}
          availableRoles={availableRoles}
          isSaving={isEditing}
          isDeleting={isDeletingEmployee}
          allowDelete={Boolean(onDeleteEmployee)}
          onClose={() => setEditingEmployee(null)}
          onSave={handleEmployeeSave}
          onDelete={onDeleteEmployee ? handleEmployeeDelete : undefined}
        />
      ) : null}

      {addEmployeeOpen && onAddEmployee ? (
        <AddEmployeeModal
          employees={orgChart.employees}
          availableRoles={availableRoles}
          isSaving={isAddingEmployee}
          onClose={() => setAddEmployeeOpen(false)}
          onSave={handleAddEmployeeSave}
        />
      ) : null}

      <ConfirmDialog
        open={pendingTabSwitch !== null}
        title="Discard unsaved changes?"
        description={
          pendingTabSwitch && mainTab === "identity"
            ? "Identity mapping edits are not saved yet. Discard them and switch tabs, or cancel and click Save mappings first."
            : "People changes are not saved yet. Discard them and switch tabs, or cancel and use Save people first."
        }
        confirmLabel="Discard & switch"
        cancelLabel="Stay on tab"
        onConfirm={() => {
          if (!pendingTabSwitch) return;
          applyTabSwitch(pendingTabSwitch.tab, pendingTabSwitch.employeeId);
          setPendingTabSwitch(null);
        }}
        onCancel={() => setPendingTabSwitch(null)}
      />

      <ConfirmDialog
        open={pendingDeleteEmployeeId !== null}
        title="Remove team member?"
        description={
          pendingDeleteEmployeeId
            ? `Remove ${
                orgChart.employees.find((item) => item.id === pendingDeleteEmployeeId)
                  ?.name ?? "this person"
              } from the organization? This cannot be undone.`
            : ""
        }
        confirmLabel="Remove"
        cancelLabel="Cancel"
        onConfirm={() => {
          if (pendingDeleteEmployeeId && onDeleteEmployee) {
            void handleEmployeeDelete(pendingDeleteEmployeeId);
          }
          setPendingDeleteEmployeeId(null);
        }}
        onCancel={() => setPendingDeleteEmployeeId(null)}
      />
      </div>

      {mode === "onboarding" ? (
        <div className="mt-auto flex items-center justify-between gap-3 border-t border-zinc-800/60 pt-4">
          <button
            type="button"
            onClick={() => router.push("/onboarding")}
            disabled={isSaving}
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-50"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Integrations
          </button>
          {saveButton}
        </div>
      ) : null}
    </div>
  );
}
