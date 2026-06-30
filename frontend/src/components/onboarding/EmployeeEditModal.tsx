"use client";

import { useContext, useEffect, useState } from "react";
import { X } from "lucide-react";

import { ComponentMultiSelect } from "@/components/org-workspace/ComponentMultiSelect";
import { RoleCombobox } from "@/components/org-workspace/RoleCombobox";
import { OnboardingContext } from "@/context/OnboardingContext";
import { collectOrgRoles } from "@/lib/org-master-data";
import type { Assignment, Employee, OrgChartPayload } from "@/lib/types";

interface EmployeeEditModalProps {
  employee: Employee;
  onClose: () => void;
  orgChart?: OrgChartPayload;
  availableRoles?: string[];
  onSave?: (
    employee: Employee,
    assignments: Assignment[],
  ) => void | Promise<void>;
  isSaving?: boolean;
}

export function EmployeeEditModal({
  employee,
  onClose,
  orgChart: orgChartProp,
  availableRoles: availableRolesProp,
  onSave: onSaveProp,
  isSaving = false,
}: EmployeeEditModalProps) {
  const onboarding = useContext(OnboardingContext);
  const orgChart = orgChartProp ?? onboarding?.orgChart;
  if (!orgChart) {
    throw new Error("EmployeeEditModal requires orgChart or OnboardingProvider.");
  }
  const availableRoles =
    availableRolesProp ?? collectOrgRoles(orgChart.employees);
  const [draft, setDraft] = useState<Employee>(employee);
  const existingComponentIds = orgChart.assignments
    .filter((assignment) => assignment.employee_id === employee.id)
    .map((assignment) => assignment.component_id);
  const [componentIds, setComponentIds] = useState<string[]>(existingComponentIds);

  useEffect(() => {
    setDraft(employee);
    setComponentIds(
      orgChart.assignments
        .filter((assignment) => assignment.employee_id === employee.id)
        .map((assignment) => assignment.component_id),
    );
  }, [employee, orgChart.assignments]);

  const managerOptions = orgChart.employees.filter(
    (item) => item.id !== employee.id,
  );

  async function handleSave() {
    const assignments: Assignment[] = componentIds.map((componentId) => ({
      employee_id: employee.id,
      component_id: componentId,
      codebase_share_pct: 0,
    }));

    if (onSaveProp) {
      await onSaveProp(draft, assignments);
    } else if (onboarding) {
      onboarding.updateEmployee(draft);
      onboarding.updateAssignments(assignments, employee.id);
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
                onChange={(event) =>
                  setDraft({ ...draft, name: event.target.value })
                }
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
              />
            </div>
            <div className="col-span-2 sm:col-span-1">
              <label className="mb-1 block text-xs text-zinc-500">
                Role / Title
              </label>
              <RoleCombobox
                value={draft.role}
                suggestions={availableRoles}
                onChange={(role) => setDraft({ ...draft, role })}
              />
            </div>
            <div className="col-span-2 sm:col-span-1">
              <label className="mb-1 block text-xs text-zinc-500">Team tag</label>
              <input
                value={draft.team_name ?? ""}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    team_name: event.target.value || null,
                  })
                }
                placeholder="Platform Reliability Squad"
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
              />
            </div>
            <div className="col-span-2">
              <label className="mb-1 block text-xs text-zinc-500">Email</label>
              <input
                type="email"
                value={draft.email}
                onChange={(event) =>
                  setDraft({ ...draft, email: event.target.value })
                }
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
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    tenure_years: parseFloat(event.target.value) || 0,
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
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    manager_id: event.target.value || null,
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
            <ComponentMultiSelect
              components={orgChart.components}
              selectedIds={componentIds}
              onChange={setComponentIds}
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-zinc-800 px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-900 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={isSaving}
            className="rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 hover:bg-white disabled:opacity-50"
          >
            {isSaving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
