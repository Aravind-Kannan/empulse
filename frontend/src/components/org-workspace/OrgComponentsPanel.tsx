"use client";

import { useEffect, useMemo, useState } from "react";
import { Boxes, Loader2, Pencil, RefreshCw, Trash2 } from "lucide-react";

import { ComponentEditModal } from "@/components/org-workspace/ComponentEditModal";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import {
  DEFAULT_LIST_PAGE_SIZE,
  ListPagination,
  paginateItems,
} from "@/components/ui/ListPagination";
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
  const [page, setPage] = useState(0);
  const [deletingComponentId, setDeletingComponentId] = useState<string | null>(
    null,
  );
  const [pendingDeleteComponent, setPendingDeleteComponent] =
    useState<Component | null>(null);

  const sortedComponents = useMemo(
    () =>
      [...orgChart.components].sort((left, right) =>
        left.name.localeCompare(right.name),
      ),
    [orgChart.components],
  );

  const paginatedComponents = useMemo(
    () => paginateItems(sortedComponents, page, DEFAULT_LIST_PAGE_SIZE),
    [sortedComponents, page],
  );

  useEffect(() => {
    const maxPage = Math.max(
      0,
      Math.ceil(sortedComponents.length / DEFAULT_LIST_PAGE_SIZE) - 1,
    );
    if (page > maxPage) {
      setPage(maxPage);
    }
  }, [sortedComponents.length, page]);

  async function handleDeleteComponent(component: Component) {
    if (!onDeleteComponent) return;

    setDeletingComponentId(component.id);
    try {
      await onDeleteComponent(component.id);
      if (editingComponent?.id === component.id) {
        setEditingComponent(null);
      }
    } finally {
      setDeletingComponentId(null);
    }
  }

  const showActions = Boolean(onUpdateComponent || onDeleteComponent);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 text-sm text-zinc-400">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-violet-500/20 bg-violet-500/10">
            <Boxes className="h-4 w-4 text-violet-300" />
          </span>
          <span>
            <span className="font-medium text-zinc-200">{sortedComponents.length}</span>{" "}
            component{sortedComponents.length === 1 ? "" : "s"} discovered
          </span>
        </div>
        {onRefresh && (
          <button
            type="button"
            onClick={() => void onRefresh()}
            disabled={isRefreshing}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-zinc-800/80 bg-zinc-950/50 px-3 py-2 text-sm font-medium text-zinc-300 transition hover:border-zinc-700 hover:bg-zinc-900/80 disabled:opacity-50"
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
            Sync GitHub or Jira from Integrations to auto-discover
            repositories and project components.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-zinc-800/60 bg-zinc-950/30">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-zinc-800/60 bg-zinc-900/30 text-xs uppercase tracking-[0.12em] text-zinc-500">
              <tr>
                <th className="px-4 py-3 font-medium">Component</th>
                <th className="px-4 py-3 font-medium">Source</th>
                <th className="px-4 py-3 font-medium">Tags</th>
                <th className="px-4 py-3 font-medium">Owners</th>
                {showActions ? (
                  <th className="px-4 py-3 font-medium">Actions</th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {paginatedComponents.map((component) => (
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
                  onDelete={
                    onDeleteComponent
                      ? () => setPendingDeleteComponent(component)
                      : undefined
                  }
                  isDeleting={
                    isDeletingComponent && deletingComponentId === component.id
                  }
                />
              ))}
            </tbody>
          </table>
          <ListPagination
            page={page}
            totalItems={sortedComponents.length}
            onPageChange={setPage}
          />
        </div>
      )}

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

      <ConfirmDialog
        open={pendingDeleteComponent !== null}
        title="Delete component?"
        description={
          pendingDeleteComponent
            ? `Delete "${pendingDeleteComponent.name}"? Assignments for this component will be removed.`
            : ""
        }
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onConfirm={() => {
          if (pendingDeleteComponent) {
            void handleDeleteComponent(pendingDeleteComponent);
          }
          setPendingDeleteComponent(null);
        }}
        onCancel={() => setPendingDeleteComponent(null)}
      />
    </div>
  );
}

function ComponentRow({
  component,
  owners,
  onEdit,
  onDelete,
  isDeleting = false,
}: {
  component: Component;
  owners: string;
  onEdit?: () => void;
  onDelete?: () => void;
  isDeleting?: boolean;
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
      {onEdit || onDelete ? (
        <td className="px-4 py-3">
          <div className="flex items-center gap-1.5">
            {onEdit ? (
              <button
                type="button"
                onClick={onEdit}
                disabled={isDeleting}
                className="rounded-lg border border-zinc-700 p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 disabled:opacity-50"
                title="Edit component"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
            ) : null}
            {onDelete ? (
              <button
                type="button"
                onClick={onDelete}
                disabled={isDeleting}
                className="rounded-lg border border-red-500/30 p-1.5 text-red-400 hover:bg-red-500/10 hover:text-red-300 disabled:opacity-50"
                title="Delete component"
              >
                {isDeleting ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Trash2 className="h-3.5 w-3.5" />
                )}
              </button>
            ) : null}
          </div>
        </td>
      ) : null}
    </tr>
  );
}
