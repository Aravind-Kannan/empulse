"use client";

import { Plus } from "lucide-react";

interface AddEmployeeButtonProps {
  onClick: () => void;
}

export function AddEmployeeButton({ onClick }: AddEmployeeButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 px-3 py-2 text-sm font-medium text-white shadow-md shadow-emerald-900/25 transition hover:from-emerald-500 hover:to-teal-500"
    >
      <Plus className="h-4 w-4" />
      Add Employee
    </button>
  );
}
