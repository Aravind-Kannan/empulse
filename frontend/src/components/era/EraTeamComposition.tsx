"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Check, ChevronRight } from "lucide-react";

import type {
  EraDimensionKey,
  EraEmployeeMetrics,
  EraRiskHistoryPoint,
  EraTeamSummary,
} from "@/lib/types";

import { DIMENSION_KEYS, ERA_DIMENSION_COLORS } from "./era-colors";
import {
  EraMultiRiskSparkline,
  EraRiskSparkline,
  EraTrendChip,
} from "./EraRiskSparkline";
import {
  dimensionValue,
  getInitials,
  historyForDimension,
  teamTrendDimensionsForChart,
} from "./era-utils";

interface EraTeamCompositionProps {
  employees: EraEmployeeMetrics[];
  summary: EraTeamSummary;
  teamHistory?: EraRiskHistoryPoint[];
  onSelectEmployee?: (employeeId: string) => void;
}

function historyTrend(history: EraRiskHistoryPoint[]): number | null {
  if (history.length < 2) {
    return null;
  }
  return (
    history[history.length - 1].risk_factor_score -
    history[0].risk_factor_score
  );
}

function riskTextClass(level: "high" | "medium" | "low"): string {
  if (level === "high") return "text-red-300";
  if (level === "medium") return "text-amber-300";
  return "text-emerald-300";
}

function CompactTrendDelta({ trend }: { trend: number | null }) {
  if (trend == null) {
    return null;
  }
  const up = trend > 0;
  const flat = trend === 0;
  return (
    <span
      className={`tabular-nums ${
        flat ? "text-zinc-500" : up ? "text-red-400" : "text-emerald-400"
      }`}
    >
      {flat ? "—" : up ? "▲" : "▼"}
      {Math.abs(trend).toFixed(1)}
    </span>
  );
}

function TeamDimensionBars({
  averages,
  topDriver,
  selectedDimensions,
  onDimensionClick,
}: {
  averages: Record<EraDimensionKey, number>;
  topDriver: EraDimensionKey;
  selectedDimensions: EraDimensionKey[];
  onDimensionClick: (key: EraDimensionKey) => void;
}) {
  const filterActive = selectedDimensions.length > 0;

  return (
    <div>
      <div className="flex items-end justify-between gap-1.5">
        {DIMENSION_KEYS.map((key) => {
          const colors = ERA_DIMENSION_COLORS[key];
          const score = Math.round(averages[key] ?? 0);
          const isTop = key === topDriver;
          const selected = selectedDimensions.includes(key);
          const dimmed = filterActive && !selected;
          return (
            <button
              key={key}
              type="button"
              aria-pressed={selected}
              onClick={() => onDimensionClick(key)}
              className={`flex min-w-0 flex-1 flex-col items-center gap-1 rounded-md px-0.5 py-1 transition ${
                selected
                  ? "bg-violet-500/15 ring-1 ring-violet-500/40"
                  : "hover:bg-zinc-800/60"
              } ${dimmed ? "opacity-45" : ""}`}
              title={`${colors.label}: ${score}% team avg — click to toggle trend`}
            >
              <span
                className={`text-[10px] tabular-nums ${selected ? colors.text : "text-zinc-500"}`}
              >
                {score}%
              </span>
              <div
                className={`relative h-16 w-full max-w-[2.25rem] rounded-sm bg-zinc-800 ${
                  isTop && !filterActive ? "ring-1 ring-violet-500/40" : ""
                }`}
              >
                <div
                  className={`absolute bottom-0 w-full rounded-sm ${colors.bar}`}
                  style={{ height: `${Math.min(100, Math.max(0, score))}%` }}
                />
              </div>
              <span
                className={`text-[8px] font-medium ${selected || isTop ? colors.text : "text-zinc-500"}`}
              >
                {colors.label[0]}
              </span>
            </button>
          );
        })}
      </div>
      <p className="mt-2 text-center text-[10px] text-zinc-600">
        {filterActive
          ? `${selectedDimensions.length} selected — click to toggle trend`
          : "Click a dimension to filter the trend chart"}
      </p>
    </div>
  );
}

