"use client";

import { useMemo, useState } from "react";
import { Boxes, Loader2, Pencil, RefreshCw } from "lucide-react";

import { ComponentEditModal } from "@/components/org-workspace/ComponentEditModal";
import type { Assignment, Component, Employee, OrgChartPayload } from "@/lib/types";

interface OrgComponentsPanelProps {
  orgChart: OrgChartPayload;
  isRefreshing?: boolean;
  onRefresh?: () => void | Promise<void>;
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
}

function componentSourceLabel(description: string): string {
  if (!description.startsWith("AUTO:")) {
    return description.trim() ? "Manual" : "—";
  }
  const tag = description.slice("AUTO:".length);
  if (tag.startsWith("github:")) return "GitHub";
  if (tag.startsWith("jira:")) return "Jira";
  return "Integration";
}

function assigneeNames(
  componentId: string,
  assignments: Assignment[],
  employees: Employee[],
): string {
  const employeeIds = assignments
    .filter((assignment) => assignment.component_id === componentId)
    .map((assignment) => assignment.employee_id);
  if (employeeIds.length === 0) return "Unassigned";

  const names = employeeIds
    .map((id) => employees.find((employee) => employee.id === id)?.name)
    .filter(Boolean) as string[];

  return names.length > 0 ? names.join(", ") : "Unassigned";
}

function formatTags(tags?: string): string {
  const trimmed = (tags ?? "").trim();
  return trimmed || "—";
}

export function OrgComponentsPanel({
  orgChart,
  isRefreshing = false,
  onRefresh,
  onUpdateComponent,
  onDeleteComponent,
  isSavingComponent = false,
  isDeletingComponent = false,
}: OrgComponentsPanelProps) {
  const [editingComponent, setEditingComponent] = useState<Component | null>(null);

  const sortedComponents = useMemo(
    () =>
      [...orgChart.components].sort((left, right) =>
        left.name.localeCompare(right.name),
      ),
    [orgChart.components],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 text-sm text-zinc-400">
          <Boxes className="h-4 w-4 text-zinc-500" />
          <span>
            {sortedComponents.length} component
            {sortedComponents.length === 1 ? "" : "s"} in org chart
          </span>
        </div>
        {onRefresh && (
          <button
            type="button"
            onClick={() => void onRefresh()}
            disabled={isRefreshing}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-zinc-700 px-3 py-2 text-sm text-zinc-300 transition hover:bg-zinc-900 disabled:opacity-50"
          >
            {isRefreshing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Refresh components
          </button>
        )}
      </div>

      {sortedComponents.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-700 bg-zinc-900/30 px-6 py-12 text-center">
          <Boxes className="mx-auto h-8 w-8 text-zinc-600" />
          <p className="mt-4 text-sm font-medium text-zinc-300">No components yet</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-zinc-500">
            Sync GitHub or Jira from Settings → Integrations to auto-discover
            repositories and project components.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-zinc-800">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-zinc-800 bg-zinc-900/60 text-xs uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-4 py-3 font-medium">Component</th>
                <th className="px-4 py-3 font-medium">Source</th>
                <th className="px-4 py-3 font-medium">Tags</th>
                <th className="px-4 py-3 font-medium">Owners</th>
                {onUpdateComponent ? (
                  <th className="px-4 py-3 font-medium">Actions</th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {sortedComponents.map((component) => (
                <ComponentRow
                  key={component.id}
                  component={component}
                  owners={assigneeNames(
                    component.id,
                    orgChart.assignments,
                    orgChart.employees,
                  )}
                  onEdit={
                    onUpdateComponent
                      ? () => setEditingComponent(component)
                      : undefined
                  }
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-zinc-600">
        Edit names and tags here. Assign owners from the List tab when editing an
        employee. Full integration sync dedupes components and syncs to Cognee.
      </p>

      {editingComponent && onUpdateComponent && (
        <ComponentEditModal
          component={editingComponent}
          onClose={() => setEditingComponent(null)}
          onSave={async (componentId, payload) => {
            await onUpdateComponent(componentId, payload);
            setEditingComponent(null);
          }}
          onDelete={
            onDeleteComponent
              ? async (componentId) => {
                  await onDeleteComponent(componentId);
                  setEditingComponent(null);
                }
              : undefined
          }
          isSaving={isSavingComponent}
          isDeleting={isDeletingComponent}
        />
      )}
    </div>
  );
}

function ComponentRow({
  component,
  owners,
  onEdit,
}: {
  component: Component;
  owners: string;
  onEdit?: () => void;
}) {
  const source = componentSourceLabel(component.description);

  return (
    <tr className="border-b border-zinc-800/80 hover:bg-zinc-900/40">
      <td className="px-4 py-3">
        <p className="font-medium text-zinc-100">{component.name}</p>
        <p className="mt-0.5 font-mono text-xs text-zinc-600">{component.id}</p>
      </td>
      <td className="px-4 py-3">
        <span
          className={`rounded-full border px-2 py-0.5 text-xs ${
            source === "GitHub"
              ? "border-violet-500/40 bg-violet-500/10 text-violet-200"
              : source === "Jira"
                ? "border-sky-500/40 bg-sky-500/10 text-sky-200"
                : "border-zinc-600 bg-zinc-800/60 text-zinc-300"
          }`}
        >
          {source}
        </span>
      </td>
      <td className="px-4 py-3 text-zinc-400">{formatTags(component.tags)}</td>
      <td className="px-4 py-3 text-zinc-400">{owners}</td>
      {onEdit ? (
        <td className="px-4 py-3">
          <button
            type="button"
            onClick={onEdit}
            className="rounded-lg border border-zinc-700 p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
            title="Edit component"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
        </td>
      ) : null}
    </tr>
  );
}
