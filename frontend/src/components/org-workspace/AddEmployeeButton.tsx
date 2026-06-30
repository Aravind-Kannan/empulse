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
      className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white shadow-lg transition hover:bg-emerald-500"
    >
      <Plus className="h-4 w-4" />
      Add Employee
    </button>
  );
}
