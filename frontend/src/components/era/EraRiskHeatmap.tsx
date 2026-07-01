"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, ChevronDown } from "lucide-react";

import type { EraDimensionKey, EraEmployeeMetrics } from "@/lib/types";

import { DIMENSION_KEYS, ERA_DIMENSION_COLORS } from "./era-colors";
import { EraDimensionBar } from "./EraDimensionBar";
import {
  dimensionValue,
  isDimensionPartial,
  riskBarClass,
} from "./era-utils";

type SortMode =
  | "highest_risk"
  | EraDimensionKey
  | "ownership";

type RiskFilter = "all" | "high" | "medium" | "low";

interface EraRiskHeatmapProps {
  employees: EraEmployeeMetrics[];
  selectedId: string | null;
  onSelect: (employeeId: string) => void;
  loading?: boolean;
}

function riskBadge(level: EraEmployeeMetrics["risk_level"], score: number) {
  const styles = {
    high: "bg-red-500/15 text-red-300 border-red-500/30",
    medium: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    low: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  }[level];

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium uppercase ${styles}`}
    >
      {level === "high" && <AlertTriangle className="h-3 w-3" />}
      {score}% {level}
    </span>
  );
}

function HeatmapSkeleton() {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: 8 }).map((_, index) => (
        <div key={index} className="h-10 animate-pulse rounded bg-zinc-800/60" />
      ))}
    </div>
  );
}

export function EraRiskHeatmap({
  employees,
  selectedId,
  onSelect,
  loading = false,
}: EraRiskHeatmapProps) {
  const [sortMode, setSortMode] = useState<SortMode>("highest_risk");
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("all");
  const [teamFilter, setTeamFilter] = useState<string>("all");
  const [identityOnly, setIdentityOnly] = useState(false);
  const [watchlistOnly, setWatchlistOnly] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const teams = useMemo(() => {
    const names = new Set<string>();
    for (const employee of employees) {
      if (employee.role) names.add(employee.role.split("·")[0].trim());
    }
    return Array.from(names).sort();
  }, [employees]);

  const filtered = useMemo(() => {
    let rows = employees.filter((employee) => !employee.excluded);
    if (riskFilter !== "all") {
      rows = rows.filter((employee) => employee.risk_level === riskFilter);
    }
    if (teamFilter !== "all") {
      rows = rows.filter((employee) =>
        employee.role.toLowerCase().includes(teamFilter.toLowerCase()),
      );
    }
    if (identityOnly) {
      rows = rows.filter(
        (employee) => (employee.data_completeness_pct ?? 100) < 80,
      );
    }
    if (watchlistOnly) {
      rows = rows.filter((employee) => employee.departure_watchlist);
    }
    const copy = [...rows];
    if (sortMode === "highest_risk") {
      copy.sort((a, b) => b.risk_factor_score - a.risk_factor_score);
    } else if (sortMode === "ownership") {
      copy.sort((a, b) => b.codebase_share_pct - a.codebase_share_pct);
    } else {
      copy.sort(
        (a, b) => dimensionValue(b, sortMode) - dimensionValue(a, sortMode),
      );
    }
    return copy;
  }, [
    employees,
    identityOnly,
    riskFilter,
    sortMode,
    teamFilter,
    watchlistOnly,
  ]);

  if (loading) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/30">
        <div className="border-b border-zinc-800 px-4 py-3 text-sm font-medium text-zinc-200">
          Risk heatmap
        </div>
        <HeatmapSkeleton />
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/30">
      <div className="flex flex-col gap-3 border-b border-zinc-800 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-sm font-medium text-zinc-200">Risk heatmap</h2>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={sortMode}
            onChange={(event) => setSortMode(event.target.value as SortMode)}
            className="rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-300"
          >
            <option value="highest_risk">Highest risk</option>
            {DIMENSION_KEYS.map((key) => (
              <option key={key} value={key}>
                {ERA_DIMENSION_COLORS[key].label}
              </option>
            ))}
            <option value="ownership">Ownership</option>
          </select>
          <button
            type="button"
            onClick={() => setFiltersOpen((open) => !open)}
            className="inline-flex items-center gap-1 rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-300"
          >
            Filters
            <ChevronDown className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {filtersOpen && (
        <div className="flex flex-wrap gap-2 border-b border-zinc-800 px-4 py-3">
          <select
            value={riskFilter}
            onChange={(event) => setRiskFilter(event.target.value as RiskFilter)}
            className="rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-300"
          >
            <option value="all">All risk levels</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select
            value={teamFilter}
            onChange={(event) => setTeamFilter(event.target.value)}
            className="rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-300"
          >
            <option value="all">All teams</option>
            {teams.map((team) => (
              <option key={team} value={team}>
                {team}
              </option>
            ))}
          </select>
          <label className="inline-flex items-center gap-1 text-xs text-zinc-400">
            <input
              type="checkbox"
              checked={identityOnly}
              onChange={(event) => setIdentityOnly(event.target.checked)}
            />
            Incomplete identity
          </label>
          <label className="inline-flex items-center gap-1 text-xs text-zinc-400">
            <input
              type="checkbox"
              checked={watchlistOnly}
              onChange={(event) => setWatchlistOnly(event.target.checked)}
            />
            Departure watchlist
          </label>
        </div>
      )}

      {/* Desktop table */}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-800 text-[11px] uppercase tracking-wide text-zinc-500">
              <th className="px-4 py-2 font-medium">Employee</th>
              {DIMENSION_KEYS.map((key) => (
                <th key={key} className="px-2 py-2 font-medium">
                  {ERA_DIMENSION_COLORS[key].label[0]}
                </th>
              ))}
              <th className="px-4 py-2 font-medium">Risk</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((employee) => {
              const selected = employee.employee_id === selectedId;
              return (
                <tr
                  key={employee.employee_id}
                  role="button"
                  tabIndex={0}
                  aria-selected={selected}
                  onClick={() => onSelect(employee.employee_id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelect(employee.employee_id);
                    }
                  }}
                  className={`cursor-pointer border-b border-zinc-800/60 transition hover:bg-zinc-800/40 ${
                    selected ? "bg-zinc-800/60" : ""
                  }`}
                >
                  <td className="px-4 py-2.5">
                    <p
                      className="max-w-[12rem] truncate font-medium text-zinc-100"
                      title={employee.name}
                    >
                      {employee.name}
                    </p>
                    <p className="max-w-[12rem] truncate text-xs text-zinc-500">
                      {employee.role}
                    </p>
                  </td>
                  {DIMENSION_KEYS.map((key) => (
                    <td key={key} className="px-2 py-2.5">
                      <EraDimensionBar
                        dimension={key}
                        value={dimensionValue(employee, key)}
                        partial={isDimensionPartial(employee, key)}
                      />
                    </td>
                  ))}
                  <td className="px-4 py-2.5">
                    <div className="flex min-w-[10rem] items-center gap-2">
                      <div className="h-2 flex-1 rounded-full bg-zinc-800">
                        <div
                          className={`h-full rounded-full bg-gradient-to-r ${riskBarClass(
                            employee.risk_factor_score,
                          )}`}
                          style={{ width: `${employee.risk_factor_score}%` }}
                        />
                      </div>
                      {riskBadge(employee.risk_level, employee.risk_factor_score)}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="space-y-2 p-3 md:hidden">
        {filtered.map((employee) => {
          const selected = employee.employee_id === selectedId;
          return (
            <button
              key={employee.employee_id}
              type="button"
              onClick={() => onSelect(employee.employee_id)}
              className={`w-full rounded-lg border p-3 text-left ${
                selected
                  ? "border-violet-500/40 bg-zinc-800/60"
                  : "border-zinc-800 bg-zinc-950/40"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="font-medium text-zinc-100">{employee.name}</p>
                  <p className="text-xs text-zinc-500">{employee.role}</p>
                </div>
                {riskBadge(employee.risk_level, employee.risk_factor_score)}
              </div>
              <div className="mt-3 grid grid-cols-5 gap-1">
                {DIMENSION_KEYS.map((key) => (
                  <EraDimensionBar
                    key={key}
                    dimension={key}
                    value={dimensionValue(employee, key)}
                    partial={isDimensionPartial(employee, key)}
                  />
                ))}
              </div>
            </button>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <p className="p-6 text-center text-sm text-emerald-300">
          No high continuity risks detected for current filters.
        </p>
      )}
    </div>
  );
}
