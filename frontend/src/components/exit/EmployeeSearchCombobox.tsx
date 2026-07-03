"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Search } from "lucide-react";

import type { EmployeeOption } from "@/lib/types";

interface EmployeeSearchComboboxProps {
  employees: EmployeeOption[];
  selectedId: string;
  onSelect: (employeeId: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function EmployeeSearchCombobox({
  employees,
  selectedId,
  onSelect,
  placeholder = "Search by name or role…",
  disabled = false,
}: EmployeeSearchComboboxProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlightIndex, setHighlightIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedEmployee = useMemo(
    () => employees.find((emp) => emp.id === selectedId) ?? null,
    [employees, selectedId],
  );

  useEffect(() => {
    if (selectedEmployee) {
      setQuery(selectedEmployee.name);
    } else if (!selectedId) {
      setQuery("");
    }
  }, [selectedEmployee, selectedId]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return employees;
    return employees.filter(
      (emp) =>
        emp.name.toLowerCase().includes(needle) ||
        emp.role.toLowerCase().includes(needle) ||
        emp.id.toLowerCase().includes(needle),
    );
  }, [employees, query]);

  useEffect(() => {
    setHighlightIndex(0);
  }, [query, filtered.length]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
        if (selectedEmployee) {
          setQuery(selectedEmployee.name);
        }
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [selectedEmployee]);

  function selectEmployee(employee: EmployeeOption) {
    onSelect(employee.id);
    setQuery(employee.name);
    setOpen(false);
  }

  function clearSelection() {
    onSelect("");
    setQuery("");
    setOpen(true);
  }

  return (
    <div ref={containerRef} className="relative">
      <div className="relative flex items-center rounded-lg border border-zinc-700 bg-zinc-900">
        <Search className="pointer-events-none absolute left-3 h-4 w-4 text-zinc-500" />
        <input
          id="exit-employee-search"
          value={query}
          disabled={disabled}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
            if (selectedId) onSelect("");
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(event) => {
            if (!open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
              setOpen(true);
              return;
            }
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setHighlightIndex((prev) =>
                prev + 1 >= filtered.length ? 0 : prev + 1,
              );
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setHighlightIndex((prev) =>
                prev - 1 < 0 ? Math.max(filtered.length - 1, 0) : prev - 1,
              );
            } else if (event.key === "Enter" && open && filtered.length > 0) {
              event.preventDefault();
              selectEmployee(filtered[highlightIndex] ?? filtered[0]!);
            } else if (event.key === "Escape") {
              setOpen(false);
              if (selectedEmployee) setQuery(selectedEmployee.name);
            }
          }}
          placeholder={placeholder}
          className="w-full rounded-lg bg-transparent py-2.5 pl-9 pr-9 text-sm text-zinc-100 outline-none placeholder:text-zinc-600 disabled:opacity-50"
        />
        <button
          type="button"
          tabIndex={-1}
          disabled={disabled}
          onClick={() => setOpen((prev) => !prev)}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-zinc-500 hover:text-zinc-300 disabled:opacity-50"
          aria-label="Toggle employee list"
        >
          <ChevronDown className="h-4 w-4" />
        </button>
      </div>

      {open && !disabled && filtered.length > 0 && (
        <ul className="absolute z-50 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-zinc-700 bg-zinc-950 py-1 shadow-xl">
          {filtered.map((employee, index) => (
            <li key={employee.id}>
              <button
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => selectEmployee(employee)}
                className={`w-full px-3 py-2 text-left ${
                  index === highlightIndex
                    ? "bg-zinc-800 text-zinc-100"
                    : "text-zinc-300 hover:bg-zinc-900"
                }`}
              >
                <p className="text-sm font-medium">{employee.name}</p>
                <p className="text-xs text-zinc-500">{employee.role}</p>
              </button>
            </li>
          ))}
        </ul>
      )}

      {open && !disabled && filtered.length === 0 && query.trim() && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-400 shadow-xl">
          No employees match &ldquo;{query.trim()}&rdquo;
        </div>
      )}

      {selectedId ? (
        <button
          type="button"
          onClick={clearSelection}
          className="mt-2 text-xs text-zinc-500 underline-offset-2 hover:text-zinc-300 hover:underline"
        >
          Clear selection
        </button>
      ) : null}
    </div>
  );
}
