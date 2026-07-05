"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ChevronDown, X } from "lucide-react";

import {
  DEFAULT_LIST_PAGE_SIZE,
  ListPagination,
  paginateItems,
} from "@/components/ui/ListPagination";
import type { EraDimensionKey, EraEmployeeMetrics } from "@/lib/types";

import { DIMENSION_KEYS, ERA_DIMENSION_COLORS } from "./era-colors";
import { EraDimensionCell } from "./EraDimensionCell";
import { dimensionValue, riskBarClass } from "./era-utils";

type SortField =
  | "highest_risk"
  | EraDimensionKey
  | "ownership";

type SortDirection = "asc" | "desc";
type RiskFilter = "all" | "high" | "medium" | "low";

const PAGE_SIZE_OPTIONS = [10, 25, 50] as const;

const SORT_FIELD_LABELS: Record<SortField, string> = {
  highest_risk: "Overall risk score",
  ownership: "Code ownership %",
  knowledge: ERA_DIMENSION_COLORS.knowledge.label,
  operational: ERA_DIMENSION_COLORS.operational.label,
  documentation: ERA_DIMENSION_COLORS.documentation.label,
  structural: ERA_DIMENSION_COLORS.structural.label,
  burnout: ERA_DIMENSION_COLORS.burnout.label,
};

interface EraRiskHeatmapProps {
  employees: EraEmployeeMetrics[];
  selectedId: string | null;
  onSelect: (employeeId: string) => void;
  onOpenDetailWithDimension?: (
    employeeId: string,
    dimension: EraDimensionKey,
  ) => void;
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
      {Array.from({ length: DEFAULT_LIST_PAGE_SIZE }).map((_, index) => (
        <div key={index} className="h-10 animate-pulse rounded bg-zinc-800/60" />
      ))}
    </div>
  );
}

function sortValue(employee: EraEmployeeMetrics, field: SortField): number {
  if (field === "highest_risk") {
    return employee.risk_factor_score;
  }
  if (field === "ownership") {
    return employee.codebase_share_pct;
  }
  return dimensionValue(employee, field);
}

