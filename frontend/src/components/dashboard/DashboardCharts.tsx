"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowUpRight } from "lucide-react";

import { useReducedMotion } from "@/hooks/useReducedMotion";
import {
  fetchIncidents,
  fetchKraSummary,
  fetchOrgChart,
} from "@/lib/api";
import type {
  DocumentationCoverageResult,
  Employee,
  IncidentSummary,
} from "@/lib/types";

const REVEAL_EASE = [0.16, 1, 0.3, 1] as const;

const TOOLTIP_STYLE = {
  backgroundColor: "#18181b",
  border: "1px solid #3f3f46",
  borderRadius: 8,
  fontSize: 12,
  color: "#e4e4e7",
};

const TOOLTIP_LABEL_STYLE = { color: "#e4e4e7" };
const TOOLTIP_ITEM_STYLE = { color: "#d4d4d8" };

const LEGEND_STYLE = { color: "#a1a1aa", fontSize: 12 };

interface TooltipEntry {
  name?: string;
  value?: number;
  color?: string;
  payload?: Record<string, unknown>;
}

interface ChartTooltipProps {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string;
  valueLabel?: (value: number, entry: TooltipEntry) => string;
  nameLabel?: (entry: TooltipEntry) => string;
}

function ChartTooltip({
  active,
  payload,
  label,
  valueLabel,
  nameLabel,
}: ChartTooltipProps) {
  if (!active || !payload?.length) return null;

  return (
    <div
      style={{
        ...TOOLTIP_STYLE,
        padding: "8px 12px",
      }}
    >
      {label && (
        <p style={{ ...TOOLTIP_LABEL_STYLE, margin: "0 0 6px", fontWeight: 500 }}>
          {label}
        </p>
      )}
      <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
        {payload.map((entry, index) => {
          const value = typeof entry.value === "number" ? entry.value : 0;
          const displayValue = valueLabel
            ? valueLabel(value, entry)
            : String(value);
          const displayName = nameLabel
            ? nameLabel(entry)
            : (entry.name ?? "Value");

          return (
            <li
              key={`${displayName}-${index}`}
              style={{
                ...TOOLTIP_ITEM_STYLE,
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginTop: index === 0 ? 0 : 4,
              }}
            >
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  backgroundColor: entry.color ?? "#a1a1aa",
                  flexShrink: 0,
                }}
              />
              <span>
                {displayName}: <strong style={{ color: "#f4f4f5" }}>{displayValue}</strong>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

const TENURE_COLORS = ["#f87171", "#fbbf24", "#34d399", "#60a5fa"];
const INCIDENT_COLORS: Record<string, string> = {
  Open: "#f87171",
  Investigating: "#fbbf24",
  "Waiting for Input": "#a78bfa",
  Resolved: "#34d399",
  Closed: "#71717a",
};
const DOC_COLORS = {
  covered: "#34d399",
  missing: "#f87171",
  stale: "#fbbf24",
};

function tenureBuckets(employees: Employee[]) {
  const buckets = [
    { label: "< 1 yr", count: 0 },
    { label: "1–3 yrs", count: 0 },
    { label: "3–5 yrs", count: 0 },
    { label: "5+ yrs", count: 0 },
  ];

  for (const employee of employees) {
    const years = employee.tenure_years;
    if (years < 1) buckets[0].count += 1;
    else if (years < 3) buckets[1].count += 1;
    else if (years < 5) buckets[2].count += 1;
    else buckets[3].count += 1;
  }

  return buckets.map((bucket, index) => ({
    ...bucket,
    fill: TENURE_COLORS[index],
  }));
}

function incidentStatusCounts(incidents: IncidentSummary[]) {
  const order = [
    "Open",
    "Investigating",
    "Waiting for Input",
    "Resolved",
    "Closed",
  ] as const;

  const counts = Object.fromEntries(order.map((status) => [status, 0])) as Record<
    (typeof order)[number],
    number
  >;

  for (const incident of incidents) {
    counts[incident.status] += 1;
  }

  return order
    .map((status) => ({
      status: status === "Waiting for Input" ? "Waiting" : status,
      fullStatus: status,
      count: counts[status],
      fill: INCIDENT_COLORS[status],
    }))
    .filter((row) => row.count > 0 || incidents.length === 0);
}

function documentationBreakdown(coverage: DocumentationCoverageResult | null) {
  if (!coverage) return [];

  const missing = coverage.gap_components.filter(
    (gap) => gap.gap_reason === "missing",
  ).length;
  const stale = coverage.gap_components.filter(
    (gap) => gap.gap_reason === "stale",
  ).length;

  return [
    { name: "Documented", value: coverage.covered_count, fill: DOC_COLORS.covered },
    { name: "Missing docs", value: missing, fill: DOC_COLORS.missing },
    { name: "Stale docs", value: stale, fill: DOC_COLORS.stale },
  ].filter((row) => row.value > 0);
}

interface ChartShellProps {
  title: string;
  description: string;
  href: string;
  delay?: number;
  children: React.ReactNode;
}

function ChartShell({ title, description, href, delay = 0, children }: ChartShellProps) {
  const reducedMotion = useReducedMotion();

  return (
    <motion.section
      initial={reducedMotion ? false : { opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.65, ease: REVEAL_EASE, delay }}
      className="relative overflow-hidden rounded-2xl border border-zinc-800/80 bg-gradient-to-br from-zinc-900/60 to-zinc-950/80 p-5"
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-zinc-200">
            {title}
          </h2>
          <p className="mt-1 text-xs text-zinc-400">{description}</p>
        </div>
        <Link
          href={href}
          className="shrink-0 rounded-lg border border-zinc-800/80 p-1.5 text-zinc-500 transition hover:border-zinc-600 hover:text-zinc-300"
          aria-label={`Open ${title}`}
        >
          <ArrowUpRight className="h-3.5 w-3.5" />
        </Link>
      </div>
      {children}
    </motion.section>
  );
}

function ChartEmpty({ message }: { message: string }) {
  return (
    <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-zinc-800 bg-zinc-950/40 px-4 text-center text-xs text-zinc-500">
      {message}
    </div>
  );
}

function ChartsSkeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {Array.from({ length: 3 }).map((_, index) => (
        <div
          key={index}
          className="h-72 animate-pulse rounded-2xl border border-zinc-800/60 bg-zinc-900/40"
        />
      ))}
    </div>
  );
}

export function DashboardCharts() {
  const [loading, setLoading] = useState(true);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [docCoverage, setDocCoverage] = useState<DocumentationCoverageResult | null>(
    null,
  );

  useEffect(() => {
    let cancelled = false;

    setLoading(true);
    Promise.all([
      fetchOrgChart().catch(() => null),
      fetchIncidents().catch(() => null),
      fetchKraSummary().catch(() => null),
    ])
      .then(([orgChart, incidentResult, kraSummary]) => {
        if (cancelled) return;
        setEmployees(orgChart?.employees ?? []);
        setIncidents(incidentResult?.incidents ?? []);
        setDocCoverage(kraSummary?.documentation_coverage ?? null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const tenureData = useMemo(() => tenureBuckets(employees), [employees]);
  const incidentData = useMemo(() => incidentStatusCounts(incidents), [incidents]);
  const docData = useMemo(() => documentationBreakdown(docCoverage), [docCoverage]);

  if (loading) {
    return <ChartsSkeleton />;
  }

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <ChartShell
        title="Tenure spread"
        description="How long people have been on the team — continuity signal"
        href="/settings/org-chart"
        delay={0.22}
      >
        {employees.length === 0 ? (
          <ChartEmpty message="Add team members to see tenure distribution" />
        ) : (
          <div className="h-48 w-full min-w-0">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <BarChart data={tenureData} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: "#a1a1aa", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: "#a1a1aa", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={28}
                />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.06)" }}
                  content={
                    <ChartTooltip
                      valueLabel={(value) => `${value} people`}
                      nameLabel={() => "Count"}
                    />
                  }
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {tenureData.map((entry) => (
                    <Cell key={entry.label} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </ChartShell>

      <ChartShell
        title="Incident pipeline"
        description="Where active investigations sit in the workflow"
        href="/investigation"
        delay={0.26}
      >
        {incidents.length === 0 ? (
          <ChartEmpty message="No incidents synced yet — connect Jira or Slack" />
        ) : (
          <div className="h-48 w-full min-w-0">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <BarChart
                data={incidentData}
                layout="vertical"
                margin={{ top: 4, right: 12, left: 4, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" horizontal={false} />
                <XAxis
                  type="number"
                  allowDecimals={false}
                  tick={{ fill: "#a1a1aa", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="status"
                  width={72}
                  tick={{ fill: "#a1a1aa", fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.06)" }}
                  content={
                    <ChartTooltip
                      valueLabel={(value) =>
                        `${value} incident${value === 1 ? "" : "s"}`
                      }
                      nameLabel={(entry) =>
                        String(entry.payload?.fullStatus ?? entry.name ?? "Status")
                      }
                    />
                  }
                />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {incidentData.map((entry) => (
                    <Cell key={entry.fullStatus} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </ChartShell>

      <ChartShell
        title="Documentation posture"
        description="Component doc health"
        href="/kra"
        delay={0.3}
      >
        {docData.length === 0 ? (
          <ChartEmpty message="Connect GitHub + Notion to score documentation coverage" />
        ) : (
          <div className="h-48 w-full min-w-0">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <PieChart>
                <Pie
                  data={docData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={48}
                  outerRadius={72}
                  paddingAngle={2}
                >
                  {docData.map((entry) => (
                    <Cell key={entry.name} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip
                  content={
                    <ChartTooltip
                      valueLabel={(value) =>
                        `${value} component${value === 1 ? "" : "s"}`
                      }
                    />
                  }
                />
                <Legend
                  verticalAlign="bottom"
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={LEGEND_STYLE}
                  formatter={(value) => (
                    <span style={{ color: "#a1a1aa" }}>{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </ChartShell>
    </div>
  );
}
