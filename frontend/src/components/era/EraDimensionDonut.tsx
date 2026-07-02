"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import type { EraDimensionKey } from "@/lib/types";

import { DIMENSION_KEYS, ERA_DIMENSION_COLORS } from "./era-colors";

interface EraDimensionDonutProps {
  totals: Record<EraDimensionKey, number>;
}

export function EraDimensionDonut({ totals }: EraDimensionDonutProps) {
  const data = DIMENSION_KEYS.map((key) => ({
    name: ERA_DIMENSION_COLORS[key].label,
    value: totals[key],
    color: ERA_DIMENSION_COLORS[key].stroke,
  })).filter((row) => row.value > 0);

  if (data.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-xs text-zinc-500">
        No dimension data
      </div>
    );
  }

  return (
    <div className="h-40 w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={42} outerRadius={64}>
            {data.map((entry) => (
              <Cell key={entry.name} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: "#18181b",
              border: "1px solid #3f3f46",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