export function EraRiskHeatmap({
  employees,
  selectedId,
  onSelect,
  onOpenDetailWithDimension,
  loading = false,
}: EraRiskHeatmapProps) {
  const [sortField, setSortField] = useState<SortField>("highest_risk");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [pageSize, setPageSize] = useState(DEFAULT_LIST_PAGE_SIZE);
  const [page, setPage] = useState(0);
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

  const hasActiveFilters =
    riskFilter !== "all" ||
    teamFilter !== "all" ||
    identityOnly ||
    watchlistOnly;

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
    const direction = sortDirection === "desc" ? -1 : 1;
    copy.sort(
      (a, b) =>
        direction * (sortValue(a, sortField) - sortValue(b, sortField)),
    );
    return copy;
  }, [
    employees,
    identityOnly,
    riskFilter,
    sortDirection,
    sortField,
    teamFilter,
    watchlistOnly,
  ]);

  const paginatedRows = useMemo(
    () => paginateItems(filtered, page, pageSize),
    [filtered, page, pageSize],
  );

  useEffect(() => {
    setPage(0);
  }, [
    riskFilter,
    teamFilter,
    identityOnly,
    watchlistOnly,
    sortField,
    sortDirection,
    pageSize,
  ]);

  useEffect(() => {
    const maxPage = Math.max(0, Math.ceil(filtered.length / pageSize) - 1);
    if (page > maxPage) {
      setPage(maxPage);
    }
  }, [filtered.length, page, pageSize]);

  function clearFilters() {
    setRiskFilter("all");
    setTeamFilter("all");
    setIdentityOnly(false);
    setWatchlistOnly(false);
  }

  const rangeStart =
    filtered.length === 0 ? 0 : page * pageSize + 1;
  const rangeEnd = Math.min((page + 1) * pageSize, filtered.length);

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
      <div className="flex flex-col gap-3 border-b border-zinc-800 px-4 py-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-sm font-medium text-zinc-200">Risk heatmap</h2>
          {filtered.length > 0 ? (
            <p className="text-xs tabular-nums text-zinc-500">
              Showing {rangeStart}–{rangeEnd} of {filtered.length}
            </p>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="inline-flex items-center gap-1.5 text-xs text-zinc-500">
            Sort by
            <select
              value={sortField}
              onChange={(event) => setSortField(event.target.value as SortField)}
              className="rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-300"
            >
              <option value="highest_risk">{SORT_FIELD_LABELS.highest_risk}</option>
              {DIMENSION_KEYS.map((key) => (
                <option key={key} value={key}>
                  {SORT_FIELD_LABELS[key]}
                </option>
              ))}
              <option value="ownership">{SORT_FIELD_LABELS.ownership}</option>
            </select>
          </label>

          <label className="inline-flex items-center gap-1.5 text-xs text-zinc-500">
            Order
            <select
              value={sortDirection}
              onChange={(event) =>
                setSortDirection(event.target.value as SortDirection)
              }
              className="rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-300"
            >
              <option value="desc">High → Low</option>
              <option value="asc">Low → High</option>
            </select>
          </label>

          <label className="inline-flex items-center gap-1.5 text-xs text-zinc-500">
            Show
            <select
              value={pageSize}
              onChange={(event) => setPageSize(Number(event.target.value))}
              className="rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-300"
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size} per page
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            onClick={() => setFiltersOpen((open) => !open)}
            className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs ${
              hasActiveFilters
                ? "border-violet-500/40 bg-violet-500/10 text-violet-200"
                : "border-zinc-700 text-zinc-300"
            }`}
          >
            Filters
            {hasActiveFilters ? (
              <span className="rounded-full bg-violet-500/30 px-1.5 text-[10px]">
                on
              </span>
            ) : null}
            <ChevronDown
              className={`h-3.5 w-3.5 transition ${filtersOpen ? "rotate-180" : ""}`}
            />
          </button>
        </div>
      </div>

      {filtersOpen && (
        <div className="flex flex-wrap items-center gap-2 border-b border-zinc-800 px-4 py-3">
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
          {hasActiveFilters ? (
            <button
              type="button"
              onClick={clearFilters}
              className="inline-flex items-center gap-1 rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-400 hover:text-zinc-200"
            >
              <X className="h-3 w-3" />
              Clear filters
            </button>
          ) : null}
        </div>
      )}

      {hasActiveFilters && !filtersOpen ? (
        <div className="flex flex-wrap gap-1.5 border-b border-zinc-800 px-4 py-2">
          {riskFilter !== "all" ? (
            <span className="rounded-full border border-zinc-700 bg-zinc-900 px-2 py-0.5 text-[10px] text-zinc-400">
              Risk: {riskFilter}
            </span>
          ) : null}
          {teamFilter !== "all" ? (
            <span className="rounded-full border border-zinc-700 bg-zinc-900 px-2 py-0.5 text-[10px] text-zinc-400">
              Team: {teamFilter}
            </span>
          ) : null}
          {identityOnly ? (
            <span className="rounded-full border border-zinc-700 bg-zinc-900 px-2 py-0.5 text-[10px] text-zinc-400">
              Incomplete identity
            </span>
          ) : null}
          {watchlistOnly ? (
            <span className="rounded-full border border-zinc-700 bg-zinc-900 px-2 py-0.5 text-[10px] text-zinc-400">
              Departure watchlist
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[56rem] text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-800 text-[11px] tracking-wide text-zinc-500">
              <th className="px-4 py-2 font-medium">Employee</th>
              {DIMENSION_KEYS.map((key) => (
                <th
                  key={key}
                  className={`min-w-[7.5rem] px-2 py-2 font-medium ${ERA_DIMENSION_COLORS[key].text}`}
                >
                  {ERA_DIMENSION_COLORS[key].label}
                </th>
              ))}
              <th className="px-4 py-2 font-medium">Risk</th>
            </tr>
          </thead>
          <tbody>
            {paginatedRows.map((employee) => {
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
                    <td key={key} className="px-2 py-2.5 align-top">
                      <EraDimensionCell
                        employee={employee}
                        dimension={key}
                        onDimensionClick={
                          onOpenDetailWithDimension
                            ? (dimension) =>
                                onOpenDetailWithDimension(
                                  employee.employee_id,
                                  dimension,
                                )
                            : undefined
                        }
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

      <div className="space-y-2 p-3 md:hidden">
        {paginatedRows.map((employee) => {
          const selected = employee.employee_id === selectedId;
          return (
            <div
              key={employee.employee_id}
              className={`rounded-lg border ${
                selected
                  ? "border-violet-500/40 bg-zinc-800/60"
                  : "border-zinc-800 bg-zinc-950/40"
              }`}
            >
              <div
                role="button"
                tabIndex={0}
                onClick={() => onSelect(employee.employee_id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(employee.employee_id);
                  }
                }}
                className="w-full cursor-pointer p-3 text-left"
              >
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="font-medium text-zinc-100">{employee.name}</p>
                    <p className="text-xs text-zinc-500">{employee.role}</p>
                  </div>
                  {riskBadge(employee.risk_level, employee.risk_factor_score)}
                </div>
              </div>
              <div className="space-y-2 border-t border-zinc-800 px-3 pb-3 pt-2">
                {DIMENSION_KEYS.map((key) => (
                  <div key={key} className="flex items-start gap-2">
                    <span
                      className={`w-24 shrink-0 text-[10px] font-medium ${ERA_DIMENSION_COLORS[key].text}`}
                    >
                      {ERA_DIMENSION_COLORS[key].label}
                    </span>
                    <div className="min-w-0 flex-1">
                      <EraDimensionCell
                        employee={employee}
                        dimension={key}
                        showHeadline={false}
                        onDimensionClick={
                          onOpenDetailWithDimension
                            ? (dimension) =>
                                onOpenDetailWithDimension(
                                  employee.employee_id,
                                  dimension,
                                )
                            : undefined
                        }
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length === 0 ? (
        <p className="p-6 text-center text-sm text-emerald-300">
          No high continuity risks detected for current filters.
        </p>
      ) : (
        <ListPagination
          page={page}
          pageSize={pageSize}
          totalItems={filtered.length}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