function RiskDistributionBar({
  summary,
  activeCount,
}: {
  summary: EraTeamSummary;
  activeCount: number;
}) {
  if (activeCount <= 0) {
    return null;
  }
  const highPct = (summary.high_risk_count / activeCount) * 100;
  const mediumPct = (summary.medium_risk_count / activeCount) * 100;
  const lowPct = (summary.low_risk_count / activeCount) * 100;

  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-zinc-800">
        {highPct > 0 && (
          <div className="bg-red-400" style={{ width: `${highPct}%` }} />
        )}
        {mediumPct > 0 && (
          <div className="bg-amber-400" style={{ width: `${mediumPct}%` }} />
        )}
        {lowPct > 0 && (
          <div className="bg-emerald-400" style={{ width: `${lowPct}%` }} />
        )}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px]">
        <span className="text-red-300">
          High {summary.high_risk_count}
        </span>
        <span className="text-amber-300">
          Medium {summary.medium_risk_count}
        </span>
        <span className="text-emerald-300">Low {summary.low_risk_count}</span>
      </div>
    </div>
  );
}

function TeamStatTile({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "good" | "warn" | "risk";
}) {
  const toneClass =
    tone === "risk"
      ? "border-red-500/25 bg-red-500/5"
      : tone === "warn"
        ? "border-amber-500/25 bg-amber-500/5"
        : tone === "good"
          ? "border-emerald-500/25 bg-emerald-500/5"
          : "border-zinc-800/80 bg-zinc-950/30";

  return (
    <div className={`rounded-lg border px-2.5 py-2 ${toneClass}`}>
      <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
        {label}
      </p>
      <p className="mt-0.5 text-sm font-semibold tabular-nums text-zinc-100">
        {value}
      </p>
      {hint ? <p className="mt-0.5 text-[9px] text-zinc-600">{hint}</p> : null}
    </div>
  );
}

