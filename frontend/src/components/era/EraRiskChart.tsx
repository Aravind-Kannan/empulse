"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { EraEmployeeMetrics } from "@/lib/types";

import { DIMENSION_KEYS, ERA_DIMENSION_COLORS } from "./era-colors";
import { dimensionValue } from "./era-utils";

function dimensionBreakdown(employee: EraEmployeeMetrics) {
  if (employee.dimensions) {
    return DIMENSION_KEYS.map((key) => ({
      metric: ERA_DIMENSION_COLORS[key].label,
      raw: dimensionValue(employee, key),
      weighted: dimensionValue(employee, key),
      dimension: key,
    }));
  }

  return [
    {
      metric: "Unresolved",
      raw: employee.unresolved_issues,
      weighted: employee.unresolved_issues * 5,
      dimension: "operational" as const,
    },
    {
      metric: "Open Tasks",
      raw: employee.open_tasks,
      weighted: employee.open_tasks * 3,
      dimension: "operational" as const,
    },
    {
      metric: "Undocumented",
      raw: employee.undocumented_solved_incidents,
      weighted: employee.undocumented_solved_incidents * 10,
      dimension: "documentation" as const,
    },
    {
      metric: "Ownership",
      raw: employee.codebase_share_pct,
      weighted: employee.codebase_share_pct * 0.4,
      dimension: "knowledge" as const,
    },
  ];
}

export function EraRiskChart({
  employee,
  compact = false,
}: {
  employee: EraEmployeeMetrics;
  compact?: boolean;
}) {
  const chartData = dimensionBreakdown(employee);
  const height = compact ? "h-56" : "h-64";

  return (
    <div className={`${height} w-full min-w-0`}>
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <BarChart
          data={chartData}
          margin={{ top: 8, right: 8, left: compact ? -8 : -16, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
          <XAxis
            dataKey="metric"
            tick={{ fill: "#a1a1aa", fontSize: compact ? 9 : 11 }}
            interval={0}
            angle={compact ? -25 : 0}
            textAnchor={compact ? "end" : "middle"}
            height={compact ? 50 : 30}
          />
          <YAxis tick={{ fill: "#a1a1aa", fontSize: 11 }} domain={[0, 100]} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#18181b",
              border: "1px solid #3f3f46",
              borderRadius: "8px",
            }}
            labelStyle={{ color: "#e4e4e7" }}
            formatter={(value, _name, item) => {
              const numeric =
                typeof value === "number" ? value : Number(value ?? 0);
              const raw = item?.payload?.raw ?? "—";
              return [`${numeric.toFixed(1)} (raw: ${raw})`, "Score"];
            }}
          />
          <Bar
            dataKey="weighted"
            fill="#a78bfa"
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
