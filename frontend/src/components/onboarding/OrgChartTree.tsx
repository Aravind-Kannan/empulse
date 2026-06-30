"use client";

import { useMemo, useState } from "react";
import { User } from "lucide-react";

import { useOnboarding } from "@/context/OnboardingContext";
import type { Employee } from "@/lib/types";

import { EmployeeEditModal } from "./EmployeeEditModal";

function roleColor(role: string) {
  const normalized = role.toLowerCase();
  if (normalized.includes("manager") || normalized.includes("director") || normalized.includes("head")) {
    return "border-violet-500/50 bg-violet-500/10";
  }
  if (normalized.includes("support") || normalized.includes("customer")) {
    return "border-amber-500/50 bg-amber-500/10";
  }
  return "border-sky-500/50 bg-sky-500/10";
}

function EmployeeNode({
  employee,
  assignmentLabel,
  onSelect,
}: {
  employee: Employee;
  assignmentLabel?: string;
  onSelect: (employee: Employee) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(employee)}
      className={`group flex w-36 flex-col items-center rounded-xl border p-3 text-center transition hover:scale-105 hover:shadow-lg ${roleColor(employee.role)}`}
    >
      <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-zinc-800 text-zinc-300 group-hover:bg-zinc-700">
        <User className="h-5 w-5" />
      </div>
      <p className="text-sm font-medium text-zinc-100">{employee.name}</p>
      <p className="text-xs text-zinc-400">{employee.role}</p>
      {assignmentLabel && (
        <p className="mt-1 truncate text-[10px] text-zinc-500">
          {assignmentLabel}
        </p>
      )}
    </button>
  );
}

export function OrgChartTree() {
  const { orgChart } = useOnboarding();
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(
    null,
  );

  const { roots, childrenByManager } = useMemo(() => {
    const children = new Map<string, Employee[]>();
    const rootsList: Employee[] = [];

    for (const employee of orgChart.employees) {
      if (!employee.manager_id) {
        rootsList.push(employee);
        continue;
      }
      const reports = children.get(employee.manager_id) ?? [];
      reports.push(employee);
      children.set(employee.manager_id, reports);
    }

    return { roots: rootsList, childrenByManager: children };
  }, [orgChart.employees]);

  function assignmentLabel(employeeId: string) {
    const assignments = orgChart.assignments.filter(
      (a) => a.employee_id === employeeId,
    );
    if (assignments.length === 0) return undefined;
    const names = assignments
      .map((assignment) => {
        const component = orgChart.components.find(
          (c) => c.id === assignment.component_id,
        );
        return component?.name;
      })
      .filter(Boolean);
    return names.length > 0 ? names.join(", ") : undefined;
  }

  return (
    <>
      <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/30 p-8">
        <p className="mb-8 text-center text-sm text-zinc-500">
          {orgChart.company} — click any node to edit
        </p>

        <div className="flex min-w-[720px] flex-col items-center gap-10">
          <div className="flex justify-center gap-6">
            {roots.map((root) => (
              <EmployeeNode
                key={root.id}
                employee={root}
                assignmentLabel={assignmentLabel(root.id)}
                onSelect={setSelectedEmployee}
              />
            ))}
          </div>

          {roots.map((root) => {
            const reports = childrenByManager.get(root.id) ?? [];
            if (reports.length === 0) return null;

            return (
              <div key={root.id} className="flex w-full flex-col items-center">
                <div className="mb-6 h-8 w-px bg-zinc-700" />
                <div className="relative flex justify-center gap-4">
                  <div className="absolute top-0 h-px w-[calc(100%-9rem)] bg-zinc-700" />
                  {reports.map((report) => (
                    <div key={report.id} className="flex flex-col items-center">
                      <div className="mb-4 h-6 w-px bg-zinc-700" />
                      <EmployeeNode
                        employee={report}
                        assignmentLabel={assignmentLabel(report.id)}
                        onSelect={setSelectedEmployee}
                      />
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {selectedEmployee && (
        <EmployeeEditModal
          employee={selectedEmployee}
          onClose={() => setSelectedEmployee(null)}
        />
      )}
    </>
  );
}
