"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

import { useOnboarding } from "@/context/OnboardingContext";
import type { Assignment, Employee } from "@/lib/types";

interface EmployeeEditModalProps {
  employee: Employee;
  onClose: () => void;
}

export function EmployeeEditModal({ employee, onClose }: EmployeeEditModalProps) {
  const { orgChart, updateEmployee, updateAssignment } = useOnboarding();
  const [draft, setDraft] = useState<Employee>(employee);
  const existingAssignment = orgChart.assignments.find(
    (a) => a.employee_id === employee.id,
  );
  const [componentId, setComponentId] = useState(
    existingAssignment?.component_id ?? "",
  );
  const [sharePct, setSharePct] = useState(
    existingAssignment?.codebase_share_pct ?? 0,
  );

  useEffect(() => {
    setDraft(employee);
    setComponentId(existingAssignment?.component_id ?? "");
    setSharePct(existingAssignment?.codebase_share_pct ?? 0);
  }, [employee, existingAssignment]);

  const managerOptions = orgChart.employees.filter((e) => e.id !== employee.id);

  function handleSave() {
    updateEmployee(draft);
    if (componentId) {
      const assignment: Assignment = {
        employee_id: employee.id,
        component_id: componentId,
        codebase_share_pct: sharePct,
      };
      updateAssignment(assignment, employee.id);
    } else {
      updateAssignment(null, employee.id);
    }
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-lg rounded-xl border border-zinc-700 bg-slate-950 shadow-xl">
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <h3 className="text-lg font-medium text-zinc-100">Edit Employee</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 p-5">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2 sm:col-span-1">
              <label className="mb-1 block text-xs text-zinc-500">Name</label>
              <input
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
              />
            </div>
            <div className="col-span-2 sm:col-span-1">
              <label className="mb-1 block text-xs text-zinc-500">Role</label>
              <select
                value={draft.role}
                onChange={(e) => setDraft({ ...draft, role: e.target.value })}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
              >
                <option>Manager</option>
                <option>Engineer</option>
                <option>Support</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="mb-1 block text-xs text-zinc-500">Email</label>
              <input
                type="email"
                value={draft.email}
                onChange={(e) => setDraft({ ...draft, email: e.target.value })}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-zinc-500">
                Tenure (years)
              </label>
              <input
                type="number"
                min={0}
                step={0.1}
                value={draft.tenure_years}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    tenure_years: parseFloat(e.target.value) || 0,
                  })
                }
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-zinc-500">
                Reports to
              </label>
              <select
                value={draft.manager_id ?? ""}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    manager_id: e.target.value || null,
                  })
                }
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
              >
                <option value="">No manager</option>
                {managerOptions.map((manager) => (
                  <option key={manager.id} value={manager.id}>
                    {manager.name} ({manager.role})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
            <p className="mb-3 text-sm font-medium text-zinc-200">
              Technical ownership
            </p>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-xs text-zinc-500">
                  Component
                </label>
                <select
                  value={componentId}
                  onChange={(e) => setComponentId(e.target.value)}
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
                >
                  <option value="">None</option>
                  {orgChart.components.map((component) => (
                    <option key={component.id} value={component.id}>
                      {component.name}
                    </option>
                  ))}
                </select>
              </div>
              {componentId && (
                <div>
                  <label className="mb-1 block text-xs text-zinc-500">
                    Codebase share ({sharePct}%)
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={sharePct}
                    onChange={(e) => setSharePct(Number(e.target.value))}
                    className="w-full"
                  />
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-zinc-800 px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-900"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 hover:bg-white"
          >
            Save changes
          </button>
        </div>
      </div>
    </div>
  );
}
