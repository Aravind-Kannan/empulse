"use client";

import { useEffect, useMemo, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCenter,
  pointerWithin,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type CollisionDetection,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { ChevronDown, ChevronRight, GripVertical, Loader2, Pencil, Trash2 } from "lucide-react";

import { AddEmployeeButton } from "@/components/org-workspace/AddEmployeeButton";
import {
  DEFAULT_LIST_PAGE_SIZE,
  ListPagination,
  paginateItems,
} from "@/components/ui/ListPagination";

import {
  buildEmployeeTree,
  flattenTree,
  wouldCreateCycle,
  type FlatRow,
} from "@/lib/org-tree-utils";
import type { Assignment, Component, Employee } from "@/lib/types";

const listDropCollision: CollisionDetection = (args) => {
  const pointerHits = pointerWithin(args);
  if (pointerHits.length > 0) return pointerHits;
  return closestCenter(args);
};

interface OrgListGridViewProps {
  employees: Employee[];
  components?: Component[];
  assignments?: Assignment[];
  selectedIds: Set<string>;
  onToggleSelect: (employeeId: string) => void;
  onReparent: (employeeId: string, managerId: string | null) => void;
  onEditEmployee?: (employee: Employee) => void;
  onDeleteEmployee?: (employeeId: string) => void | Promise<void>;
  deletingEmployeeId?: string | null;
  onAddEmployee?: () => void;
  embedded?: boolean;
}

function DraggableRow({
  row,
  isSelected,
  isCollapsed,
  onToggleCollapse,
  onToggleSelect,
  isDropTarget,
  onEditEmployee,
  onDeleteEmployee,
  deletingEmployeeId = null,
  componentLabel,
}: {
  row: FlatRow;
  isSelected: boolean;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onToggleSelect: () => void;
  isDropTarget: boolean;
  onEditEmployee?: (employee: Employee) => void;
  onDeleteEmployee?: (employeeId: string) => void | Promise<void>;
  deletingEmployeeId?: string | null;
  componentLabel?: string;
}) {
  const { employee, depth, hasChildren } = row;
  const {
    attributes,
    listeners,
    setNodeRef: setDragRef,
    transform,
    isDragging,
  } = useDraggable({ id: employee.id });
  const { setNodeRef: setDropRef, isOver } = useDroppable({
    id: `drop-${employee.id}`,
  });

  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.45 : 1,
  };

  const isDeleting = deletingEmployeeId === employee.id;
  const showActions = onEditEmployee || onDeleteEmployee;

  return (
    <tr
      ref={(node) => {
        setDragRef(node);
        setDropRef(node);
      }}
      style={style}
      className={`border-b border-zinc-800/50 transition-colors ${
        isSelected
          ? "bg-violet-500/10"
          : isOver || isDropTarget
            ? "bg-sky-500/10"
            : "hover:bg-zinc-900/40"
      } ${depth > 0 ? "bg-zinc-950/30" : ""}`}
    >
      <td className="px-3 py-2">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={onToggleSelect}
          className="rounded border-zinc-600 bg-zinc-950"
        />
      </td>
      <td className="px-3 py-2">
        <button
          type="button"
          className="cursor-grab text-zinc-500 hover:text-zinc-300"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-4 w-4" />
        </button>
      </td>
      <td className="px-3 py-3">
        <div
          className="flex items-center gap-2"
          style={{ paddingLeft: `${depth * 1.5}rem` }}
        >
          {hasChildren ? (
            <button
              type="button"
              onClick={onToggleCollapse}
              className="rounded p-0.5 text-zinc-500 hover:bg-zinc-800"
            >
              {isCollapsed ? (
                <ChevronRight className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </button>
          ) : (
            <span className="inline-block w-5" />
          )}
          <div>
            <p className="font-medium text-zinc-100">{employee.name}</p>
            <p className="text-xs text-zinc-500">{employee.role}</p>
          </div>
        </div>
      </td>
      <td className="px-3 py-3 text-sm text-zinc-400">{employee.email}</td>
      <td className="px-3 py-3 text-sm text-zinc-400">
        {employee.team_name ? (
          <span className="rounded-full border border-violet-500/40 bg-violet-500/10 px-2 py-0.5 text-xs text-violet-200">
            {employee.team_name}
          </span>
        ) : (
          "—"
        )}
      </td>
      <td className="px-3 py-3 text-sm text-zinc-400">
        {componentLabel ?? "—"}
      </td>
      {showActions ? (
        <td className="px-3 py-3">
          <div className="flex items-center gap-1.5">
            {onEditEmployee ? (
              <button
                type="button"
                onClick={() => onEditEmployee(employee)}
                disabled={isDeleting}
                className="rounded-lg border border-zinc-700 p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 disabled:opacity-50"
                title="Edit employee"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
            ) : null}
            {onDeleteEmployee ? (
              <button
                type="button"
                onClick={() => {
                  if (
                    window.confirm(
                      `Remove ${employee.name} from the organization? This cannot be undone.`,
                    )
                  ) {
                    void onDeleteEmployee(employee.id);
                  }
                }}
                disabled={isDeleting}
                className="rounded-lg border border-red-500/30 p-1.5 text-red-400 hover:bg-red-500/10 hover:text-red-300 disabled:opacity-50"
                title="Delete employee"
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

function RootDropZone({ colSpan }: { colSpan: number }) {
  const { setNodeRef, isOver } = useDroppable({ id: "drop-root" });

  return (
    <tr ref={setNodeRef}>
      <td colSpan={colSpan} className="px-3 py-2">
        <div
          className={`rounded-lg border border-dashed px-3 py-2 text-center text-xs transition ${
            isOver
              ? "border-sky-500/60 bg-sky-500/10 text-sky-200"
              : "border-zinc-700 text-zinc-500"
          }`}
        >
          Drop here to remove manager (top-level)
        </div>
      </td>
    </tr>
  );
}

export function OrgListGridView({
  employees,
  components = [],
  assignments = [],
  selectedIds,
  onToggleSelect,
  onReparent,
  onEditEmployee,
  onDeleteEmployee,
  deletingEmployeeId = null,
  onAddEmployee,
  embedded = false,
}: OrgListGridViewProps) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [activeId, setActiveId] = useState<string | null>(null);
  const [dropTargetId, setDropTargetId] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  );

  const tree = useMemo(() => buildEmployeeTree(employees), [employees]);
  const rows = useMemo(
    () => flattenTree(tree, collapsed),
    [tree, collapsed],
  );

  const paginatedRows = useMemo(
    () => paginateItems(rows, page, DEFAULT_LIST_PAGE_SIZE),
    [rows, page],
  );

  useEffect(() => {
    const maxPage = Math.max(0, Math.ceil(rows.length / DEFAULT_LIST_PAGE_SIZE) - 1);
    if (page > maxPage) {
      setPage(maxPage);
    }
  }, [rows.length, page]);

  const activeEmployee = employees.find((employee) => employee.id === activeId);
  const showActions = Boolean(onEditEmployee || onDeleteEmployee);
  const columnCount = showActions ? 7 : 6;

  const componentNamesById = useMemo(
    () => new Map(components.map((component) => [component.id, component.name])),
    [components],
  );

  function assignmentLabel(employeeId: string): string | undefined {
    const names = assignments
      .filter((assignment) => assignment.employee_id === employeeId)
      .map((assignment) => componentNamesById.get(assignment.component_id))
      .filter(Boolean) as string[];
    return names.length > 0 ? names.join(", ") : undefined;
  }

  function handleDragStart(event: DragStartEvent) {
    setActiveId(String(event.active.id));
  }

  function handleDragEnd(event: DragEndEvent) {
    const draggedId = String(event.active.id);
    const overId = event.over?.id ? String(event.over.id) : null;
    setActiveId(null);
    setDropTargetId(null);

    if (!overId) return;
    if (overId === "drop-root") {
      if (employees.find((employee) => employee.id === draggedId)?.manager_id) {
        onReparent(draggedId, null);
      }
      return;
    }
    if (overId.startsWith("drop-")) {
      const managerId = overId.replace("drop-", "");
      const draggedEmployee = employees.find(
        (employee) => employee.id === draggedId,
      );
      if (
        managerId !== draggedId &&
        draggedEmployee?.manager_id !== managerId &&
        !wouldCreateCycle(employees, draggedId, managerId)
      ) {
        onReparent(draggedId, managerId);
      }
    }
  }

  function toggleCollapse(employeeId: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(employeeId)) next.delete(employeeId);
      else next.add(employeeId);
      return next;
    });
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={listDropCollision}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragOver={(event) => {
        setDropTargetId(event.over?.id ? String(event.over.id) : null);
      }}
    >
      {onAddEmployee && (
        <div className={`flex justify-end ${embedded ? "border-b border-zinc-800/60 px-4 py-3" : "mb-3"}`}>
          <AddEmployeeButton onClick={onAddEmployee} />
        </div>
      )}

      <div
        className={
          embedded ? "overflow-x-auto" : "overflow-x-auto rounded-xl border border-zinc-800"
        }
      >
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-zinc-800/60 bg-zinc-900/40 text-xs uppercase tracking-[0.12em] text-zinc-500">
            <tr>
              <th className="px-3 py-3 font-medium text-zinc-400">Select</th>
              <th className="px-3 py-3 font-medium text-zinc-400">Drag</th>
              <th className="px-3 py-3 font-medium text-zinc-300">Employee</th>
              <th className="px-3 py-3 font-medium text-zinc-300">Email</th>
              <th className="px-3 py-3 font-medium text-zinc-300">Team</th>
              <th className="px-3 py-3 font-medium text-zinc-300">Components</th>
              {showActions ? (
                <th className="px-3 py-3 font-medium text-zinc-300">Actions</th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {page === 0 ? <RootDropZone colSpan={columnCount} /> : null}
            {paginatedRows.map((row) => (
              <DraggableRow
                key={row.employee.id}
                row={row}
                isSelected={selectedIds.has(row.employee.id)}
                isCollapsed={collapsed.has(row.employee.id)}
                onToggleCollapse={() => toggleCollapse(row.employee.id)}
                onToggleSelect={() => onToggleSelect(row.employee.id)}
                isDropTarget={dropTargetId === `drop-${row.employee.id}`}
                onEditEmployee={onEditEmployee}
                onDeleteEmployee={onDeleteEmployee}
                deletingEmployeeId={deletingEmployeeId}
                componentLabel={assignmentLabel(row.employee.id)}
              />
            ))}
          </tbody>
        </table>
      </div>

      <ListPagination
        page={page}
        totalItems={rows.length}
        onPageChange={setPage}
      />

      <DragOverlay>
        {activeEmployee ? (
          <div className="rounded-lg border border-sky-500/50 bg-slate-950 px-4 py-2 shadow-xl">
            <p className="font-medium text-zinc-100">{activeEmployee.name}</p>
            <p className="text-xs text-zinc-500">{activeEmployee.role}</p>
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
