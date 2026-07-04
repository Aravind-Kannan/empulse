"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  GitBranchPlus,
  Pencil,
  Trash2,
  Unlink,
  User,
} from "lucide-react";

import type { Employee } from "@/lib/types";

export type EmployeeFlowNodeData = {
  employee: Employee;
  isSelected: boolean;
  isDropTarget: boolean;
  isHighlighted: boolean;
  isDragging?: boolean;
  onToggleSelect: () => void;
  onEdit?: () => void;
  onUnparent?: () => void;
  onDelete?: () => void;
};

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function EmployeeFlowNodeComponent({
  data,
}: NodeProps & { data: EmployeeFlowNodeData }) {
  const {
    employee,
    isSelected,
    isDropTarget,
    isHighlighted,
    isDragging = false,
    onToggleSelect,
    onEdit,
    onUnparent,
    onDelete,
  } = data;

  const showActions = onEdit || onUnparent || onDelete;

  return (
    <div
      className={`w-[188px] rounded-2xl border p-3 shadow-lg shadow-black/30 ${
        isDragging
          ? "z-20 scale-[1.04] border-sky-400/80 bg-zinc-900/95 ring-2 ring-sky-400/40 shadow-xl shadow-sky-900/30 transition-transform duration-150"
          : isHighlighted
            ? "border-dashed border-amber-400/70 bg-zinc-900/90 ring-1 ring-amber-400/30"
            : isSelected
              ? "border-violet-500/50 bg-gradient-to-br from-violet-500/15 to-indigo-500/5 ring-2 ring-violet-500/30"
              : isDropTarget
                ? "border-sky-400/80 bg-gradient-to-br from-sky-500/15 to-cyan-500/5 ring-2 ring-sky-400/50 transition-colors duration-150"
                : "border-zinc-700/80 bg-zinc-900/90 transition-colors duration-150 hover:border-zinc-500"
      }`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!h-2 !w-2 !border-zinc-600 !bg-zinc-400"
      />

      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          onToggleSelect();
        }}
        onDoubleClick={(event) => {
          event.stopPropagation();
          onEdit?.();
        }}
        className="w-full text-left"
      >
        <div className="mb-2 flex items-center gap-2">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500/30 to-violet-600/25 text-xs font-semibold text-zinc-100 ring-1 ring-white/10">
            {getInitials(employee.name) || <User className="h-4 w-4" />}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-zinc-100">
              {employee.name}
            </p>
            <p className="truncate text-[11px] text-zinc-500">{employee.role}</p>
          </div>
        </div>
        {employee.team_name && (
          <span className="inline-block max-w-full truncate rounded-full border border-violet-500/40 bg-violet-500/10 px-2 py-0.5 text-[10px] text-violet-200">
            {employee.team_name}
          </span>
        )}
      </button>

      {showActions ? (
        <div className="mt-2 flex items-center justify-end gap-1 border-t border-zinc-800/80 pt-2">
          {onUnparent && employee.manager_id ? (
            <button
              type="button"
              title="Remove manager"
              onClick={(event) => {
                event.stopPropagation();
                onUnparent();
              }}
              className="rounded-md border border-zinc-700/80 p-1 text-zinc-400 transition hover:border-zinc-600 hover:bg-zinc-800 hover:text-zinc-200"
            >
              <Unlink className="h-3.5 w-3.5" />
            </button>
          ) : null}
          {onEdit ? (
            <button
              type="button"
              title="Edit"
              onClick={(event) => {
                event.stopPropagation();
                onEdit();
              }}
              className="rounded-md border border-zinc-700/80 p-1 text-zinc-400 transition hover:border-zinc-600 hover:bg-zinc-800 hover:text-zinc-200"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
          ) : null}
          {onDelete ? (
            <button
              type="button"
              title="Remove from org"
              onClick={(event) => {
                event.stopPropagation();
                onDelete();
              }}
              className="rounded-md border border-red-500/30 p-1 text-red-400 transition hover:bg-red-500/10 hover:text-red-300"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          ) : null}
          {isDragging ? (
            <GitBranchPlus className="ml-0.5 h-3.5 w-3.5 text-sky-300" />
          ) : null}
        </div>
      ) : null}

      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-2 !w-2 !border-zinc-600 !bg-zinc-400"
      />
    </div>
  );
}

export const EmployeeFlowNode = memo(EmployeeFlowNodeComponent);

export const employeeFlowNodeTypes = {
  employee: EmployeeFlowNode,
};
