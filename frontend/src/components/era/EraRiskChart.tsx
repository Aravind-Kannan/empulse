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

function weightedBreakdown(employee: EraEmployeeMetrics) {
  return [
    {
      metric: "Unresolved",
      raw: employee.unresolved_issues,
      weighted: employee.unresolved_issues * 5,
    },
    {
      metric: "Open Tasks",
      raw: employee.open_tasks,
      weighted: employee.open_tasks * 3,
    },
    {
      metric: "Undocumented",
      raw: employee.undocumented_solved_incidents,
      weighted: employee.undocumented_solved_incidents * 10,
    },
    {
      metric: "Cognee Share",
      raw: employee.codebase_share_pct,
      weighted: employee.codebase_share_pct * 0.4,
    },
  ];
}

export function EraRiskChart({ employee }: { employee: EraEmployeeMetrics }) {
  const chartData = weightedBreakdown(employee);

  return (
    <div className="mt-4 h-64 w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <BarChart data={chartData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
          <XAxis dataKey="metric" tick={{ fill: "#a1a1aa", fontSize: 11 }} />
          <YAxis tick={{ fill: "#a1a1aa", fontSize: 11 }} />
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
              return [`${numeric.toFixed(1)} pts (raw: ${raw})`, "Weighted"];
            }}
          />
          <Bar dataKey="weighted" fill="#f97316" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
