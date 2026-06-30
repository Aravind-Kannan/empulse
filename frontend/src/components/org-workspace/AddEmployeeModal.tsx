"use client";

import { useState } from "react";
import { X } from "lucide-react";

import { RoleCombobox } from "@/components/org-workspace/RoleCombobox";
import type { Employee } from "@/lib/types";

export interface NewEmployeeDraft {
  name: string;
  email: string;
  role: string;
  team_name: string | null;
  manager_id: string | null;
}

interface AddEmployeeModalProps {
  employees: Employee[];
  availableRoles: string[];
  onClose: () => void;
  onSave: (draft: NewEmployeeDraft) => void | Promise<void>;
  isSaving?: boolean;
}

const EMPTY_DRAFT: NewEmployeeDraft = {
  name: "",
  email: "",
  role: "",
  team_name: null,
  manager_id: null,
};

export function AddEmployeeModal({
  employees,
  availableRoles,
  onClose,
  onSave,
  isSaving = false,
}: AddEmployeeModalProps) {
  const [draft, setDraft] = useState<NewEmployeeDraft>(EMPTY_DRAFT);
  const [validationError, setValidationError] = useState<string | null>(null);

  async function handleSave() {
    const name = draft.name.trim();
    const email = draft.email.trim().toLowerCase();
    const role = draft.role.trim();

    if (!name) {
      setValidationError("Name is required.");
      return;
    }
    if (!email || !email.includes("@")) {
      setValidationError("A valid email is required.");
      return;
    }
    if (!role) {
      setValidationError("Role / title is required.");
      return;
    }
    if (employees.some((employee) => employee.email.toLowerCase() === email)) {
      setValidationError("An employee with this email already exists.");
      return;
    }

    setValidationError(null);
    await onSave({
      name,
      email,
      role,
      team_name: draft.team_name?.trim() || null,
      manager_id: draft.manager_id,
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-lg rounded-xl border border-zinc-700 bg-slate-950 shadow-xl">
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <h3 className="text-lg font-medium text-zinc-100">Add Employee</h3>
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
                placeholder="Jordan Lee"
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
              />
            </div>
            <div className="col-span-2 sm:col-span-1">
              <label className="mb-1 block text-xs text-zinc-500">Email</label>
              <input
                type="email"
                value={draft.email}
                onChange={(event) =>
                  setDraft({ ...draft, email: event.target.value })
                }
                placeholder="jordan.lee@acme.com"
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
              <label className="mb-1 block text-xs text-zinc-500">
                Team group name
              </label>
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
                <option value="">No manager (top-level)</option>
                {employees.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {employee.name} ({employee.role})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {validationError && (
            <p className="text-sm text-red-300">{validationError}</p>
          )}
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
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {isSaving ? "Adding…" : "Add employee"}
          </button>
        </div>
      </div>
    </div>
  );
}
