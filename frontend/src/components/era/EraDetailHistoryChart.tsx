"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { EraRiskHistoryPoint } from "@/lib/types";
import { formatLocalDate } from "@/lib/datetime";

interface EraDetailHistoryChartProps {
  history: EraRiskHistoryPoint[];
  employeeName: string;
}

function formatDate(value: string) {
  return formatLocalDate(value, { month: "short", day: "numeric" });
}

export function EraDetailHistoryChart({
  history,
  employeeName,
}: EraDetailHistoryChartProps) {
  if (history.length < 2) {
    return (
      <section className="rounded-xl border border-dashed border-zinc-700 bg-zinc-900/20 p-5">
        <h3 className="text-sm font-medium text-zinc-200">30-day risk history</h3>
        <p className="mt-2 text-sm text-zinc-500">
          Risk trend appears after two sync days. Run a global integration sync to
          capture the first snapshot.
        </p>
      </section>
    );
  }

  const data = history.map((point) => ({
    date: formatDate(point.snapshot_date),
    risk: point.risk_factor_score,
  }));

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
      <h3 className="text-sm font-medium text-zinc-200">30-day risk history</h3>
      <p className="mt-1 text-xs text-zinc-500">
        Daily ERA score for {employeeName.split(" ")[0]}
      </p>
      <div className="mt-4 h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid stroke="#27272a" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fill: "#71717a", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fill: "#71717a", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={32}
            />
            <Tooltip
              contentStyle={{
                background: "#18181b",
                border: "1px solid #3f3f46",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ color: "#e4e4e7" }}
              formatter={(value: number) => [`${value}%`, "Risk"]}
            />
            <Line
              type="monotone"
              dataKey="risk"
              stroke="#a78bfa"
              strokeWidth={2}
              dot={{ r: 2, fill: "#a78bfa" }}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