export function EraTeamComposition({
  employees,
  summary,
  teamHistory = [],
  onSelectEmployee,
}: EraTeamCompositionProps) {
  const [filterDimensions, setFilterDimensions] = useState<EraDimensionKey[]>([]);
  const active = employees.filter((employee) => !employee.excluded);
  const driver = ERA_DIMENSION_COLORS[summary.top_risk_driver];
  const trendDimensions = useMemo(
    () => teamTrendDimensionsForChart(summary.top_risk_driver, filterDimensions),
    [summary.top_risk_driver, filterDimensions],
  );
  const multiTrend = trendDimensions.length > 1;
  const dimensionSeries = useMemo(
    () =>
      trendDimensions.map((dimension) => ({
        dimension,
        history: historyForDimension(teamHistory, dimension),
        colors: ERA_DIMENSION_COLORS[dimension],
      })),
    [teamHistory, trendDimensions],
  );
  const singleSeries = dimensionSeries[0];
  const startScore =
    singleSeries && singleSeries.history.length > 0
      ? Math.round(singleSeries.history[0].risk_factor_score)
      : teamHistory.length > 0
        ? Math.round(teamHistory[0].risk_factor_score)
        : null;
  const endScore =
    singleSeries && singleSeries.history.length > 0
      ? Math.round(
          singleSeries.history[singleSeries.history.length - 1].risk_factor_score,
        )
      : teamHistory.length > 0
        ? Math.round(teamHistory[teamHistory.length - 1].risk_factor_score)
        : null;

  function handleDimensionClick(key: EraDimensionKey) {
    setFilterDimensions((current) => {
      if (current.includes(key)) {
        return current.filter((item) => item !== key);
      }
      return current.length === 0 ? [key] : [...current, key];
    });
  }

  const dimensionAverages = useMemo(() => {
    if (active.length === 0) {
      return DIMENSION_KEYS.reduce(
        (acc, key) => {
          acc[key] = 0;
          return acc;
        },
        {} as Record<EraDimensionKey, number>,
      );
    }
    return DIMENSION_KEYS.reduce(
      (acc, key) => {
        const total = active.reduce(
          (sum, employee) => sum + dimensionValue(employee, key),
          0,
        );
        acc[key] = total / active.length;
        return acc;
      },
      {} as Record<EraDimensionKey, number>,
    );
  }, [active]);

  const spofComponents = useMemo(() => {
    const map = new Map<string, { name: string; criticality?: string }>();
    for (const employee of active) {
      for (const component of employee.affected_components ?? []) {
        if (component.spof) {
          map.set(component.id, {
            name: component.name,
            criticality: component.criticality,
          });
        }
      }
    }
    return map;
  }, [active]);

  const identityGaps = useMemo(
    () =>
      active
        .filter((employee) => (employee.data_completeness_pct ?? 100) < 80)
        .sort(
          (left, right) =>
            (left.data_completeness_pct ?? 0) - (right.data_completeness_pct ?? 0),
        ),
    [active],
  );

  const highRiskEmployees = useMemo(
    () =>
      [...active]
        .filter((employee) => employee.risk_level === "high")
        .sort((left, right) => right.risk_factor_score - left.risk_factor_score)
        .slice(0, 6),
    [active],
  );

  const mediumRiskEmployees = useMemo(
    () =>
      [...active]
        .filter((employee) => employee.risk_level === "medium")
        .sort((left, right) => right.risk_factor_score - left.risk_factor_score)
        .slice(0, 4),
    [active],
  );

  const avgRiskLevel: "high" | "medium" | "low" =
    summary.avg_risk_score >= 60
      ? "high"
      : summary.avg_risk_score >= 35
        ? "medium"
        : "low";

  return (
    <section className="flex h-full min-h-[28rem] flex-col rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
            Team composition
          </p>
          <p className="mt-0.5 text-base font-semibold text-zinc-100">
            {active.length} active{" "}
            <span className="font-normal text-zinc-500">
              · {summary.high_risk_count} high risk
            </span>
          </p>
          <span
            className={`mt-1.5 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${driver.text} border-zinc-700/80 bg-zinc-950/50`}
          >
            Top driver: {driver.label}
          </span>
        </div>
        <div className="shrink-0 text-right">
          <p
            className={`text-2xl font-bold tabular-nums leading-none ${riskTextClass(avgRiskLevel)}`}
          >
            {Math.round(summary.avg_risk_score)}%
          </p>
          <p className="mt-0.5 text-[9px] font-medium uppercase tracking-wide text-zinc-500">
            Avg continuity risk
          </p>
          {summary.avg_risk_trend_7d != null && (
            <div className="mt-1 flex justify-end">
              <EraTrendChip trend={summary.avg_risk_trend_7d} />
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 grid flex-1 gap-4 border-t border-zinc-800/80 pt-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="min-w-0">
            <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
              Dimension mix
            </p>
            <p className="mt-0.5 text-[10px] text-zinc-600">
              Team average per dimension
            </p>
            <div className="mt-3">
              <TeamDimensionBars
                averages={dimensionAverages}
                topDriver={summary.top_risk_driver}
                selectedDimensions={filterDimensions}
                onDimensionClick={handleDimensionClick}
              />
            </div>
          </div>

          <div className="min-w-0 sm:border-l sm:border-zinc-800/80 sm:pl-4">
            <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
              30-day trend
              {!multiTrend && singleSeries && (
                <span className={`ml-1.5 normal-case ${singleSeries.colors.text}`}>
                  · {singleSeries.colors.label}
                </span>
              )}
            </p>
            <div className="mt-2 flex items-end gap-2">
              <div className="min-w-0 flex-1">
                {multiTrend ? (
                  <EraMultiRiskSparkline
                    fluid
                    series={dimensionSeries.map((item) => ({
                      id: item.dimension,
                      history: item.history,
                      strokeColor: item.colors.stroke,
                    }))}
                  />
                ) : singleSeries ? (
                  <EraRiskSparkline
                    history={singleSeries.history}
                    fluid
                    strokeColor={singleSeries.colors.stroke}
                  />
                ) : null}
              </div>
              {!multiTrend && singleSeries && (
                <div className="shrink-0 text-right">
                  <EraTrendChip trend={historyTrend(singleSeries.history)} />
                  {startScore != null &&
                    endScore != null &&
                    singleSeries.history.length >= 2 && (
                      <p className="mt-0.5 text-[9px] tabular-nums text-zinc-500">
                        {startScore}% → {endScore}%
                      </p>
                    )}
                </div>
              )}
            </div>
            {multiTrend && (
              <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
                {dimensionSeries.map((item) => (
                  <span
                    key={item.dimension}
                    className="inline-flex items-center gap-1.5 text-[9px]"
                  >
                    <span
                      className="h-0.5 w-3 shrink-0 rounded-full"
                      style={{ backgroundColor: item.colors.stroke }}
                    />
                    <span className={item.colors.text}>{item.colors.label}</span>
                    <CompactTrendDelta trend={historyTrend(item.history)} />
                  </span>
                ))}
              </div>
            )}
            <div className="mt-4">
              <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
                Risk distribution
              </p>
              <div className="mt-2">
                <RiskDistributionBar summary={summary} activeCount={active.length} />
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <TeamStatTile
            label="Recovery"
            value={`${summary.estimated_recovery_weeks.min}–${summary.estimated_recovery_weeks.max} wk`}
            hint="If key person leaves"
          />
          <TeamStatTile
            label="Org health"
            value={`${summary.org_health_score ?? 0}%`}
            tone={
              (summary.org_health_score ?? 0) >= 70
                ? "good"
                : (summary.org_health_score ?? 0) >= 45
                  ? "neutral"
                  : "warn"
            }
          />
          <TeamStatTile
            label="Data health"
            value={`${Math.round(summary.data_health_pct)}%`}
            tone={summary.data_health_pct >= 80 ? "good" : "warn"}
            hint="Identity & signal coverage"
          />
          <TeamStatTile
            label="Hotspots"
            value={String(summary.critical_hotspot_count ?? 0)}
            tone={(summary.critical_hotspot_count ?? 0) > 0 ? "risk" : "good"}
            hint="Critical file silos"
          />
        </div>

        {(highRiskEmployees.length > 0 || mediumRiskEmployees.length > 0) && (
          <div className="grid gap-3 sm:grid-cols-2">
            {highRiskEmployees.length > 0 && (
              <div className="min-w-0">
                <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
                  Highest risk
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {highRiskEmployees.map((employee) => {
                    const chip = (
                      <span className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-red-500/25 bg-red-500/5 px-2 py-1.5 text-[10px] text-zinc-300">
                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-red-500/15 text-[9px] font-medium text-red-200">
                          {getInitials(employee.name)}
                        </span>
                        <span className="min-w-0 truncate">{employee.name}</span>
                        <span className="shrink-0 tabular-nums text-red-300">
                          {Math.round(employee.risk_factor_score)}%
                        </span>
                      </span>
                    );
                    if (onSelectEmployee) {
                      return (
                        <button
                          key={employee.employee_id}
                          type="button"
                          onClick={() => onSelectEmployee(employee.employee_id)}
                          className="max-w-full text-left transition hover:brightness-110"
                        >
                          {chip}
                        </button>
                      );
                    }
                    return <span key={employee.employee_id}>{chip}</span>;
                  })}
                </div>
              </div>
            )}
            {mediumRiskEmployees.length > 0 && (
              <div className="min-w-0 sm:border-l sm:border-zinc-800/80 sm:pl-4">
                <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
                  Medium risk
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {mediumRiskEmployees.map((employee) => {
                    const chip = (
                      <span className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-amber-500/20 bg-amber-500/5 px-2 py-1.5 text-[10px] text-zinc-300">
                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-500/15 text-[9px] font-medium text-amber-200">
                          {getInitials(employee.name)}
                        </span>
                        <span className="min-w-0 truncate">{employee.name}</span>
                        <span className="shrink-0 tabular-nums text-amber-300">
                          {Math.round(employee.risk_factor_score)}%
                        </span>
                      </span>
                    );
                    if (onSelectEmployee) {
                      return (
                        <button
                          key={employee.employee_id}
                          type="button"
                          onClick={() => onSelectEmployee(employee.employee_id)}
                          className="max-w-full text-left transition hover:brightness-110"
                        >
                          {chip}
                        </button>
                      );
                    }
                    return <span key={employee.employee_id}>{chip}</span>;
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="mt-auto grid gap-3 border-t border-zinc-800/80 pt-3 sm:grid-cols-2">
        <div className="min-w-0">
          <div className="flex items-baseline justify-between gap-2">
            <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
              SPOF components
            </p>
            <span className="text-[9px] tabular-nums text-zinc-600">
              {spofComponents.size}
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {Array.from(spofComponents.entries())
              .slice(0, 8)
              .map(([id, component]) => (
              <Link
                key={id}
                href={`/kra?highlight=${encodeURIComponent(id)}`}
                className="inline-flex max-w-full items-center gap-1 rounded border border-orange-500/30 bg-orange-500/5 px-1.5 py-0.5 text-[9px] text-zinc-300 transition hover:border-orange-500/50 hover:bg-orange-500/10"
              >
                <span className="h-1 w-1 shrink-0 rounded-full bg-orange-400" />
                <span className="truncate">{component.name}</span>
                <span className="shrink-0 text-[8px] font-medium uppercase text-orange-400">
                  SPOF
                </span>
              </Link>
            ))}
            {spofComponents.size > 8 && (
              <span className="self-center text-[9px] text-zinc-600">
                +{spofComponents.size - 8} more
              </span>
            )}
            {spofComponents.size === 0 && (
              <span className="text-[10px] text-zinc-500">No SPOF flagged</span>
            )}
          </div>
          <Link
            href="/kra?filter=spof"
            className="mt-1.5 inline-flex items-center gap-0.5 text-[10px] text-violet-300 hover:text-violet-200"
          >
            Open KRA
            <ChevronRight className="h-3 w-3" />
          </Link>
        </div>

        <div className="min-w-0 sm:border-l sm:border-zinc-800/80 sm:pl-3">
          <div className="flex items-baseline justify-between gap-2">
            <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
              Identity gaps
            </p>
            {identityGaps.length > 0 && (
              <span className="text-[9px] tabular-nums text-amber-400/80">
                {identityGaps.length}
              </span>
            )}
          </div>
          {identityGaps.length > 0 ? (
            <>
              <ul className="mt-2 space-y-1.5">
                {identityGaps.slice(0, 6).map((employee) => {
                  const row = (
                    <span className="flex min-w-0 items-center gap-2 rounded-md border border-amber-500/20 bg-amber-500/5 px-2.5 py-1.5">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-500/15 text-[9px] font-medium text-amber-200">
                        {getInitials(employee.name)}
                      </span>
                      <span className="min-w-0 flex-1 truncate text-[10px] text-zinc-300">
                        {employee.name}
                      </span>
                      <span className="shrink-0 text-[9px] tabular-nums text-amber-300">
                        {employee.data_completeness_pct ?? 0}%
                      </span>
                    </span>
                  );
                  if (onSelectEmployee) {
                    return (
                      <li key={employee.employee_id}>
                        <button
                          type="button"
                          onClick={() => onSelectEmployee(employee.employee_id)}
                          className="w-full text-left transition hover:brightness-110"
                        >
                          {row}
                        </button>
                      </li>
                    );
                  }
                  return <li key={employee.employee_id}>{row}</li>;
                })}
              </ul>
              <Link
                href="/settings/org-chart?tab=identity"
                className="mt-1.5 inline-flex items-center gap-0.5 text-[10px] text-violet-300 hover:text-violet-200"
              >
                Fix mappings
                <ChevronRight className="h-3 w-3" />
              </Link>
            </>
          ) : (
            <p className="mt-1.5 flex items-center gap-1 text-[10px] text-zinc-500">
              <Check className="h-3 w-3 text-emerald-500/80" />
              All identities mapped
            </p>
          )}
        </div>
        </div>
      </div>
    </section>
  );
}
