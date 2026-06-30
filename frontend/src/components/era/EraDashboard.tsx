"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowUpDown, Loader2 } from "lucide-react";

import { fetchEraMetrics } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import type { EraEmployeeMetrics } from "@/lib/types";

const EraRiskChart = dynamic(
  () => import("./EraRiskChart").then((mod) => mod.EraRiskChart),
  {
    ssr: false,
    loading: () => (
      <div className="mt-4 flex h-64 items-center justify-center rounded-lg bg-zinc-900/50 text-sm text-zinc-500">
        Loading chart…
      </div>
    ),
  },
);

type SortMode = "highest_risk" | "highest_ownership";

function riskBadge(level: EraEmployeeMetrics["risk_level"], score: number) {
  const styles = {
    high: "bg-red-500/15 text-red-300 border-red-500/30",
    medium: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    low: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  }[level];

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${styles}`}
    >
      {level === "high" && <AlertTriangle className="h-3 w-3" />}
      {score}%
    </span>
  );
}

export function EraDashboard() {
  const { operationalRevision } = useWorkspace();
  const [employees, setEmployees] = useState<EraEmployeeMetrics[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("highest_risk");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchEraMetrics()
      .then((data) => {
        if (cancelled) return;
        setEmployees(data.employees);
        setSelectedId(data.employees[0]?.employee_id ?? null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load metrics. Is the backend running on port 8000?",
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [mounted, operationalRevision]);

  const sortedEmployees = useMemo(() => {
    const copy = [...employees];
    if (sortMode === "highest_risk") {
      copy.sort((a, b) => b.risk_factor_score - a.risk_factor_score);
    } else {
      copy.sort((a, b) => b.codebase_share_pct - a.codebase_share_pct);
    }
    return copy;
  }, [employees, sortMode]);

  const selectedEmployee =
    employees.find((e) => e.employee_id === selectedId) ?? sortedEmployees[0];

  if (!mounted || loading) {
    return (
      <div className="flex h-64 items-center justify-center text-zinc-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading ERA metrics…
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-zinc-100">
          Employee Risk Assessment (ERA)
        </h1>
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">
          {error}
        </div>
        <button
          type="button"
          onClick={() => {
            setLoading(true);
            setError(null);
            fetchEraMetrics()
              .then((data) => {
                setEmployees(data.employees);
                setSelectedId(data.employees[0]?.employee_id ?? null);
              })
              .catch((err) =>
                setError(err instanceof Error ? err.message : "Retry failed"),
              )
              .finally(() => setLoading(false));
          }}
          className="rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 hover:bg-white"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">
            Employee Risk Assessment (ERA)
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Structural vulnerabilities, burnout signals, and knowledge bottlenecks.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/50 p-1">
          <ArrowUpDown className="ml-2 h-4 w-4 text-zinc-500" />
          <button
            type="button"
            onClick={() => setSortMode("highest_risk")}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
              sortMode === "highest_risk"
                ? "bg-zinc-100 text-slate-950"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Highest Risk
          </button>
          <button
            type="button"
            onClick={() => setSortMode("highest_ownership")}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
              sortMode === "highest_ownership"
                ? "bg-zinc-100 text-slate-950"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Highest Code Ownership
          </button>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/30 xl:col-span-2">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-xs uppercase tracking-wide text-zinc-500">
                  <th className="px-4 py-3 font-medium">Employee</th>
                  <th className="px-4 py-3 font-medium">Unresolved</th>
                  <th className="px-4 py-3 font-medium">Open Tasks</th>
                  <th className="px-4 py-3 font-medium">Undocumented</th>
                  <th className="px-4 py-3 font-medium">Code %</th>
                  <th className="px-4 py-3 font-medium">Risk</th>
                </tr>
              </thead>
              <tbody>
                {sortedEmployees.map((employee) => {
                  const isSelected = employee.employee_id === selectedId;
                  return (
                    <tr
                      key={employee.employee_id}
                      onClick={() => setSelectedId(employee.employee_id)}
                      className={`cursor-pointer border-b border-zinc-800/60 transition hover:bg-zinc-800/40 ${
                        isSelected ? "bg-zinc-800/60" : ""
                      }`}
                    >
                      <td className="px-4 py-3">
                        <p className="font-medium text-zinc-100">{employee.name}</p>
                        <p className="text-xs text-zinc-500">{employee.role}</p>
                      </td>
                      <td className="px-4 py-3 text-zinc-300">
                        {employee.unresolved_issues}
                        {(employee.jira_backlog_boost ?? 0) > 0 && (
                          <span className="ml-1 text-xs text-amber-400">
                            (+{employee.jira_backlog_boost} Jira)
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-zinc-300">
                        {employee.open_tasks}
                      </td>
                      <td className="px-4 py-3 text-zinc-300">
                        {employee.undocumented_solved_incidents}
                      </td>
                      <td className="px-4 py-3 text-zinc-300">
                        {employee.codebase_share_pct}%
                      </td>
                      <td className="px-4 py-3">
                        {riskBadge(employee.risk_level, employee.risk_factor_score)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
          <h2 className="text-sm font-medium text-zinc-200">
            Risk breakdown
            {selectedEmployee && (
              <span className="ml-1 font-normal text-zinc-500">
                — {selectedEmployee.name}
              </span>
            )}
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            Weighted contributions to the risk score (capped at 100%)
          </p>
          {selectedEmployee ? (
            <EraRiskChart employee={selectedEmployee} />
          ) : (
            <div className="mt-4 flex h-64 items-center justify-center text-sm text-zinc-500">
              No employee data available
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
