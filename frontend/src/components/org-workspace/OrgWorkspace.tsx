"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Boxes,
  FileSpreadsheet,
  Fingerprint,
  GitBranch,
  LayoutGrid,
  Loader2,
  Network,
  Pencil,
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
import { TeamTagBar } from "@/components/org-workspace/TeamTagBar";
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
      className={`relative flex flex-1 items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
        active
          ? "bg-gradient-to-br from-zinc-100 to-zinc-200 text-slate-950 shadow-lg shadow-black/20"
          : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200"
      }`}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {label}
      {count !== undefined ? (
        <span
          className={`rounded-full px-1.5 py-0.5 text-[11px] font-semibold tabular-nums ${
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
    <div className="inline-flex rounded-xl border border-zinc-800/80 bg-zinc-950/70 p-1 shadow-inner shadow-black/20">
      <button
        type="button"
        onClick={() => onChange("chart")}
        className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition ${
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
        className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition ${
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

  const selectedEmployee = useMemo(() => {
    if (selectedIds.size !== 1) return null;
    const [employeeId] = selectedIds;
    return orgChart.employees.find((employee) => employee.id === employeeId) ?? null;
  }, [orgChart.employees, selectedIds]);

  function switchTab(tab: OrgMainTab, employeeId?: string | null) {
    setMainTab(tab);
    onTabChange?.(tab, employeeId ?? null);
    if (tab === "components" && onRefreshOrgChart) {
      void onRefreshOrgChart();
    }
  }

  function toggleSelect(employeeId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(employeeId)) next.delete(employeeId);
      else next.add(employeeId);
      return next;
    });
    setFocusEmployeeId(employeeId);
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

  function openIdentityForEmployee(employeeId: string) {
    setIdentityFocusEmployeeId(employeeId);
    switchTab("identity", employeeId);
  }

  const title = mode === "onboarding" ? "Org Chart Setup" : "Organization Hub";
  const subtitle =
    mode === "onboarding"
      ? "Drag to re-parent employees, assign team tags, then ingest to Cognee."
      : "People, components, and identity mappings — your workspace command center.";

  const listView = (
    <OrgListGridView
      embedded
      employees={orgChart.employees}
      components={orgChart.components}
      assignments={orgChart.assignments}
      selectedIds={selectedIds}
      onToggleSelect={toggleSelect}
      onReparent={onReparent}
      onEditEmployee={onUpdateEmployee ? setEditingEmployee : undefined}
      onDeleteEmployee={onDeleteEmployee ? handleEmployeeDelete : undefined}
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
      onEditEmployee={onUpdateEmployee ? setEditingEmployee : undefined}
      onAddEmployee={onAddEmployee ? () => setAddEmployeeOpen(true) : undefined}
      focusEmployeeId={focusEmployeeId}
      onFocusHandled={() => setFocusEmployeeId(null)}
    />
  );

  return (
    <div className="relative mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-56 bg-gradient-to-b from-emerald-500/[0.07] via-violet-500/[0.04] to-transparent"
        aria-hidden
      />

      <header className="relative space-y-5">
        {backHref ? (
          <Link
            href={backHref}
            className="inline-flex items-center gap-2 text-sm text-zinc-500 transition hover:text-zinc-300"
          >
            <ArrowLeft className="h-4 w-4" />
            {backLabel}
          </Link>
        ) : null}

        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/15 to-violet-500/10 shadow-lg shadow-emerald-500/5">
              <GitBranch className="h-6 w-6 text-emerald-300" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-600">
                Workspace
              </p>
              <h1 className="mt-1 text-2xl font-semibold tracking-tight text-zinc-100 sm:text-3xl">
                {title}
              </h1>
              <p className="mt-1.5 max-w-2xl text-sm text-zinc-400">{subtitle}</p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 sm:gap-3">
            <StatPill
              label="People"
              value={orgChart.employees.length}
              accent="border-emerald-500/20 bg-emerald-500/5"
            />
            <StatPill
              label="Components"
              value={orgChart.components.length}
              accent="border-violet-500/20 bg-violet-500/5"
            />
            <StatPill
              label="Teams"
              value={teamCount}
              accent="border-sky-500/20 bg-sky-500/5"
            />
          </div>
        </div>
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

      <div className="relative flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-1 gap-1.5 rounded-2xl border border-zinc-800/80 bg-zinc-950/50 p-1.5 backdrop-blur-sm">
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
              label="Identity"
            />
          ) : null}
        </div>

        {mainTab === "people" ? (
          <button
            type="button"
            onClick={() => setBulkCsvOpen(true)}
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border border-zinc-800/80 bg-zinc-950/50 px-4 py-2.5 text-sm font-medium text-zinc-300 backdrop-blur-sm transition hover:border-zinc-700 hover:bg-zinc-900/80 hover:text-zinc-100"
          >
            <FileSpreadsheet className="h-4 w-4" />
            CSV Import / Export
          </button>
        ) : null}
      </div>

      {mainTab === "people" ? (
        <div className="relative space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <PeopleViewToggle view={peopleView} onChange={setPeopleView} />
            <p className="text-xs text-zinc-600">
              {peopleView === "chart"
                ? "Drag nodes to re-parent · double-click to edit"
                : "Drag rows onto managers · expand teams in the hierarchy"}
            </p>
          </div>

          <TeamTagBar
            selectedCount={selectedIds.size}
            onAssign={handleAssignTeam}
            onClearSelection={() => setSelectedIds(new Set())}
          />

          <div className="overflow-hidden rounded-2xl border border-zinc-800/80 bg-gradient-to-br from-zinc-900/60 via-zinc-950/80 to-zinc-950 shadow-xl shadow-black/25">
            {peopleView === "chart" ? chartView : listView}
          </div>

          {selectedEmployee ? (
            <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-violet-500/25 bg-gradient-to-r from-violet-500/10 via-zinc-900/40 to-zinc-950/60 px-4 py-3.5 shadow-lg shadow-violet-500/5">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500/30 to-indigo-600/20 text-sm font-semibold text-violet-100 ring-1 ring-violet-500/30">
                  {selectedEmployee.name
                    .split(/\s+/)
                    .slice(0, 2)
                    .map((part) => part[0]?.toUpperCase() ?? "")
                    .join("")}
                </div>
                <div className="min-w-0">
                  <p className="truncate font-medium text-zinc-100">
                    {selectedEmployee.name}
                  </p>
                  <p className="truncate text-xs text-zinc-500">
                    {selectedEmployee.role}
                    {selectedEmployee.team_name
                      ? ` · ${selectedEmployee.team_name}`
                      : ""}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {onUpdateEmployee ? (
                  <button
                    type="button"
                    onClick={() => setEditingEmployee(selectedEmployee)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700/80 bg-zinc-900/80 px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:border-zinc-600 hover:text-zinc-100"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    Edit
                  </button>
                ) : null}
                {mode === "settings" ? (
                  <button
                    type="button"
                    onClick={() => openIdentityForEmployee(selectedEmployee.id)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-violet-500/30 bg-violet-500/10 px-3 py-1.5 text-xs font-medium text-violet-200 transition hover:bg-violet-500/20"
                  >
                    <Fingerprint className="h-3.5 w-3.5" />
                    Identity mappings
                  </button>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {mainTab === "components" ? (
        <div className="relative overflow-hidden rounded-2xl border border-zinc-800/80 bg-gradient-to-br from-zinc-900/60 via-zinc-950/80 to-zinc-950 p-4 shadow-xl shadow-black/25 sm:p-5">
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

      {mode === "settings" ? (
        <div
          className={
            mainTab === "identity"
              ? "relative overflow-hidden rounded-2xl border border-zinc-800/80 bg-gradient-to-br from-zinc-900/60 via-zinc-950/80 to-zinc-950 p-4 shadow-xl shadow-black/25 sm:p-5"
              : undefined
          }
        >
          <IdentityMappingPanel
            focusEmployeeId={identityFocusEmployeeId}
            preloadProviderMembers
            visible={mainTab === "identity"}
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

      <div className="sticky bottom-4 z-10 flex flex-col gap-3 sm:flex-row">
        {mode === "onboarding" ? (
          <button
            type="button"
            onClick={() => router.push("/onboarding")}
            disabled={isSaving}
            className="rounded-xl border border-zinc-800/80 bg-zinc-950/80 px-4 py-2.5 text-sm font-medium text-zinc-300 backdrop-blur-md transition hover:bg-zinc-900 disabled:opacity-50"
          >
            Back to Integrations
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => void onSave()}
          disabled={isSaving}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 px-4 py-3.5 text-sm font-semibold text-white shadow-lg shadow-emerald-900/30 transition hover:from-emerald-500 hover:to-teal-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSaving ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              {savingLabel ??
                (mode === "onboarding"
                  ? "Ingesting to Cognee…"
                  : "Saving…")}
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
